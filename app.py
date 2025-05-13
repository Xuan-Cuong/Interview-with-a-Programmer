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
    # Log an error or raise a more specific exception if preferred
    print("Error: GOOGLE_API_KEY not found in .env file. Please create a .env file with your API key.")
    # As a fallback for local testing without .env, you might prompt or use None, but raising is safer.
    # For now, we'll raise the original error if the key isn't found.
    raise ValueError("GOOGLE_API_KEY not found in .env file")

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
     print(f"Error configuring Google AI with provided API key: {e}")
     print("Please check your GOOGLE_API_KEY in the .env file.")
     # Depending on severity, you might raise here or proceed with limited functionality
     # For now, let's proceed but AI calls will likely fail if configuration failed.


# Chọn model phù hợp (ví dụ: gemini-pro)
# Tùy thuộc vào khả năng và giới hạn của các model hiện tại của Google AI Studio
MODEL_NAME = "gemini-2.0-flash" # Hoặc model khác phù hợp

# Simple check if the model is available (optional but good practice)
# This check itself can sometimes fail depending on the API status,
# so handle potential exceptions here as well.
try:
    # This is a lightweight way to check if the model name is valid
    # A more robust check might involve listing models, but this is simpler.
    test_model = genai.GenerativeModel(MODEL_NAME)
    print(f"Successfully loaded model: {MODEL_NAME}")
except Exception as e:
    print(f"Error loading model {MODEL_NAME}: {e}")
    print("Please ensure you have a valid API key and the model name is correct and available for your account.")
    print("Proceeding, but AI calls might fail.")
    # Set model to None or handle failure appropriately in API endpoints
    test_model = None # Indicate model failed to load


