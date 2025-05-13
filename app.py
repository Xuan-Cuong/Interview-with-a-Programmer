import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS # Cần thiết nếu frontend và backend chạy trên các cổng khác nhau
from dotenv import load_dotenv
import google.generativeai as genai
import json # Để lưu/tải trạng thái phỏng vấn đơn giản

load_dotenv() # Load biến môi trường từ file .env

# Cấu hình Google AI API
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env file")
genai.configure(api_key=API_KEY)

# Chọn model phù hợp (ví dụ: gemini-pro)
# Tùy thuộc vào khả năng và giới hạn của các model hiện tại của Google AI Studio
MODEL_NAME = "gemini-2.0-flash" # Hoặc model khác phù hợp

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    print(f"Error loading model {MODEL_NAME}: {e}")
    print("Please ensure you have a valid API key and the model name is correct and available.")
    # Thoát hoặc xử lý lỗi phù hợp
    exit()


app = Flask(__name__, static_folder='.')
CORS(app) # Cho phép Cross-Origin requests (quan trọng khi dev)

# --- State Management for Interview ---
# In a real app, use sessions or database. For this example, a simple dict works
# Structure: { "session_id": { "topic": "...", "question_index": 0, "history": [...], "score": 0 } }
# We'll simulate a single user for simplicity here, not using session_id
interview_state = {
    "active": False,
    "topic": None,
    "current_question_index": 0,
    "questions": [],
    "answers": [],
    "feedback": [],
    "score": 0
}
MAX_QUESTIONS = 10

# --- Helper Function to generate AI responses ---
def generate_ai_response(prompt, history=None):
    try:
        chat = model.start_chat(history=history if history is not None else [])
        response = chat.send_message(prompt)
        # Sometimes content is blocked, check for response.text
        if hasattr(response, 'text'):
            return response.text.strip()
        else:
             print("AI response blocked or empty:", response)
             return "Xin lỗi, tôi không thể tạo phản hồi cho yêu cầu này."
    except Exception as e:
        print(f"AI API Error: {e}")
        return f"Đã xảy ra lỗi khi giao tiếp với AI: {e}"


# --- API Endpoints ---

# Serve index.html
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Serve static files
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/interview/start', methods=['POST'])
def start_interview():
    data = request.json
    topic = data.get('topic')
    if not topic:
        return jsonify({"error": "Chưa chọn chủ đề phỏng vấn."}), 400

    print(f"Starting interview on topic: {topic}")

    # Reset state
    global interview_state
    interview_state = {
        "active": True,
        "topic": topic,
        "current_question_index": 0,
        "questions": [],
        "answers": [],
        "feedback": [],
        "score": 0
    }

    # Generate first question
    prompt = f"""Bạn là một chuyên gia phỏng vấn lập trình viên. Hãy tạo câu hỏi phỏng vấn đầu tiên về chủ đề "{topic}". Câu hỏi cần rõ ràng, súc tích và phù hợp với cấp độ trung bình."""
    first_question = generate_ai_response(prompt)

    if "Đã xảy ra lỗi" in first_question or "không thể tạo phản hồi" in first_question:
         interview_state["active"] = False # Deactivate if AI fails
         return jsonify({"error": first_question}), 500


    interview_state["questions"].append(first_question)

    return jsonify({
        "question": first_question,
        "question_number": 1,
        "total_questions": MAX_QUESTIONS,
        "topic": topic
    })

