// script.js remains the same as the previous version (without particles.js)

document.addEventListener('DOMContentLoaded', () => {
    const agentButtons = document.querySelectorAll('.agent-button');
    const interviewSection = document.getElementById('interview-section');
    const researchSection = document.getElementById('research-section');
    const interviewSetup = interviewSection.querySelector('.interview-setup');
    const interviewActive = interviewSection.querySelector('.interview-active');
    const researchSetup = researchSection.querySelector('.research-setup');
    const researchResult = researchSection.querySelector('#research-result');

    const interviewTopicSelect = document.getElementById('interview-topic');
    const customTopicInput = document.getElementById('custom-topic');
    const startInterviewBtn = document.getElementById('start-interview-btn');
    const questionCount = document.getElementById('question-count');
    const progressBarFill = interviewActive.querySelector('.progress-fill');
    const interviewLog = document.getElementById('interview-log');
    const userAnswerTextarea = document.getElementById('user-answer');
    const submitAnswerBtn = document.getElementById('submit-answer-btn');
    const interviewResultDiv = document.getElementById('interview-result');
    const finalSummaryDiv = document.getElementById('final-summary');
    const finalScoreDiv = document.getElementById('final-score');

    const researchTopicInput = document.getElementById('research-topic');
    const startResearchBtn = document.getElementById('start-research-btn');
    const researchReportContentDiv = document.getElementById('research-report-content');
    const researchLoadingIndicator = researchResult.querySelector('.loading-indicator');

    const errorMessageDiv = document.getElementById('error-message');
    const errorTextSpan = document.getElementById('error-text');

    const BACKEND_URL = 'http://127.0.0.1:5000'; // Thay đổi nếu backend chạy ở host/port khác

    let currentQuestionNumber = 0;
    let totalQuestions = 10;
    let messageIndex = 0; // Counter for message animation delay

    // --- Helper Functions ---
    function showSection(sectionElement) {
        document.querySelectorAll('.agent-section').forEach(sec => sec.classList.add('hidden'));
        sectionElement.classList.remove('hidden');
    }

    function showLoading(isLoading, section) {
        if (section === 'research') {
            researchLoadingIndicator.classList.toggle('hidden', !isLoading);
            startResearchBtn.disabled = isLoading;
            researchTopicInput.disabled = isLoading;
        } else if (section === 'interview') {
             startInterviewBtn.disabled = isLoading;
             submitAnswerBtn.disabled = isLoading;
             userAnswerTextarea.disabled = isLoading;
        }
    }

     function displayError(message) {
         errorTextSpan.textContent = message;
         errorMessageDiv.classList.remove('hidden');
     }

     function hideError() {
         errorMessageDiv.classList.add('hidden');
     }

    // Function to render Markdown (especially bold) for chat messages
    // Using marked.js: parseInline for chat messages, parse for block content (like reports)
    function renderMarkdown(text, inline = true) {
         if (!text) return '';
         // Replace newline characters with <br> *before* markdown parsing for chat messages
         // Marked.js 'parse' handles paragraphs, but 'parseInline' doesn't naturally
         // handle explicit newlines the way we want for chat bubbles.
         // We keep <br> replacement for consistency in appendMessageToLog.
         let html = inline ? marked.parseInline(text) : marked.parse(text);
         if (inline) {
             // marked.parseInline might wrap in <p> for bold, remove that
             html = html.replace(/^<p>([\s\S]*)<\/p>$/, '$1');
             // Add back br tags for explicit newlines in chat (AFTER marked parsing)
             html = html.replace(/\n/g, '<br>');
         }
         return html;
    }


    function appendMessageToLog(type, content) {
         const messageDiv = document.createElement('div');
         messageDiv.classList.add(`chat-${type}`);
         // Add a custom property for animation delay
         messageDiv.style.setProperty('--message-index', messageIndex++);
         // Use renderMarkdown to display content
         messageDiv.innerHTML = `<p>${renderMarkdown(content, true)}</p>`; // Use inline rendering for chat

         interviewLog.appendChild(messageDiv);

         // Manually trigger reflow and set initial state before animation
         void messageDiv.offsetWidth;
         messageDiv.style.opacity = 0;
         messageDiv.style.transform = 'translateY(10px)';


         // Auto-scroll to the latest message after a small delay
         setTimeout(() => {
             interviewLog.scrollTop = interviewLog.scrollHeight;
         }, 100); // Delay scroll slightly to allow message to appear

    }

    function updateProgress(current, total) {
        const percentage = (current / total) * 100;
        progressBarFill.style.width = `${percentage}%`;
        questionCount.textContent = `Câu hỏi: ${current}/${total}`;
    }

    // --- Event Listeners ---
    agentButtons.forEach(button => {
        button.addEventListener('click', () => {
            const agentType = button.dataset.agent;
            hideError(); // Hide error on section switch
            // Update active button class
            agentButtons.forEach(btn => btn.classList.remove('active-mode-button'));
            button.classList.add('active-mode-button');

            if (agentType === 'interview') {
                showSection(interviewSection);
                // Reset interview view
                interviewSetup.classList.remove('hidden');
                interviewActive.classList.add('hidden'); // Keep active section hidden initially until start button is pressed
                 interviewResultDiv.classList.add('hidden');
                 interviewLog.innerHTML = ''; // Clear previous chat
                 userAnswerTextarea.value = '';
                 submitAnswerBtn.classList.remove('hidden');
                 userAnswerTextarea.classList.remove('hidden');
                 interviewActive.querySelector('.user-input-area').classList.remove('hidden');
                 currentQuestionNumber = 0;
                 messageIndex = 0; // Reset message index for animation
                 updateProgress(0, totalQuestions); // Reset progress


            } else if (agentType === 'research') {
                showSection(researchSection);
                // Reset research view
                 researchSetup.classList.remove('hidden');
                 researchResult.classList.add('hidden');
                 researchReportContentDiv.innerHTML = '';
                 researchTopicInput.value = '';
            }
        });
    });

    interviewTopicSelect.addEventListener('change', (event) => {
        if (event.target.value === 'Nhập chủ đề khác') {
            customTopicInput.classList.remove('hidden');
            customTopicInput.focus();
        } else {
            customTopicInput.classList.add('hidden');
            customTopicInput.value = '';
        }
    });


    startInterviewBtn.addEventListener('click', async () => {
        let selectedTopic = interviewTopicSelect.value;
        if (selectedTopic === 'Nhập chủ đề khác') {
            selectedTopic = customTopicInput.value.trim();
        }

        if (!selectedTopic) {
            displayError('Vui lòng chọn hoặc nhập chủ đề phỏng vấn.');
            return;
        }

        hideError();
        showLoading(true, 'interview');
        interviewLog.innerHTML = ''; // Clear log for new interview
        messageIndex = 0; // Reset message index

        try {
            const response = await fetch(`${BACKEND_URL}/interview/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ topic: selectedTopic }),
            });

            const data = await response.json();

            if (response.ok) {
                interviewSetup.classList.add('hidden');
                interviewActive.classList.remove('hidden'); // Now show active section
                interviewResultDiv.classList.add('hidden');
                submitAnswerBtn.classList.remove('hidden');
                userAnswerTextarea.classList.remove('hidden');
                 interviewActive.querySelector('.user-input-area').classList.remove('hidden');


                currentQuestionNumber = data.question_number;
                totalQuestions = data.total_questions;
                updateProgress(currentQuestionNumber, totalQuestions);
                appendMessageToLog('question', `Câu hỏi ${currentQuestionNumber}: ${data.question}`);
            } else {
                 displayError(`Lỗi bắt đầu phỏng vấn: ${data.error || response.statusText}`);
                 // Revert to setup if start fails
                 interviewSetup.classList.remove('hidden');
                 interviewActive.classList.add('hidden');
            }
        } catch (error) {
            console.error('Error starting interview:', error);
            displayError(`Lỗi kết nối đến server: ${error.message}`);
             // Revert to setup if start fails
             interviewSetup.classList.remove('hidden');
             interviewActive.classList.add('hidden');
        } finally {
            showLoading(false, 'interview');
        }
    });

    submitAnswerBtn.addEventListener('click', async () => {
        const userAnswer = userAnswerTextarea.value.trim();
        if (!userAnswer) {
            displayError('Vui lòng nhập câu trả lời của bạn.');
            return;
        }

        hideError();
        appendMessageToLog('answer', userAnswer);
        userAnswerTextarea.value = ''; // Clear input after sending
        showLoading(true, 'interview');
        // Disable input area temporarily
        userAnswerTextarea.disabled = true;
        submitAnswerBtn.disabled = true;


        try {
            const response = await fetch(`${BACKEND_URL}/interview/answer`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ answer: userAnswer }),
            });

            const data = await response.json();

            if (response.ok) {
                // Add feedback first
                appendMessageToLog('feedback', `Phản hồi: ${data.feedback}`);

                if (data.status === 'continue') {
                    currentQuestionNumber++;
                    updateProgress(currentQuestionNumber, totalQuestions);
                    // Add next question after a slight delay to improve chat flow feel
                    setTimeout(() => {
                         appendMessageToLog('question', `Câu hỏi ${currentQuestionNumber}: ${data.next_question}`);
                         // Re-enable input area after receiving next question
                         userAnswerTextarea.disabled = false;
                         submitAnswerBtn.disabled = false;
                         userAnswerTextarea.focus(); // Focus textarea
                    }, 500); // 500ms delay
                } else if (data.status === 'finished') {
                    updateProgress(totalQuestions, totalQuestions); // Complete progress bar
                    questionCount.textContent = "Phỏng vấn hoàn thành!"; // Update text
                    submitAnswerBtn.classList.add('hidden'); // Hide submit button
                    userAnswerTextarea.classList.add('hidden'); // Hide textarea
                    interviewActive.querySelector('.user-input-area').classList.add('hidden'); // Hide input area


                    interviewResultDiv.classList.remove('hidden');
                    // Render summary with Markdown
                    finalSummaryDiv.innerHTML = `<strong>Tóm tắt:</strong> ${renderMarkdown(data.final_summary, false)}`; // Use block rendering for summary
                    finalScoreDiv.innerHTML = `<strong>Điểm số cuối cùng:</strong> <span class="final-score-value">${data.final_score}</span>`;

                }
            } else {
                displayError(`Lỗi xử lý câu trả lời: ${data.error || response.statusText}`);
                 // Keep disabled on critical error
                 // submitAnswerBtn.disabled = true; // Already done before fetch
                 // userAnswerTextarea.disabled = true; // Already done before fetch
            }
        } catch (error) {
            console.error('Error submitting answer:', error);
            displayError(`Lỗi kết nối đến server: ${error.message}`);
            // Keep disabled on connection error
            // submitAnswerBtn.disabled = true; // Already done before fetch
            // userAnswerTextarea.disabled = true; // Already done before fetch
        } finally {
            // showLoading(false, 'interview'); // Loading hidden here as inputs might stay disabled on error
             if (data && data.status !== 'continue') { // Only hide loading if not waiting for next question
                  showLoading(false, 'interview');
             }
             // If error occurred, inputs remain disabled, loading stays hidden by displayError logic
        }
    });


    startResearchBtn.addEventListener('click', async () => {
        const researchTopic = researchTopicInput.value.trim();
        if (!researchTopic) {
            displayError('Vui lòng nhập chủ đề nghiên cứu.');
            return;
        }

        hideError();
        researchResult.classList.remove('hidden'); // Show result area
        researchReportContentDiv.innerHTML = ''; // Clear previous report
        showLoading(true, 'research');


        try {
            const response = await fetch(`${BACKEND_URL}/research`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ topic: researchTopic }),
            });

            const data = await response.json();

            if (response.ok) {
                // Render report with Markdown
                researchReportContentDiv.innerHTML = renderMarkdown(data.report, false); // Use block rendering for report
                researchReportContentDiv.style.color = 'var(--text-color)'; // Reset color in case of previous error
            } else {
                 researchReportContentDiv.innerHTML = `Không thể tạo báo cáo. ${renderMarkdown(data.error || response.statusText, false)}`; // Render error report with Markdown
                 researchReportContentDiv.style.color = 'var(--error-color)'; // Indicate error visually
                 displayError(`Lỗi nghiên cứu: ${data.error || response.statusText}`);
            }
        } catch (error) {
            console.error('Error performing research:', error);
             researchReportContentContentDiv.innerHTML = `Đã xảy ra lỗi kết nối. ${renderMarkdown(error.message, false)}`; // Render error report with Markdown
             researchReportContentDiv.style.color = 'var(--error-color)'; // Indicate error visually
            displayError(`Lỗi kết nối đến server: ${error.message}`);
        } finally {
            showLoading(false, 'research');
        }
    });

    // --- Add Enter key listeners ---

    // Interview answer textarea: Enter sends, Shift+Enter is newline
    userAnswerTextarea.addEventListener('keydown', (event) => {
        // Check if Enter key is pressed AND Shift key is NOT pressed
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent default newline
            submitAnswerBtn.click(); // Trigger button click
        }
    });

    // Research topic input: Enter triggers search
    researchTopicInput.addEventListener('keydown', (event) => {
        // Check if Enter key is pressed
        if (event.key === 'Enter') {
            event.preventDefault(); // Prevent default (e.g., form submission if applicable)
            startResearchBtn.click(); // Trigger button click
        }
    });


    // Initial state: Show agent selection, hide sections
    document.querySelectorAll('.agent-section').forEach(sec => sec.classList.add('hidden'));
    // Initially activate the first button or none, depending on desired default
     // Let's add active class to the first button by default
    if (agentButtons.length > 0) {
         agentButtons[0].classList.add('active-mode-button');
         // Optionally, simulate click on first button to show its section by default
         // agentButtons[0].click(); // Uncomment if you want a section to show immediately
    }


});