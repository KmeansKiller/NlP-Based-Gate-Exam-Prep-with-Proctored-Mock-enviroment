document.addEventListener('DOMContentLoaded', function () {
    // --- Configuration & Element Selection ---
    const timerElement = document.getElementById('timer');
    const video = document.getElementById('webcam');
    const proctorStatus = document.getElementById('proctorStatus');
    const examForm = document.getElementById('examForm'); // Get the form
    const sessionIdInput = examForm ? examForm.querySelector('input[name="session_id"]') : null; // Find session ID input within the form
    const proctoringUrl = '/record_proctor_event/'; // URL for proctoring AJAX endpoint
    const initialTime = 3600; // 60 minutes * 60 seconds (adjust as needed)
    const proctoringIntervalSeconds = 15; // How often to send proctoring data (in seconds)

    // --- State Variables ---
    let timeLeft = initialTime;
    let proctoringIntervalId = null; // To store the interval ID for stopping later
    let prevFrameData = null; // Store previous frame for movement detection
    let isSubmitting = false; // Flag to prevent multiple submissions
    let timerIntervalId = null; // To store the timer interval ID

    // --- Helper Functions ---

    /**
     * Gets a cookie value by name.
     * @param {string} name - The name of the cookie.
     * @returns {string|null} The cookie value or null if not found.
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Updates the proctoring status message and style.
     * @param {string} message - The message to display.
     * @param {'success'|'warning'|'danger'|'info'} type - The type of message (affects color).
     */
    function updateProctorStatus(message, type = 'info') {
        if (!proctorStatus) return; // Element might not exist on all pages
        proctorStatus.textContent = message;
        proctorStatus.className = 'mt-2 fw-bold'; // Reset base classes
        switch (type) {
            case 'success':
                proctorStatus.classList.add('text-success'); // Green
                break;
            case 'warning':
                proctorStatus.classList.add('text-warning'); // Orange
                break;
            case 'danger':
                proctorStatus.classList.add('text-danger');  // Red
                break;
            case 'info':
            default:
                proctorStatus.classList.add('text-info');   // Blue
                break;
        }
    }

    // --- Timer Function ---
    function updateTimer() {
        if (timeLeft <= 0) {
            if (timerElement) {
                timerElement.textContent = 'Time Up!';
                timerElement.classList.remove('alert-info', 'alert-success', 'alert-warning'); // Remove other alerts
                timerElement.classList.add('alert-danger');
            }
            stopProctoring(); // Stop sending data when time is up
            stopTimer(); // Stop the timer interval

            // Optional: Auto-submit the form if it exists and hasn't been submitted
            if (examForm && !isSubmitting) {
                console.log("Time's up! Submitting form."); //
                isSubmitting = true;
                examForm.submit();
            }
            return;
        }

        let minutes = Math.floor(timeLeft / 60);
        let seconds = timeLeft % 60;
        if (timerElement) {
            timerElement.textContent = `Time Left: ${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
            // Optional: Change color based on time remaining
            if (timeLeft < 300) { // Less than 5 minutes
                timerElement.classList.remove('alert-info', 'alert-success');
                timerElement.classList.add('alert-warning');
            }
        }
        timeLeft--;
    }

    function startTimer() {
       if (timerElement && !timerIntervalId) {
           updateTimer(); // Initial display
           timerIntervalId = setInterval(updateTimer, 1000); // Update every second
       }
    }

    function stopTimer() {
        if (timerIntervalId) {
            clearInterval(timerIntervalId);
            timerIntervalId = null;
        }
    }


    // --- Webcam and Proctoring Logic ---

    /**
     * Captures a frame from the webcam, sends it for analysis, and updates status.
     */
    function captureAndSendFrame() {
        if (!video || !video.srcObject || !video.videoWidth || !video.videoHeight || !sessionIdInput || !sessionIdInput.value || isSubmitting) {
            console.log("Proctoring prerequisites not met (video stream/session ID/already submitted)."); //
            // Optionally update status or stop proctoring if session ID is missing
            // updateProctorStatus("Proctoring Error: Missing Session ID", "danger");
            // stopProctoring(); // Consider stopping if prerequisites fail permanently
            return;
        }

        let canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        let ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        // Use JPEG with moderate compression to reduce data size
        let frameData = canvas.toDataURL('image/jpeg', 0.7);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', proctoringUrl, true);
        xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
        const csrftoken = getCookie('csrftoken'); // Ensure CSRF token is available

        if (csrftoken) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        } else {
            console.warn("CSRF token not found. Proctoring request might fail."); //
            updateProctorStatus("Proctoring Error: Config Issue", "danger");
            // Maybe stop proctoring if CSRF token is essential and missing
            // stopProctoring();
            return;
        }

        xhr.onload = function () {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.status === 'success' && response.ai_result) {
                        let issues = [];
                        const aiResult = response.ai_result;
                        // Use .get for safer access in case keys are missing
                        // Javascript equivalent: check if key exists before accessing or use || default
                        if (aiResult.face_match === false) issues.push("Face mismatch");

                        const detectedObjects = aiResult.objects || []; // Default to empty array if missing
                        if (Array.isArray(detectedObjects)) { // Check if it's an array
                             if (detectedObjects.includes("cell phone")) issues.push("Phone detected");
                             // Check specifically for 'person' count > 1
                             if (detectedObjects.filter(obj => obj === 'person').length > 1) {
                                  issues.push("Multiple people detected");
                             }
                        } else {
                             console.warn("Unexpected format for detected objects:", detectedObjects); //
                        }

                        if ((aiResult.movement || 'normal') === 'suspicious') issues.push("Suspicious movement");

                        if (issues.length > 0) {
                            updateProctorStatus(`Proctoring Alert: ${issues.join(', ')}`, 'danger');
                        } else {
                            updateProctorStatus("Proctoring: OK", 'success');
                        }
                    } else if (response.status === 'success') {
                         updateProctorStatus("Proctoring check completed.", 'success'); // No specific AI results to parse
                    } else {
                        // Handle cases where status might not be 'success' but request was 200 OK
                        console.warn("Proctoring request successful but status indicates failure:", response); //
                        updateProctorStatus(`Proctoring Status: ${response.error || 'Unknown issue'}`, 'warning');
                    }
                } catch (e) {
                    console.error("Error parsing proctoring response:", e, xhr.responseText); //
                    updateProctorStatus("Proctoring Status: Error processing response.", 'warning'); // Match user's error
                }
            } else {
                console.error("Proctoring AJAX error:", xhr.status, xhr.statusText, xhr.responseText); //
                 // Provide more specific error messages if possible
                 let errorMsg = `Proctoring Status: Error (${xhr.status})`;
                 if (xhr.status === 404) errorMsg = "Proctoring Status: Endpoint not found (404).";
                 if (xhr.status === 403) errorMsg = "Proctoring Status: Forbidden (403). Check login/CSRF.";
                 if (xhr.status >= 500) errorMsg = "Proctoring Status: Server Error (5xx).";
                updateProctorStatus(errorMsg, 'danger');
                // Consider stopping proctoring on persistent errors (e.g., 403, 404)
                // if (xhr.status === 403 || xhr.status === 404) { stopProctoring(); }
            }
        };

        xhr.onerror = function() {
            console.error("Proctoring AJAX request failed (Network Error)."); //
            updateProctorStatus("Proctoring Status: Network Error.", 'danger');
            // Consider adding retry logic here if needed, or stopping after multiple failures
        };

        // Include previous frame data if available
        const sessionId = sessionIdInput.value; // Get current session ID value
        // Ensure frameData is properly encoded
        const encodedFrameData = encodeURIComponent(frameData);
        let params = `session_id=${sessionId}&frame_data=${encodedFrameData}`;

        if (prevFrameData) {
            params += `&prev_frame_data=${encodeURIComponent(prevFrameData)}`;
        }

        xhr.send(params);

        prevFrameData = frameData; // Update previous frame for the next cycle
    }

    /**
     * Starts the proctoring process (webcam access and interval).
     */
    function startProctoring() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            updateProctorStatus("Webcam not supported by this browser.", 'warning');
            return;
        }
        if (!video) {
             updateProctorStatus("Webcam element not found.", 'danger');
             return;
        }
        if (!sessionIdInput || !sessionIdInput.value) {
            updateProctorStatus("Proctoring disabled: Session ID missing.", 'danger');
            return; // Don't start without session ID
        }

        navigator.mediaDevices.getUserMedia({ video: true })
            .then(function (stream) {
                video.srcObject = stream;
                video.onloadedmetadata = () => {
                    video.play(); // Ensure video plays
                    updateProctorStatus("Proctoring Initializing...", 'info'); // Initial status

                    // Start proctoring loop only after video is ready and session ID is confirmed
                    if (!proctoringIntervalId && sessionIdInput.value) {
                         // Initial check after a short delay to ensure rendering and analysis setup
                        setTimeout(captureAndSendFrame, 2500); // Increased delay slightly
                         // Regular checks
                        proctoringIntervalId = setInterval(captureAndSendFrame, proctoringIntervalSeconds * 1000);
                        console.log("Proctoring interval started."); //
                    }
                };
                 video.onerror = (e) => {
                     console.error("Error occurred with video stream:", e); //
                     updateProctorStatus("Webcam Error.", 'danger');
                     stopProctoring();
                 };
            })
            .catch(function (error) {
                console.error("Webcam access error:", error); //
                if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                     updateProctorStatus("Webcam Access Denied. Proctoring disabled.", 'danger');
                } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                     updateProctorStatus("No webcam found. Proctoring disabled.", 'danger');
                }
                 else {
                     updateProctorStatus(`Webcam Access Error (${error.name}). Proctoring disabled.`, 'danger');
                }
                // No need to call stopProctoring() here as the interval wouldn't have started
            });
    }

     /**
      * Stops the proctoring interval and releases the webcam.
      */
    function stopProctoring() {
        // Stop the interval
        if (proctoringIntervalId) {
            clearInterval(proctoringIntervalId);
            proctoringIntervalId = null;
            console.log("Proctoring interval stopped."); //
        }
        // Stop the webcam stream
        if (video && video.srcObject) {
             video.srcObject.getTracks().forEach(track => track.stop());
             video.srcObject = null;
             console.log("Webcam stream released."); //
             // Optionally update status when explicitly stopped
             // updateProctorStatus("Proctoring Stopped.", 'info');
        }
        // Reset previous frame data
        prevFrameData = null;
    }

    // --- Initialization ---
    startTimer(); // Start the exam timer

    // Start proctoring only if elements are present
    if (video && proctorStatus && sessionIdInput) {
        startProctoring();
    } else {
        console.log("Required elements for proctoring not found on this page."); //
        if(proctorStatus) updateProctorStatus("Proctoring disabled (missing elements).", "warning");
    }

    // --- Event Listeners ---
    // Stop proctoring and timer when form is submitted manually
    if (examForm) {
        examForm.addEventListener('submit', function(e) {
             // Check if already submitting to prevent double submissions
             if (isSubmitting) {
                 e.preventDefault(); // Prevent form submission again
                 console.log("Submission already in progress."); //
                 return;
             }
             // Confirmation dialog before submitting
             const confirmed = confirm("Are you sure you want to submit the exam?");
             if (confirmed) {
                 console.log("Form submitted manually."); //
                 isSubmitting = true; // Set flag immediately
                 stopTimer(); // Stop timer on submit
                 stopProctoring(); // Stop webcam and interval on submit
                 // Allow the form submission to proceed naturally
             } else {
                  e.preventDefault(); // Prevent form submission if cancelled
                  console.log("Exam submission cancelled by user."); //
             }
        });
    }

     // Stop proctoring and timer if the user navigates away or closes the tab/window
     window.addEventListener('beforeunload', (event) => {
         // This event fires just before the page unloads.
         // We can't reliably prevent navigation, but we can stop processes.
         if (!isSubmitting) { // Only stop if not already submitted
              console.log("Page unloading, stopping timer and proctoring."); //
              stopTimer();
              stopProctoring();
              // Note: You cannot reliably auto-submit here. The form submission
              // might be interrupted by the page closing. Time-up submission is safer.
         }
          // Standard practice for beforeunload to show a generic browser confirmation
          // event.preventDefault(); // Not always reliable
          // event.returnValue = ''; // Legacy method
     });

}); // End DOMContentLoaded