model = test_model # Use the potentially None model

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
    if model is None:
        print("Attempted AI call but model failed to load.")
        return "Đã xảy ra lỗi: Mô hình AI không khả dụng."
    try:
        # Gemini-2.0-flash might handle system instructions differently or prefer prompt format.
        # Let's try providing the full context in the prompt itself.
        chat = model.start_chat(history=history if history is not None else [])
        response = chat.send_message(prompt)
        # Sometimes content is blocked, check for response.text
        if hasattr(response, 'text'):
            return response.text.strip()
        else:
             print("AI response blocked or empty:", response)
             # Check for safety ratings if response is blocked
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                  print(f"Block reason: {response.prompt_feedback.block_reason}")
                  return "Xin lỗi, yêu cầu của bạn bị chặn do nội dung không phù hợp."
             elif response.candidates and response.candidates[0].finish_reason:
                 print(f"Finish reason: {response.candidates[0].finish_reason}")
                 return "Xin lỗi, tôi không thể tạo phản hồi hoàn chỉnh."
             else:
                 return "Xin lỗi, tôi không thể tạo phản hồi cho yêu cầu này."
    except Exception as e:
        print(f"AI API Error: {e}")
        # Check for specific API errors if possible
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
    prompt = f"""Bạn là một chuyên gia phỏng vấn lập trình viên. Hãy tạo câu hỏi phỏng vấn đầu tiên về chủ đề "{topic}". Câu hỏi cần rõ ràng, súc tích và phù hợp với cấp độ trung bình. Sử dụng **định dạng đậm** cho các thuật ngữ quan trọng nếu cần. Chỉ trả về câu hỏi, không có lời giới thiệu hay kết thúc."""
    first_question = generate_ai_response(prompt)

    if "Đã xảy ra lỗi" in first_question or "không thể tạo phản hồi" in first_question or "bị chặn" in first_question:
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
    # Ensure we don't go out of bounds if state is inconsistent
    if current_index >= len(interview_state["questions"]):
         return jsonify({"error": "Lỗi trạng thái phỏng vấn. Vui lòng bắt đầu lại."}), 500

    current_question = interview_state["questions"][current_index]

    # Allow empty answers, feedback will reflect it
    if user_answer is None:
         user_answer = "" # Treat None as empty string


    interview_state["answers"].append(user_answer)

    print(f"Processing answer for Q{current_index + 1}: {user_answer}")

    # --- AI Process Answer, Feedback, and Next Question ---
    # Build history for better context
    # Reconstruct history for the AI to understand the conversation flow
    history_for_ai = []
    for i in range(current_index):
        # AI asks question (model role in history)
        history_for_ai.append({"role": "model", "parts": [f"Câu hỏi {i+1}: {interview_state['questions'][i]}"]})
        # User answers (user role in history)
        history_for_ai.append({"role": "user", "parts": [interview_state["answers"][i]]})
        # AI provides feedback and next question (model role) - Combine for history
        # Format this part clearly for the AI
        if i < len(interview_state["feedback"]) and i + 1 < len(interview_state["questions"]):
             combined_model_turn = f"Phản hồi: {interview_state['feedback'][i]}\n"
             combined_model_turn += f"Câu hỏi {i+2}: {interview_state['questions'][i+1]}"
             history_for_ai.append({"role": "model", "parts": [combined_model_turn]})


    # Add the current turn to history
    # AI asks the current question
    history_for_ai.append({"role": "model", "parts": [f"Câu hỏi {current_index + 1}: {current_question}"]})
    # User provides the current answer
    history_for_ai.append({"role": "user", "parts": [user_answer]})


    feedback_and_next_prompt = f"""
Bạn là chuyên gia phỏng vấn. Dựa trên lịch sử phỏng vấn và câu trả lời gần nhất của ứng viên ("{user_answer}") cho câu hỏi ("{current_question}"), hãy:
1. Đánh giá câu trả lời: Cung cấp phản hồi ngắn gọn (khoảng 2-3 dòng) về điểm mạnh, điểm cần cải thiện hoặc mức độ phù hợp. Sử dụng **định dạng đậm** cho các thuật ngữ quan trọng.
2. Chuẩn bị câu hỏi tiếp theo: Nếu đây là câu hỏi thứ {current_index + 1} (trong tổng số {MAX_QUESTIONS} câu), hãy tạo câu hỏi thứ {current_index + 2} (nếu chưa đủ {MAX_QUESTIONS} câu) về chủ đề "{topic}", dựa trên câu trả lời vừa rồi hoặc một khía cạnh khác của chủ đề. Sử dụng **định dạng đậm** cho các thuật ngữ quan trọng.
3. Định dạng phản hồi của bạn theo cấu trúc sau (sử dụng dấu phân cách rõ ràng):
---FEEDBACK---
[Phản hồi đánh giá câu trả lời ở đây]
---NEXT_QUESTION---
[Câu hỏi tiếp theo ở đây, hoặc thông báo "END_INTERVIEW" nếu đã đủ 10 câu]
---SCORE_HINT---
[Gợi ý ngắn gọn (1-2 từ) về mức độ đánh giá cho câu trả lời này (ví dụ: "Good", "OK", "Needs Improvement"). Dùng tiếng Anh để dễ xử lý hơn. Đừng giải thích.]
"""

    ai_response_text = generate_ai_response(feedback_and_next_prompt, history=history_for_ai)

    if "Đã xảy ra lỗi" in ai_response_text or "không thể tạo phản hồi" in ai_response_text or "bị chặn" in ai_response_text:
         interview_state["active"] = False # Deactivate if AI fails
         return jsonify({"error": ai_response_text}), 500


    # Parse AI response
    feedback = "Không có phản hồi từ AI."
    next_question = "END_INTERVIEW"
    score_hint = "Neutral" # Default hint

    parts = ai_response_text.split("---")
    parsed_feedback = "Không có phản hồi từ AI."
    parsed_next_question = "END_INTERVIEW"
    parsed_score_hint = "Neutral"

    try:
        # Clean up parts and map to variables
        part_map = {}
        current_key = None
        current_value_lines = []

        for part in parts:
            part = part.strip()
            if part in ["FEEDBACK", "NEXT_QUESTION", "SCORE_HINT"]:
                if current_key is not None:
                    part_map[current_key] = "\n".join(current_value_lines).strip()
                current_key = part
                current_value_lines = []
            elif current_key is not None:
                current_value_lines.append(part)

        # Capture the last part
        if current_key is not None:
             part_map[current_key] = "\n".join(current_value_lines).strip()

        parsed_feedback = part_map.get("FEEDBACK", parsed_feedback)
        parsed_next_question = part_map.get("NEXT_QUESTION", parsed_next_question)
        parsed_score_hint = part_map.get("SCORE_HINT", parsed_score_hint)

    except Exception as e:
        print(f"Error parsing AI response format: {e}")
        print("AI response text:", ai_response_text)
        # Fallback - try to extract parts less strictly if parse fails
        feedback_start = ai_response_text.find("---FEEDBACK---")
        next_q_start = ai_response_text.find("---NEXT_QUESTION---")
        score_start = ai_response_text.find("---SCORE_HINT---")

        if feedback_start != -1:
             feedback_end = next_q_start if next_q_start != -1 else (score_start if score_start != -1 else len(ai_response_text))
             parsed_feedback = ai_response_text[feedback_start + len("---FEEDBACK---"):feedback_end].strip()

        if next_q_start != -1:
             next_q_end = score_start if score_start != -1 else len(ai_response_text)
             parsed_next_question = ai_response_text[next_q_start + len("---NEXT_QUESTION---"):next_q_end].strip()

        if score_start != -1:
             parsed_score_hint = ai_response_text[score_start + len("---SCORE_HINT---"):].strip()

        # If even fallback parsing fails, use error message
        if "---FEEDBACK---" not in ai_response_text: # Simple check for basic structure
             parsed_feedback = f"Lỗi xử lý phản hồi từ AI: {e}. Phản hồi gốc:\n{ai_response_text}"
             parsed_next_question = "END_INTERVIEW" # Force end on severe parse error
             parsed_score_hint = "Error"


    # Use parsed values
    feedback = parsed_feedback
    next_question = parsed_next_question
    score_hint = parsed_score_hint


    interview_state["feedback"].append(feedback)

    # Simple scoring based on hint (adjust points as needed)
    lower_score_hint = score_hint.lower()
    if "good" in lower_score_hint or "excellent" in lower_score_hint or "strong" in lower_score_hint:
        interview_state["score"] += 10
    elif "ok" in lower_score_hint or "average" in lower_score_hint or "decent" in lower_score_hint:
        interview_state["score"] += 7
    elif "improvement" in lower_score_hint or "weak" in lower_score_hint or "needs work" in lower_score_hint:
        interview_state["score"] += 3
    elif "partial" in lower_score_hint:
        interview_state["score"] += 5
     # Award some points even for empty answers if feedback is neutral/OK (optional logic)
    elif user_answer.strip() == "" and ("neutral" in lower_score_hint or "ok" in lower_score_hint):
         interview_state["score"] += 1 # Small penalty for no answer
    # Add more scoring logic if needed for other hints
    # Handle 'Error' hint: no points added, potentially subtract?
    elif "error" in lower_score_hint:
         pass # Don't add points for errors


    response_data = {
        "feedback": feedback,
        "question_number": current_index + 1, # This is the number of the question just answered
        "total_questions": MAX_QUESTIONS,
        "score_hint": score_hint # Optional: send hint to frontend
    }

    interview_state["current_question_index"] += 1

    # Check if it's time to finish based on index or AI signal
    if interview_state["current_question_index"] >= MAX_QUESTIONS or next_question.strip().upper() == "END_INTERVIEW":
        # --- Generate Final Score ---
        final_score_prompt = f"""
        Bạn là chuyên gia đánh giá kết quả phỏng vấn. Dựa trên chủ đề "{topic}" và toàn bộ lịch sử phỏng vấn (có sẵn trong bộ nhớ của bạn từ cuộc trò chuyện này), hãy cung cấp:
        1. Một đánh giá tổng quan ngắn gọn (khoảng 3-5 dòng) về hiệu suất của ứng viên trong suốt cuộc phỏng vấn. Sử dụng **định dạng đậm** cho các điểm nổi bật.
        2. Một điểm số cuối cùng. Thang điểm tùy ý bạn (ví dụ: X/100, A-F, Pass/Fail), nhưng phải có con số hoặc ký hiệu rõ ràng thể hiện mức độ.
        3. Định dạng kết quả theo cấu trúc:
        ---SUMMARY---
        [Đánh giá tổng quan ở đây]
        ---FINAL_SCORE---
        [Điểm số cuối cùng (chỉ con số hoặc chuỗi điểm - VD: 75/100, B+, Pass)]
        """
        # We don't pass history here again explicitly in the prompt body,
        # as the AI should retain history in the chat session.
        final_evaluation_text = generate_ai_response(final_score_prompt, history=history_for_ai) # Pass full history


        summary = "Không có tóm tắt từ AI."
        final_score_str = f"{interview_state['score']}/?" # Fallback using internal score

        parts = final_evaluation_text.split("---")
        parsed_summary = "Không có tóm tắt từ AI."
        parsed_final_score = f"{interview_state['score']}/?"

        try:
             # Clean up parts and map to variables
             part_map = {}
             current_key = None
             current_value_lines = []

             for part in parts:
                 part = part.strip()
                 if part in ["SUMMARY", "FINAL_SCORE"]:
                     if current_key is not None:
                         part_map[current_key] = "\n".join(current_value_lines).strip()
                     current_key = part
                     current_value_lines = []
                 elif current_key is not None:
                     current_value_lines.append(part)

             # Capture the last part
             if current_key is not None:
                  part_map[current_key] = "\n".join(current_value_lines).strip()

             parsed_summary = part_map.get("SUMMARY", parsed_summary)
             parsed_final_score = part_map.get("FINAL_SCORE", parsed_final_score)

        except Exception as e:
             print(f"Error parsing final evaluation: {e}")
             print("Final evaluation text:", final_evaluation_text)
             # Fallback - try basic extraction
             summary_start = final_evaluation_text.find("---SUMMARY---")
             score_start = final_evaluation_text.find("---FINAL_SCORE---")

             if summary_start != -1:
                 summary_end = score_start if score_start != -1 else len(final_evaluation_text)
                 parsed_summary = final_evaluation_text[summary_start + len("---SUMMARY---"):summary_end].strip()

             if score_start != -1:
                 parsed_final_score = final_evaluation_text[score_start + len("---FINAL_SCORE---"):].strip()

             if "---SUMMARY---" not in final_evaluation_text: # Basic check
                 parsed_summary = f"Lỗi xử lý kết quả cuối cùng từ AI: {e}.\nPhản hồi gốc:\n{final_evaluation_text}"


        summary = parsed_summary
        final_score_str = final_score_str # Use AI generated score string (or fallback)


        response_data["status"] = "finished"
        response_data["final_summary"] = summary
        response_data["final_score"] = final_score_str # Use AI generated score string

        # Reset state after finishing
        interview_state["active"] = False

    else:
        # Continue, add the generated question to state
        interview_state["questions"].append(next_question)
        response_data["next_question"] = next_question
        response_data["status"] = "continue"


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
    # Request Markdown formatting in the prompt
    research_prompt = f"""
    Bạn là một nhà nghiên cứu chuyên nghiệp. Hãy tổng hợp thông tin và tạo một báo cáo chi tiết (khoảng 300-500 từ) về chủ đề "{topic}". Báo cáo cần bao gồm các điểm chính, ứng dụng (nếu có), thách thức hoặc xu hướng liên quan. Trình bày báo cáo một cách rõ ràng, có cấu trúc, sử dụng các định dạng Markdown như **đậm**, *nghiêng*, dấu gạch đầu dòng (-) cho danh sách, và code block (```) nếu cần cho ví dụ kỹ thuật. Chỉ trả về nội dung báo cáo, không có lời giới thiệu "Đây là báo cáo của bạn" hay kết thúc.
    """

    research_report = generate_ai_response(research_prompt)

    if "Đã xảy ra lỗi" in research_report or "không thể tạo phản hồi" in research_report or "bị chặn" in research_report:
         return jsonify({"error": research_report}), 500

    return jsonify({"report": research_report})

if __name__ == '__main__':
    # Chạy Flask server
    # host='0.0.0.0' để có thể truy cập từ mạng nội bộ
    # debug=True để tự động load lại khi code thay đổi (chỉ dùng khi phát triển)
    app.run(debug=True, host='0.0.0.0', port=5000)