@app.route('/interview/answer', methods=['POST'])
def submit_answer():
    data = request.json
    user_answer = data.get('answer')

    if not interview_state["active"]:
         return jsonify({"error": "Cuộc phỏng vấn chưa được bắt đầu hoặc đã kết thúc."}), 400

    topic = interview_state["topic"]
    current_index = interview_state["current_question_index"]
    current_question = interview_state["questions"][current_index]

    if user_answer is None:
         return jsonify({"error": "Chưa nhập câu trả lời."}), 400

    interview_state["answers"].append(user_answer)

    print(f"Processing answer for Q{current_index + 1}: {user_answer}")

    # --- AI Process Answer, Feedback, and Next Question ---
    # Build history for better context
    history_for_ai = []
    for i in range(current_index + 1):
        history_for_ai.append({"role": "user", "parts": [interview_state["questions"][i]]})
        if i < current_index: # Add previous answers and feedback to history
            history_for_ai.append({"role": "model", "parts": [f"Feedback: {interview_state['feedback'][i]}\nNext Question: {interview_state['questions'][i+1]}"]})
        elif i == current_index: # Add the current answer
             history_for_ai.append({"role": "user", "parts": [user_answer]})


    feedback_and_next_prompt = f"""
Bạn là chuyên gia phỏng vấn. Dựa trên câu hỏi trước ("{current_question}") và câu trả lời của ứng viên ("{user_answer}"), hãy:
1. Đánh giá câu trả lời: Cung cấp phản hồi ngắn gọn (khoảng 2-3 dòng) về điểm mạnh, điểm cần cải thiện hoặc mức độ phù hợp.
2. Chuẩn bị câu hỏi tiếp theo: Nếu đây là câu hỏi thứ {current_index + 1} (trong tổng số {MAX_QUESTIONS} câu), hãy tạo câu hỏi thứ {current_index + 2} (nếu chưa đủ {MAX_QUESTIONS} câu) về chủ đề "{topic}", dựa trên câu trả lời vừa rồi hoặc một khía cạnh khác của chủ đề.
3. Định dạng phản hồi của bạn theo cấu trúc sau (sử dụng dấu phân cách rõ ràng):
---FEEDBACK---
[Phản hồi đánh giá câu trả lời ở đây]
---NEXT_QUESTION---
[Câu hỏi tiếp theo ở đây, hoặc thông báo "END_INTERVIEW" nếu đã đủ 10 câu]
---SCORE_HINT---
[Gợi ý ngắn gọn (1-2 từ) về mức độ đánh giá cho câu trả lời này (ví dụ: "Good", "OK", "Needs Improvement"). Dùng tiếng Anh để dễ xử lý hơn.]
"""

    ai_response_text = generate_ai_response(feedback_and_next_prompt, history=history_for_ai)

    if "Đã xảy ra lỗi" in ai_response_text or "không thể tạo phản hồi" in ai_response_text:
         interview_state["active"] = False # Deactivate if AI fails
         return jsonify({"error": ai_response_text}), 500


    # Parse AI response
    feedback = "Không có phản hồi từ AI."
    next_question = "END_INTERVIEW"
    score_hint = "Neutral" # Default hint

    parts = ai_response_text.split("---")
    try:
        for i in range(len(parts)):
            if parts[i].strip() == "FEEDBACK" and i + 1 < len(parts):
                feedback = parts[i+1].strip()
            elif parts[i].strip() == "NEXT_QUESTION" and i + 1 < len(parts):
                next_question = parts[i+1].strip()
            elif parts[i].strip() == "SCORE_HINT" and i + 1 < len(parts):
                 score_hint = parts[i+1].strip()
    except Exception as e:
        print(f"Error parsing AI response format: {e}")
        print("AI response text:", ai_response_text)
        feedback = f"Lỗi xử lý phản hồi từ AI: {e}. Phản hồi gốc: {ai_response_text}"
        next_question = "END_INTERVIEW" # Force end if parsing fails badly
        score_hint = "Error"


    interview_state["feedback"].append(feedback)

    # Simple scoring based on hint
    if "Good" in score_hint:
        interview_state["score"] += 10 # Example points
    elif "OK" in score_hint or "Improvement" in score_hint:
        interview_state["score"] += 5 # Example points
    # Add more scoring logic if needed

    response_data = {
        "feedback": feedback,
        "question_number": current_index + 1, # This is the number of the question just answered
        "total_questions": MAX_QUESTIONS,
        "score_hint": score_hint # Optional: send hint to frontend
    }

    interview_state["current_question_index"] += 1

    if interview_state["current_question_index"] < MAX_QUESTIONS and next_question != "END_INTERVIEW":
        interview_state["questions"].append(next_question)
        response_data["next_question"] = next_question
        response_data["status"] = "continue"
    else:
        # --- Generate Final Score ---
        final_score_prompt = f"""
        Bạn là chuyên gia đánh giá kết quả phỏng vấn. Dựa trên chủ đề "{topic}" và toàn bộ lịch sử phỏng vấn:
        {json.dumps({"questions": interview_state["questions"], "answers": interview_state["answers"], "feedback": interview_state["feedback"]}, indent=2)}
        Hãy cung cấp một đánh giá tổng quan ngắn gọn (khoảng 3-5 dòng) và một điểm số cuối cùng (ví dụ: X/100 hoặc thang điểm khác tùy ý bạn, nhưng phải có con số).
        Định dạng kết quả theo cấu trúc:
        ---SUMMARY---
        [Đánh giá tổng quan]
        ---FINAL_SCORE---
        [Điểm số cuối cùng (chỉ con số hoặc chuỗi điểm)]
        """
        final_evaluation_text = generate_ai_response(final_score_prompt)

        summary = "Không có tóm tắt từ AI."
        final_score_str = f"{interview_state['score']}/?" # Fallback using internal score

        parts = final_evaluation_text.split("---")
        try:
             for i in range(len(parts)):
                 if parts[i].strip() == "SUMMARY" and i + 1 < len(parts):
                     summary = parts[i+1].strip()
                 elif parts[i].strip() == "FINAL_SCORE" and i + 1 < len(parts):
                     final_score_str = parts[i+1].strip()
        except Exception as e:
            print(f"Error parsing final evaluation: {e}")
            print("Final evaluation text:", final_evaluation_text)


        response_data["status"] = "finished"
        response_data["final_summary"] = summary
        response_data["final_score"] = final_score_str # Use AI generated score string

        # Reset state after finishing
        interview_state["active"] = False


    return jsonify(response_data)


@app.route('/research', methods=['POST'])
def perform_research():
    data = request.json
    topic = data.get('topic')
    if not topic:
        return jsonify({"error": "Chưa nhập chủ đề nghiên cứu."}), 400

    print(f"Performing research on topic: {topic}")

    # --- AI Research Simulation ---
    # The AI doesn't browse the web in real-time via this API.
    # It uses its training data to summarize information it knows.
    # To simulate 'finding information', we ask it to act as a researcher.
    research_prompt = f"""
    Bạn là một nhà nghiên cứu chuyên nghiệp. Hãy tổng hợp thông tin và tạo một báo cáo chi tiết (khoảng 300-500 từ) về chủ đề "{topic}". Báo cáo cần bao gồm các điểm chính, ứng dụng (nếu có), thách thức hoặc xu hướng liên quan. Trình bày báo cáo một cách rõ ràng, có cấu trúc.
    """

    research_report = generate_ai_response(research_prompt)

    if "Đã xảy ra lỗi" in research_report or "không thể tạo phản hồi" in research_report:
         return jsonify({"error": research_report}), 500

    return jsonify({"report": research_report})

if __name__ == '__main__':
    # Chạy Flask server
    # host='0.0.0.0' để có thể truy cập từ mạng nội bộ
    # debug=True để tự động load lại khi code thay đổi (chỉ dùng khi phát triển)
    app.run(debug=True, host='0.0.0.0', port=5000)