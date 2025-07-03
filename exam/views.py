# exam/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.core.files.base import ContentFile # For handling base64 image
from django.conf import settings # To get API Key
from django.db import IntegrityError # For catching database errors
import base64
import requests # For API calls
import re # Keep for chatbot
import random # Keep for chatbot
import traceback # <--- IMPORT ADDED HERE

from .models import (
    Question, ExamSession, CandidateAnswer, ProctorLog, CandidateProfile,
    Note, PreviousQuestionPaper # Ensure all models are imported
)
# Import process_proctoring, but handle potential errors during its execution
from .proctoring import process_proctoring

# --- Helper function to handle Base64 image data ---
def decode_base64_file(data):
    # print("[DEBUG] Attempting to decode base64 image...") # Debug print
    if not data or ';base64,' not in data:
        # print("[DEBUG] Invalid base64 data format.") # Debug print
        return None
    try:
        format, imgstr = data.split(';base64,')
        ext = format.split('/')[-1]
        decoded_content = base64.b64decode(imgstr)
        # print(f"[DEBUG] Decoded image, extension: {ext}, size: {len(decoded_content)} bytes") # Debug print
        return ContentFile(decoded_content, name=f'captured_face.{ext}')
    except Exception as e:
        print(f"[ERROR] Error decoding base64 image: {e}") # Log error
        print(traceback.format_exc()) # <--- Uses traceback
        return None

# --- Home view ---
def home_view(request):
    return render(request, 'exam/home.html')

# --- Registration View (Modified for OTP Step 1) ---
def register(request):
    if request.method == 'POST':
        # --- Get all form data ---
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        email = request.POST.get('email', '')
        phone_number = request.POST.get('phone_number') # Get phone number
        face_data_file = request.FILES.get('face_data')
        face_data_capture = request.POST.get('face_data_capture') # Hidden input for captured image

        # --- Basic Validation ---
        if not all([username, password, email, phone_number]):
             return render(request, 'exam/register.html', {'error': 'Please fill all required fields.'})

        if User.objects.filter(username=username).exists():
            return render(request, 'exam/register.html', {'error': 'Username already taken.'})

        if User.objects.filter(email=email).exists():
             return render(request, 'exam/register.html', {'error': 'Email already registered.'})

        # Basic phone number format check (adjust regex as needed)
        if not re.match(r'^\+?1?\d{9,15}$', phone_number):
             return render(request, 'exam/register.html', {'error': 'Invalid phone number format.'})

        # --- Process Face Image ---
        processed_face_data = None
        face_data_b64_for_session = None # To store in session if captured
        if face_data_capture:
            processed_face_data = decode_base64_file(face_data_capture)
            face_data_b64_for_session = face_data_capture # Store the raw base64
        elif face_data_file:
            processed_face_data = face_data_file
            # If you need to store uploaded file in session, read and encode it
            # try:
            #     face_data_b64_for_session = base64.b64encode(face_data_file.read()).decode('utf-8')
            #     face_data_file.seek(0) # Reset file pointer if needed elsewhere
            # except Exception as e:
            #     print(f"[ERROR] Could not read uploaded file for session storage: {e}")

        # --- Store registration data temporarily in session ---
        request.session['registration_data'] = {
            'username': username,
            'password': password, # Still consider hashing before user creation later
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone_number': phone_number,
        }
        # Store face data in session if available
        if face_data_b64_for_session:
            request.session['temp_face_b64'] = face_data_b64_for_session
        else:
             request.session.pop('temp_face_b64', None) # Ensure it's clear if no image provided


        # --- Send OTP via 2factor.in ---
        api_key = settings.TWOFACTOR_API_KEY
        if not api_key or api_key == 'YOUR_2FACTOR_API_KEY_HERE':
             return render(request, 'exam/register.html', {'error': 'OTP Service not configured by admin.'})

        try:
            # Note: Ensure phone_number includes country code if required by 2factor
            print(f"[DEBUG] Sending OTP to: {phone_number}") #
            otp_send_url = f"https://2factor.in/API/V1/{api_key}/SMS/{phone_number}/AUTOGEN"
            # Consider adding a timeout to the request
            response = requests.get(otp_send_url, timeout=10) # 10 second timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            result = response.json()
            print(f"[DEBUG] OTP Send Response: {result}") #

            if result.get('Status') == 'Success':
                otp_session_id = result.get('Details')
                request.session['otp_session_id'] = otp_session_id # Store OTP session ID
                print(f"[DEBUG] OTP Sent Successfully. Session ID: {otp_session_id}") #
                return redirect('verify_otp') # Redirect to OTP verification page
            else:
                 error_message = result.get('Details', 'Failed to send OTP.')
                 print(f"[ERROR] Failed to send OTP: {error_message}") #
                 return render(request, 'exam/register.html', {'error': error_message})

        except requests.exceptions.Timeout:
             print("[ERROR] Timeout connecting to OTP service.") #
             return render(request, 'exam/register.html', {'error': 'OTP service timed out. Please try again later.'})
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] OTP API Request Error: {e}") #
            return render(request, 'exam/register.html', {'error': f'Could not connect to OTP service. Please try again later.'})
        except Exception as e:
            print(f"[ERROR] Unexpected error during OTP sending: {e}") #
            print(traceback.format_exc()) # <--- Uses traceback #
            return render(request, 'exam/register.html', {'error': f'An unexpected error occurred: {e}'})

    # GET request
    return render(request, 'exam/register.html')


# --- OTP Verification View (New) ---
def verify_otp(request):
    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        otp_session_id = request.session.get('otp_session_id')
        registration_data = request.session.get('registration_data')
        temp_face_b64 = request.session.get('temp_face_b64')

        print(f"[DEBUG] Verifying OTP. Session ID from session: {otp_session_id}") #
        if not otp_session_id or not registration_data:
            request.session.pop('otp_session_id', None)
            request.session.pop('registration_data', None)
            request.session.pop('temp_face_b64', None)
            print("[ERROR] OTP Session or Registration data missing.") #
            return render(request, 'exam/verify_otp.html', {'error': 'Session expired or invalid. Please register again.'})

        api_key = settings.TWOFACTOR_API_KEY
        if not api_key or api_key == 'YOUR_2FACTOR_API_KEY_HERE':
             return render(request, 'exam/verify_otp.html', {'error': 'OTP Service not configured by admin.'})

        verify_url = f"https://2factor.in/API/V1/{api_key}/SMS/VERIFY/{otp_session_id}/{user_otp}"
        print(f"[DEBUG] Calling OTP Verify URL: {verify_url}") #

        try:
            response = requests.get(verify_url, timeout=10) # 10 second timeout
            response.raise_for_status()
            result = response.json()
            print(f"[DEBUG] OTP Verify Response: {result}") #

            if result.get('Status') == 'Success':
                print("[DEBUG] OTP Verified Successfully.") #
                # --- Check if user already exists ---
                username_to_create = registration_data['username']
                if User.objects.filter(username=username_to_create).exists():
                    print(f"[WARN] User '{username_to_create}' already exists during OTP verification.") #
                    # Clean up session first
                    request.session.pop('otp_session_id', None)
                    request.session.pop('registration_data', None)
                    request.session.pop('temp_face_b64', None)
                    return render(request, 'exam/verify_otp.html', {'error': 'Username already exists. Please login.'})

                # --- User does not exist, proceed with creation ---
                try:
                    print(f"[DEBUG] Creating user: {username_to_create}") #
                    user = User.objects.create_user(
                        username=username_to_create,
                        password=registration_data['password'], # Ensure this is handled securely
                        email=registration_data['email'],
                        first_name=registration_data['first_name'],
                        last_name=registration_data['last_name']
                    )
                    print(f"[DEBUG] User '{user.username}' created.") #

                    print(f"[DEBUG] Creating profile for user '{user.username}'") #
                    profile = CandidateProfile.objects.create(
                        user=user,
                        phone_number=registration_data['phone_number'],
                        is_phone_verified=True,
                    )
                    print(f"[DEBUG] Profile created.") #

                    # Handle face data
                    processed_face_data = None
                    if temp_face_b64:
                        print("[DEBUG] Processing face data from session.") #
                        processed_face_data = decode_base64_file(temp_face_b64)

                    if processed_face_data:
                        print("[DEBUG] Saving face data to profile.") #
                        profile.face_data = processed_face_data
                        profile.save()
                        print("[DEBUG] Face data saved.") #
                    else:
                        print("[DEBUG] No face data found in session to save.") #


                    # Clean up session
                    print("[DEBUG] Clearing registration session data.") #
                    request.session.pop('otp_session_id', None)
                    request.session.pop('registration_data', None)
                    request.session.pop('temp_face_b64', None)

                    # Login the new user
                    print(f"[DEBUG] Logging in user '{user.username}'.") #
                    auth_login(request, user)
                    return redirect('exam')

                except IntegrityError as ie: # Catch specific integrity errors during creation
                     print(f"[ERROR] IntegrityError during user/profile creation: {ie}") #
                     # print(traceback.format_exc()) # <--- Uses traceback
                     return render(request, 'exam/verify_otp.html', {'error': 'Could not create user. Username or email might already exist.'})
                except Exception as inner_e: # Catch other errors during user/profile creation
                     print(f"[ERROR] Exception during user/profile creation: {inner_e}") #
                     print(traceback.format_exc()) # <--- Uses traceback #
                     # Attempt to delete the user if profile creation failed? Requires careful thought.
                     # if 'user' in locals() and user.pk: user.delete()
                     return render(request, 'exam/verify_otp.html', {'error': 'An error occurred creating your profile.'})


            else: # OTP Invalid
                error_detail = result.get('Details', 'Invalid OTP')
                print(f"[ERROR] Invalid OTP entered. Details: {error_detail}") #
                return render(request, 'exam/verify_otp.html', {'error': f"Invalid OTP entered. {error_detail}" })

        except requests.exceptions.Timeout:
             print("[ERROR] Timeout connecting to OTP verification service.") #
             return render(request, 'exam/verify_otp.html', {'error': 'OTP service timed out. Please try again.'})
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] OTP Verification API Request Error: {e}") #
            return render(request, 'exam/verify_otp.html', {'error': 'Could not connect to OTP service.'})
        except Exception as e:
             print(f"[ERROR] Unexpected error during OTP verification logic: {e}") #
             print(traceback.format_exc()) # <--- Uses traceback #
             return render(request, 'exam/verify_otp.html', {'error': 'An unexpected error occurred during verification.'})

    # GET request: show the OTP form
    if not request.session.get('otp_session_id'):
        print("[WARN] Accessing verify_otp page without OTP session ID. Redirecting to register.") #
        return redirect('register')
    print("[DEBUG] Displaying OTP entry form.") #
    return render(request, 'exam/verify_otp.html')


# --- Login view (Keep as is, but ensure profile check is appropriate) ---
def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            # Optional: Check if phone is verified before allowing login
            profile = getattr(user, 'candidateprofile', None)
            # if not profile or not profile.is_phone_verified:
            #     return render(request, 'exam/login.html', {'error': 'Account not fully verified. Please complete registration or contact support.'})

            auth_login(request, user)
            return redirect('exam') # Redirect to exam page after login
        else:
            return render(request, 'exam/login.html', {'error': 'Invalid credentials'})
    return render(request, 'exam/login.html')

# --- Logout view (Keep as is) ---
def logout(request):
    auth_logout(request)
    return redirect('login') # Redirect to login page after logout


# --- Chatbot, Profile, Notes, Papers views (Keep as is) ---
# (Keep the existing functions: get_chatbot_response, chatbot, profile, view_question_papers, notes)
gate_subjects = ['math', 'physics', 'chemistry', 'mechanical', 'electrical', 'civil', 'computer science', 'cs', 'electronics', 'aptitude']
sample_qs_by_subject = {
    'math': ['Q: What is the rank of the matrix [[1, 2], [3, 6]]?', 'Q: Solve the differential equation dy/dx = y.'],
    'physics': ['Q: State Lenz\'s Law.', 'Q: Define escape velocity.'],
    'chemistry': ['Q: What is hybridization?', 'Q: Write the formula for methane.'],
    'computer science': ['Q: Explain Big O notation.', 'Q: What is the difference between TCP and UDP?'],
    'cs': ['Q: Explain Big O notation.', 'Q: What is the difference between TCP and UDP?'], # Alias for CS
    'mechanical': ['Q: Define Thermodynamics first law.', 'Q: What is stress vs strain?'],
    'electrical': ['Q: Explain Ohm\'s law.', 'Q: What is a transistor?'],
    'civil': ['Q: What is slump test?', 'Q: Define bearing capacity of soil.'],
    'electronics': ['Q: What is a diode?', 'Q: Explain Boolean algebra.'],
    'aptitude': ['Q: If A is 10% more than B, by what % is B less than A?', 'Q: Find the next number in the series: 2, 5, 10, 17, __?']
}

def get_chatbot_response(message):
    # (Keep existing chatbot logic)
    message = message.lower().strip()
    response = "I'm sorry, I didn't quite understand that. Could you please rephrase? I can help with GATE exam tips, subject info, and sample questions." # Default fallback

    # Greetings
    if re.search(r'\b(hello|hi|hey|good morning|good afternoon)\b', message):
        response = "Hello! How can I help you with your GATE preparation today?"
    # ... (rest of chatbot logic remains the same) ...
    else:
         found_subject = False
         for subject in gate_subjects:
             if re.search(rf'\b{subject}\b', message):
                  # Check if asking for questions or general info
                  if re.search(r'\b(question|sample|example|qs)\b', message):
                      qs = sample_qs_by_subject.get(subject, ["Sorry, I don't have specific sample questions for that subject right now."])
                      response = f"Okay, here are some sample questions for {subject.title()}:\n" + "\n".join(qs)
                  else:
                      # Provide general info or ask for clarification
                      response = f"Ah, {subject.title()}! Are you looking for sample questions, resources, or specific concepts within {subject.title()}?"
                  found_subject = True
                  break # Stop checking once a subject is found
         # If no subject was found and no other pattern matched, use the default fallback.
         if not found_subject and response.startswith("I'm sorry"):
              pass # Keep the default fallback message

    return response

@login_required
def chatbot(request):
    if request.method == 'POST':
        user_message = request.POST.get('message', '')
        reply = get_chatbot_response(user_message)
        return JsonResponse({'reply': reply})
    return render(request, 'exam/chatbot.html')

@login_required
def profile(request):
    # Make sure profile exists, handle potential DoesNotExist
    try:
        profile = request.user.candidateprofile
    except CandidateProfile.DoesNotExist:
        # Optionally create profile here if it's missing for a logged-in user
        # profile = CandidateProfile.objects.create(user=request.user)
        # Or handle the error appropriately
        pass
    return render(request, 'exam/profile.html')

@login_required
def view_question_papers(request):
    papers = PreviousQuestionPaper.objects.all()
    context = {'papers': papers}
    return render(request, 'exam/question_papers.html', context)

@login_required
def notes(request):
    notes_list = Note.objects.all()
    context = {'notes_list': notes_list}
    return render(request, 'exam/notes.html', context)


# exam/views.py (within the file)

from .models import Question # Make sure Question model is imported

# --- Function to populate questions (IMPROVED PLACEHOLDERS) ---
def populate_sample_questions():
    desired_question_count = 64
    current_q_count = Question.objects.count()

    if current_q_count < desired_question_count:
        print(f"[DEBUG] Current question count ({current_q_count}) is less than {desired_question_count}. Populating with improved placeholders...") #

        # **********************************************************************
        # ** IMPORTANT: These are REPRESENTATIVE PLACEHOLDER questions.        **
        # ** You MUST replace these with actual, verified GATE questions      **
        # ** from official sources (e.g., previous year papers) before use.   **
        # **********************************************************************
        real_gate_questions_placeholders = [
            # --- General Aptitude (Example: 10 questions, ~15 Marks) ---
            { # GA - MCQ - 1 Mark
                'question_text': 'Choose the word that is most nearly opposite in meaning to the word "EXODUS".',
                'question_type': 'MCQ',
                'choices': {'A': 'Influx', 'B': 'Departure', 'C': 'Migration', 'D': 'Exit'},
                'correct_answer': 'A', 'marks': 1.0, 'negative_marks': 0.33
            },
            { # GA - MCQ - 1 Mark
                'question_text': 'Pen : Write :: Knife : _________',
                'question_type': 'MCQ',
                'choices': {'A': 'Cut', 'B': 'Vegetable', 'C': 'Sharp', 'D': 'Shoot'},
                'correct_answer': 'A', 'marks': 1.0, 'negative_marks': 0.33
            },
             { # GA - MCQ - 1 Mark
                'question_text': 'If (x - 1/2)^2 – (x - 3/2)^2 = x + 2, then the value of x is:',
                'question_type': 'MCQ',
                'choices': {'A': '2', 'B': '4', 'C': '6', 'D': '8'},
                'correct_answer': 'B', 'marks': 1.0, 'negative_marks': 0.33
            },
            { # GA - NAT - 1 Mark
                'question_text': 'What is the missing number in the sequence: 2, 12, 60, 240, 720, 1440, _____, 0?',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '1440', 'marks': 1.0, 'negative_marks': 0.0
            },
             { # GA - MCQ - 2 Marks
                'question_text': 'A six-sided unbiased die with four green faces and two red faces is rolled seven times. Which of the following combinations is the most likely outcome?',
                'question_type': 'MCQ',
                'choices': {'A': 'Three green faces and four red faces', 'B': 'Four green faces and three red faces', 'C': 'Five green faces and two red faces', 'D': 'Six green faces and one red face'},
                'correct_answer': 'C', 'marks': 2.0, 'negative_marks': 0.67 # Approximation
            },
            { # GA - MCQ - 2 Marks
                'question_text': 'If pqr != 0 and p^(-x) = 1/q, q^(-y) = 1/r, r^(-z) = 1/p, what is the value of the product xyz?',
                'question_type': 'MCQ',
                'choices': {'A': '-1', 'B': '1/pqr', 'C': '1', 'D': 'pqr'},
                'correct_answer': 'C', 'marks': 2.0, 'negative_marks': 0.67
            },
            { # GA - NAT - 2 Marks
                'question_text': 'The ratio of the cost of item P to item Q is 3:4. Discount of 20% on P and 15% on Q is offered. If the total cost after discount is Rs. 567, what was the original cost of item Q (in Rs.)?',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '420', 'marks': 2.0, 'negative_marks': 0.0
            },
             { # GA - MSQ - 2 Marks
                'question_text': 'Which of the following shapes are convex polygons? (Select all that apply)',
                'question_type': 'MSQ',
                'choices': {'A': 'Square', 'B': 'Regular Hexagon', 'C': 'Star (5-pointed)', 'D': 'Equilateral Triangle'},
                'correct_answer': 'A,B,D', 'marks': 2.0, 'negative_marks': 0.0
            },
            { # GA - MCQ - 1 Mark
                'question_text': 'His knowledge of the subject was excellent but his classroom performance was ________.',
                'question_type': 'MCQ',
                'choices': {'A': 'extremely poor', 'B': 'good', 'C': 'desirable', 'D': 'praiseworthy'},
                'correct_answer': 'A', 'marks': 1.0, 'negative_marks': 0.33
            },
             { # GA - NAT - 2 Marks
                'question_text': 'Find the area (in square units) of the triangle whose vertices are (0,0), (3,1), and (1,4).',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '5.5', 'marks': 2.0, 'negative_marks': 0.0 # Area = 0.5 * |(x1(y2-y3) + x2(y3-y1) + x3(y1-y2))| = 0.5 * |0(1-4)+3(4-0)+1(0-1)| = 0.5 * |12-1| = 5.5
            },
            # --- Engineering Mathematics (Example: 8 questions, ~13 Marks) ---
             { # Math - MCQ - 1 Mark (Linear Algebra)
                'question_text': 'What is the rank of the matrix A = [[1, 2, 3], [2, 4, 6], [3, 6, 9]]?',
                'question_type': 'MCQ',
                'choices': {'A': '0', 'B': '1', 'C': '2', 'D': '3'},
                'correct_answer': 'B', 'marks': 1.0, 'negative_marks': 0.33
            },
            { # Math - NAT - 1 Mark (Calculus)
                'question_text': r'The value of the integral $\int_{0}^{1} x^2 dx$ is _____. (Enter numerical value up to 3 decimal places)',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '0.333', 'marks': 1.0, 'negative_marks': 0.0
            },
            { # Math - MCQ - 1 Mark (Probability)
                'question_text': 'A fair coin is tossed three times. What is the probability of getting exactly two heads?',
                'question_type': 'MCQ',
                'choices': {'A': '1/8', 'B': '2/8', 'C': '3/8', 'D': '4/8'},
                'correct_answer': 'C', 'marks': 1.0, 'negative_marks': 0.33 # HHT, HTH, THH out of 8 outcomes
            },
            { # Math - MCQ - 2 Marks (Differential Eq)
                'question_text': r'The solution to the differential equation $\frac{dy}{dx} = y$ with y(0) = 1 is:',
                'question_type': 'MCQ',
                'choices': {'A': 'y = e^x', 'B': 'y = e^(-x)', 'C': 'y = sin(x)', 'D': 'y = cos(x)'},
                'correct_answer': 'A', 'marks': 2.0, 'negative_marks': 0.67
            },
            { # Math - MCQ - 2 Marks (Routh Hurwitz)
                'question_text': 'Consider the polynomial P(s) = s^3 + 2s^2 + 3s + 6. According to Routh-Hurwitz criteria, the number of roots in the right half s-plane is:',
                'question_type': 'MCQ',
                'choices': {'A': '0', 'B': '1', 'C': '2', 'D': '3'},
                'correct_answer': 'A', 'marks': 2.0, 'negative_marks': 0.67
            },
             { # Math - NAT - 2 Marks (Calculus)
                'question_text': r'If $y = e^{-2x}$, find the value of $\frac{d^2y}{dx^2}$ at $x=0$.',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '4', 'marks': 2.0, 'negative_marks': 0.0
            },
            { # Math - NAT - 2 Marks (Linear Algebra)
                'question_text': r'Find the determinant of the matrix $B = \begin{pmatrix} 2 & 1 \\ 3 & 4 \end{pmatrix}$.',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '5', 'marks': 2.0, 'negative_marks': 0.0 # (2*4) - (1*3) = 8 - 3 = 5
            },
            { # Math - MSQ - 2 Marks (Discrete Math)
                'question_text': 'Which of the following relations on the set {1, 2, 3} are equivalence relations? (Select all that apply)',
                'question_type': 'MSQ',
                'choices': {'A': '{(1,1), (2,2), (3,3)}', 'B': '{(1,1), (2,2), (3,3), (1,2), (2,1)}', 'C': '{(1,1), (1,2), (1,3)}', 'D': '{(1,1), (2,2), (3,3), (1,2)}'},
                'correct_answer': 'A,B', 'marks': 2.0, 'negative_marks': 0.0 # A, B are reflexive, symmetric, transitive. C is not reflexive/symmetric. D is not symmetric/transitive.
            },
            # --- Core Subject (Example: CS - 46 questions, ~72 Marks) ---
            # (Adding more diverse examples across CS topics)
            { # CS - MCQ - 1 Mark (Complexity)
                'question_text': 'What is the time complexity of finding the height of a balanced binary search tree with n nodes?',
                'question_type': 'MCQ',
                'choices': {'A': 'O(1)', 'B': 'O(log n)', 'C': 'O(n)', 'D': 'O(n log n)'},
                'correct_answer': 'B', 'marks': 1.0, 'negative_marks': 0.33
            },
            { # CS - MCQ - 1 Mark (Networks)
                'question_text': 'Which layer of the OSI model is responsible for routing packets between networks?',
                'question_type': 'MCQ',
                'choices': {'A': 'Physical Layer', 'B': 'Data Link Layer', 'C': 'Network Layer', 'D': 'Transport Layer'},
                'correct_answer': 'C', 'marks': 1.0, 'negative_marks': 0.33
            },
             { # CS - MCQ - 1 Mark (DS)
                'question_text': 'Which data structure uses LIFO (Last-In, First-Out)?',
                'question_type': 'MCQ',
                'choices': {'A': 'Queue', 'B': 'Stack', 'C': 'Linked List', 'D': 'Tree'},
                'correct_answer': 'B', 'marks': 1.0, 'negative_marks': 0.33
            },
             { # CS - MCQ - 1 Mark (OS)
                'question_text': 'Which scheduling algorithm can lead to starvation?',
                'question_type': 'MCQ',
                'choices': {'A': 'FCFS', 'B': 'SJF (Non-preemptive)', 'C': 'Round Robin', 'D': 'Priority Scheduling'},
                'correct_answer': 'D', 'marks': 1.0, 'negative_marks': 0.33
            },
            { # CS - NAT - 1 Mark (Digital Logic)
                'question_text': 'How many selection lines are required for a 16x1 multiplexer?',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '4', 'marks': 1.0, 'negative_marks': 0.0
            },
             { # CS - NAT - 1 Mark (COA)
                'question_text': 'A memory has 16 address lines and 8 data lines. What is its capacity in KB?',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '64', 'marks': 1.0, 'negative_marks': 0.0 # 2^16 locations * 8 bits/location = 2^16 * 1 Byte = 64 KB
            },
            { # CS - MSQ - 2 Marks (TOC)
                'question_text': 'Which of the following languages are regular? (Select all that apply)',
                'question_type': 'MSQ',
                'choices': {'A': '{a^n b^n | n >= 0}', 'B': '{w | w contains an even number of a\'s}', 'C': '{w | w is a palindrome over {a,b}}', 'D': 'The set of all valid C identifiers'},
                'correct_answer': 'B,D', 'marks': 2.0, 'negative_marks': 0.0
            },
             { # CS - MSQ - 2 Marks (DBMS)
                'question_text': 'Which of the following are ACID properties of transactions? (Select all that apply)',
                'question_type': 'MSQ',
                'choices': {'A': 'Atomicity', 'B': 'Concurrency', 'C': 'Isolation', 'D': 'Durability', 'E': 'Consistency'},
                'correct_answer': 'A,C,D,E', 'marks': 2.0, 'negative_marks': 0.0
            },
             { # CS - MCQ - 2 Marks (OS - Deadlock)
                'question_text': 'Consider a system with 3 processes sharing 4 resource units. Each process needs a maximum of 2 units. Is the system in a safe state?',
                'question_type': 'MCQ',
                'choices': {'A': 'Yes', 'B': 'No', 'C': 'Depends on the current allocation', 'D': 'Cannot be determined'},
                'correct_answer': 'A', 'marks': 2.0, 'negative_marks': 0.67
            },
            { # CS - MCQ - 2 Marks (Algorithms)
                'question_text': 'What is the time complexity of Heap Sort algorithm in the worst case?',
                'question_type': 'MCQ',
                'choices': {'A': 'O(n)', 'B': 'O(log n)', 'C': 'O(n log n)', 'D': 'O(n^2)'},
                'correct_answer': 'C', 'marks': 2.0, 'negative_marks': 0.67
            },
            { # CS - MCQ - 2 Marks (Networks - TCP)
                'question_text': 'Which field in the TCP header is used for flow control?',
                'question_type': 'MCQ',
                'choices': {'A': 'Sequence Number', 'B': 'Acknowledgement Number', 'C': 'Window Size', 'D': 'Checksum'},
                'correct_answer': 'C', 'marks': 2.0, 'negative_marks': 0.67
            },
             { # CS - NAT - 2 Marks (DBMS - Keys)
                'question_text': 'Consider a relation R(A, B, C, D, E) with functional dependencies {A -> B, BC -> D, D -> E}. What is the candidate key? Enter attributes separated by comma if multiple, e.g., A,C',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': 'A,C', 'marks': 2.0, 'negative_marks': 0.0 # (AC)+ = ACBED
            },
             { # CS - NAT - 2 Marks (Algorithms - Graph)
                'question_text': 'What is the maximum number of edges in a simple undirected graph with 10 vertices?',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '45', 'marks': 2.0, 'negative_marks': 0.0 # nC2 = 10C2 = 10*9 / 2 = 45
            },
             # --- Add more questions (approx 33 more needed) ---
             # Add diverse questions covering remaining CS topics like Compiler Design,
             # more on OS, Networks, Algorithms, Data Structures, COA, Digital Logic, TOC, DBMS etc.
             # Ensure a mix of 1/2 marks and MCQ/MSQ/NAT.

             # Example: More CS Questions
              { # CS - MCQ - 1 Mark (Compiler)
                'question_text': 'Which phase of the compiler generates the symbol table?',
                'question_type': 'MCQ',
                'choices': {'A': 'Lexical Analysis', 'B': 'Syntax Analysis', 'C': 'Semantic Analysis', 'D': 'Code Generation'},
                'correct_answer': 'A', 'marks': 1.0, 'negative_marks': 0.33
            },
             { # CS - MCQ - 1 Mark (Networks - Addressing)
                'question_text': 'Which of the following is a private IP address?',
                'question_type': 'MCQ',
                'choices': {'A': '12.0.0.1', 'B': '172.16.10.5', 'C': '172.32.0.1', 'D': '192.169.1.1'},
                'correct_answer': 'B', 'marks': 1.0, 'negative_marks': 0.33
            },
             { # CS - MCQ - 2 Marks (DS - Trees)
                'question_text': 'The number of nodes in a full binary tree of height h (root at height 0) is:',
                'question_type': 'MCQ',
                'choices': {'A': '2^h - 1', 'B': '2^h', 'C': '2^(h+1) - 1', 'D': '2^(h+1)'},
                'correct_answer': 'C', 'marks': 2.0, 'negative_marks': 0.67
            },
             { # CS - NAT - 1 Mark (TOC)
                'question_text': 'Consider the grammar S -> aSb | ε. How many strings of length 4 does it generate?',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '1', 'marks': 1.0, 'negative_marks': 0.0 # Only 'aabb'
            },
             { # CS - MSQ - 2 Marks (Algorithms - Sorting)
                'question_text': 'Which of the following sorting algorithms have a worst-case time complexity of O(n log n)? (Select all that apply)',
                'question_type': 'MSQ',
                'choices': {'A': 'Bubble Sort', 'B': 'Merge Sort', 'C': 'Quick Sort', 'D': 'Heap Sort', 'E': 'Insertion Sort'},
                'correct_answer': 'B,D', 'marks': 2.0, 'negative_marks': 0.0 # Quick sort worst case is O(n^2)
            },
            # ... Continue adding placeholders until 64 are reached ...
            # Placeholder for question 64
             {
                'question_text': 'Placeholder Question 64 - Example NAT 2 Mark (Math)',
                'question_type': 'NAT',
                'choices': None,
                'correct_answer': '100',
                'marks': 2.0,
                'negative_marks': 0.0
            },

        ]

        # Ensure we don't add more than desired_question_count
        # Adjust if the placeholder list doesn't have exactly 64 items
        num_placeholders = len(real_gate_questions_placeholders)
        questions_to_populate = [real_gate_questions_placeholders[i % num_placeholders] for i in range(desired_question_count)]


        num_to_add = desired_question_count - current_q_count
        questions_to_create = []
        # Use modulo to cycle through placeholders if needed, although ideally have 64 placeholders
        # num_placeholders = len(questions_to_populate) # Already defined above

        # Add unique suffix logic just in case placeholders < 64 or to force uniqueness
        for i in range(num_to_add):
             q_data_index = i % num_placeholders
             q_data = questions_to_populate[q_data_index]
             # Make text unique if cycling through placeholders or just to be safe
             unique_suffix = f" (ID:{current_q_count + i + 1})" # Use database count offset
             temp_text = f"{q_data['question_text']}{unique_suffix}"

             # Check if a question with this exact text already exists
             if not Question.objects.filter(question_text=temp_text).exists():
                  questions_to_create.append(
                      Question(
                          question_text=temp_text,
                          question_type=q_data['question_type'],
                          choices=q_data.get('choices'),
                          correct_answer=q_data['correct_answer'],
                          marks=q_data.get('marks', 1.0),
                          # Ensure negative marks are stored as positive
                          negative_marks=abs(q_data.get('negative_marks', 0.0))
                      )
                  )
             else:
                 print(f"[WARN] Question with text '{temp_text}' likely already exists. Skipping.") #


        if questions_to_create:
            Question.objects.bulk_create(questions_to_create)
            print(f"[INFO] Populated {len(questions_to_create)} new questions using improved placeholders.") #
        else:
             print(f"[INFO] No new questions needed or placeholders already exist.") #

    # else:
    #     print(f"[INFO] Database already has {current_q_count} questions. Skipping population.")
# --- Exam view (Ensure population is called) ---
@login_required
def exam_view(request):
    populate_sample_questions() # Call the function here
    # Check profile verification status
    profile = getattr(request.user, 'candidateprofile', None)
    if not profile or not profile.is_phone_verified:
         # You might want to redirect to profile or show a message
         print(f"[WARN] User '{request.user.username}' attempting exam view without verified profile.") #
         # return redirect('profile') # Example redirect
         return render(request, 'exam/message.html', {'message': 'Please complete your profile verification.'})


    # Check for an existing active session
    active_session = ExamSession.objects.filter(candidate=request.user, end_time__isnull=True).first()

    if not active_session:
        print(f"[INFO] No active session found for user '{request.user.username}'. Creating new session.") #
        # Create a new session if none is active
        active_session = ExamSession.objects.create(candidate=request.user) # start_time is auto_now_add
    else:
         print(f"[INFO] Resuming active session {active_session.id} for user '{request.user.username}'.") #


    # Fetch exactly 64 questions for the exam session
    questions = Question.objects.all().order_by('id')[:64] # Or random selection
    context = {
        'session': active_session,
        'questions': questions,
    }
    return render(request, 'exam/exam.html', context)


# --- Submit Exam View (Updated with Negative Marking) ---
@login_required
def submit_exam(request):
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        print(f"[DEBUG] Attempting to submit exam for session ID: {session_id}") #
        try:
            # Ensure the session belongs to the current user and is not already finished
            session = ExamSession.objects.get(id=session_id, candidate=request.user, end_time__isnull=True)
        except ExamSession.DoesNotExist:
            print(f"[ERROR] Active session {session_id} not found for user '{request.user.username}'.") #
            # Handle error: session not found, already submitted, or belongs to another user
            return redirect('home') # Redirect home or show an error

        # Fetch the same questions shown in the exam view (ensure consistency)
        questions = Question.objects.all().order_by('id')[:64]
        total_score = 0.0
        answers_to_create_or_update = [] # Store data for bulk operations

        # Get existing answers for this session to perform updates instead of creates if possible
        existing_answers = {ans.question_id: ans for ans in CandidateAnswer.objects.filter(session=session)}

        print(f"[DEBUG] Processing answers for {len(questions)} questions.") #
        for question in questions:
            answer_str = ""
            question_score = 0.0 # Score for this question

            # Get submitted answer based on question type
            if question.question_type == 'MSQ':
                selected_options = request.POST.getlist(f'question_{question.id}')
                # Sort selected options to ensure consistent format for comparison
                selected_options.sort()
                answer_str = ','.join(selected_options)
            else:
                # Handles MCQ (single value) and NAT (text value)
                answer_str = request.POST.get(f'question_{question.id}', '').strip()

            # Determine if the question was answered
            is_answered = bool(answer_str)

            # --- Scoring Logic ---
            if is_answered:
                correct_answer_val = question.correct_answer
                # MSQ Scoring (Exact match, full marks, no negative)
                if question.question_type == 'MSQ':
                     correct_parts = sorted(correct_answer_val.split(','))
                     correct_answer_formatted = ','.join(correct_parts)
                     if answer_str == correct_answer_formatted:
                         question_score = question.marks
                # MCQ Scoring (Check correctness, apply negative marks)
                elif question.question_type == 'MCQ':
                    if answer_str == correct_answer_val:
                        question_score = question.marks
                    else:
                        # Apply negative marking only if the question has negative marks defined
                        if question.negative_marks > 0:
                             question_score = -abs(question.negative_marks)
                # NAT Scoring (Numerical comparison, no negative marks)
                elif question.question_type == 'NAT':
                    try:
                        # Use a small tolerance for floating point comparisons
                        if abs(float(answer_str) - float(correct_answer_val)) < 0.001:
                             question_score = question.marks
                    except (ValueError, TypeError):
                         print(f"[WARN] Invalid numeric answer '{answer_str}' for NAT Q{question.id}") #
                         pass # Invalid number entered, score remains 0
            # else: (not answered) score remains 0

            total_score += question_score
            # print(f"[DEBUG] Q{question.id}: Type={question.question_type}, Ans='{answer_str}', Correct='{question.correct_answer}', Score={question_score}")

            # Prepare data for bulk update/create
            answer_defaults = {
                'answer': answer_str,
                # 'score_awarded': question_score # Uncomment if storing score per answer
            }
            if question.id in existing_answers:
                # Update existing answer object
                ans_obj = existing_answers[question.id]
                ans_obj.answer = answer_str
                # ans_obj.score_awarded = question_score # Update score if storing
                answers_to_create_or_update.append(ans_obj) # Add object itself for bulk_update
            else:
                # Create new answer instance data
                 answers_to_create_or_update.append(
                     CandidateAnswer(
                         session=session,
                         question=question,
                         **answer_defaults
                     )
                 )

        # --- Perform Bulk Operations ---
        new_answers = [ans for ans in answers_to_create_or_update if not ans.pk]
        answers_to_update = [ans for ans in answers_to_create_or_update if ans.pk]

        if new_answers:
             CandidateAnswer.objects.bulk_create(new_answers)
             print(f"[DEBUG] Bulk created {len(new_answers)} answers.") #
        if answers_to_update:
             # Specify fields to update, including the answer and optionally score
             update_fields = ['answer']
             # if 'score_awarded' in CandidateAnswer._meta.fields: update_fields.append('score_awarded')
             CandidateAnswer.objects.bulk_update(answers_to_update, update_fields)
             print(f"[DEBUG] Bulk updated {len(answers_to_update)} answers.") #


        # Update session score and end time
        print(f"[DEBUG] Final total score for session {session.id}: {total_score}") #
        session.score = total_score
        session.end_time = timezone.now()
        session.save()

        print(f"[INFO] Exam session {session.id} submitted successfully.") #
        return redirect('result', session_id=session.id)

    # If not POST, redirect back
    print("[WARN] submit_exam accessed via GET. Redirecting.") #
    return redirect('exam')


# --- Result View (Keep as is) ---
@login_required
def result_view(request, session_id):
    session = get_object_or_404(ExamSession, id=session_id, candidate=request.user)
    answers = session.answers.all().order_by('question__id') # Ensure order
    proctor_logs = session.proctor_logs.all().order_by('timestamp') # Ensure order
    context = {
        'session': session,
        'answers': answers,
        'proctor_logs': proctor_logs,
    }
    return render(request, 'exam/result.html', context)

# --- Proctoring View (Enhanced Logging & Error Handling) ---
@csrf_exempt # Consider using proper CSRF handling with AJAX if possible
@login_required
def record_proctor_event(request):
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        frame_data = request.POST.get('frame_data')
        prev_frame_data = request.POST.get('prev_frame_data')

        # print(f"[DEBUG] Received proctor event for session: {session_id}") # Log entry

        if not session_id:
             print("[ERROR] Proctoring request missing session_id.") #
             return JsonResponse({'status': 'failed', 'error': 'Missing session ID.'}, status=400)

        try:
            # Ensure session exists, belongs to user, and is active
            session = ExamSession.objects.select_related('candidate__candidateprofile').get(
                id=session_id,
                candidate=request.user,
                end_time__isnull=True
            )
            candidate_profile = getattr(session.candidate, 'candidateprofile', None)
            # print(f"[DEBUG] Found active session {session.id} for user {session.candidate.username}")
        except ExamSession.DoesNotExist:
             print(f"[ERROR] Active session {session_id} not found for user '{request.user.username}' in proctoring.") #
             return JsonResponse({'status': 'failed', 'error': 'Active session not found.'}, status=404)
        except Exception as e:
             print(f"[ERROR] Error retrieving session/profile in proctoring: {e}") #
             print(traceback.format_exc()) # <--- Uses traceback #
             return JsonResponse({'status': 'failed', 'error': f'Error finding session: {e}'}, status=500)


        registered_face_path = None
        if candidate_profile and candidate_profile.face_data and hasattr(candidate_profile.face_data, 'path'):
             try:
                 if candidate_profile.face_data.storage.exists(candidate_profile.face_data.name):
                     registered_face_path = candidate_profile.face_data.path
                     # print(f"[DEBUG] Found registered face path: {registered_face_path}")
                 else:
                      print(f"[WARN] Face data file missing for user {session.candidate.username} at path: {candidate_profile.face_data.name}") #
             except Exception as e:
                  print(f"[ERROR] Error checking existence/path of face data: {e}") #
                  print(traceback.format_exc()) # <--- Uses traceback #


        ai_result = None
        details = "Proctoring check initiated."
        event_type = "proctor_check" # Default type

        if frame_data and registered_face_path:
            # print("[DEBUG] Frame data and face path available, calling process_proctoring.")
            try:
                # *** This is the most likely place for a 500 error if AI models fail ***
                ai_result = process_proctoring(frame_data, registered_face_path, prev_frame_data)
                # print(f"[DEBUG] AI Result: {ai_result}") # Log the AI result

                # Process results safely using .get()
                face_match_str = f"Face Match: {ai_result.get('face_match', 'N/A')}"
                objects_str = f"Objects: {ai_result.get('objects', [])}"
                movement_str = f"Movement: {ai_result.get('movement', 'N/A')}"
                details = f"{face_match_str}, {objects_str}, {movement_str}"

                extra_messages = []
                detected_objects = ai_result.get('objects', [])
                if isinstance(detected_objects, list):
                    if "cell phone" in detected_objects: extra_messages.append("Mobile phone")
                    if detected_objects.count("person") > 1: extra_messages.append("Multiple people")
                # Add check for face mismatch alert
                if ai_result.get('face_match') == False: extra_messages.append("Face mismatch")
                 # Add check for suspicious movement alert
                if ai_result.get('movement') == 'suspicious': extra_messages.append("Suspicious movement")


                if extra_messages:
                    details += " | ALERTS: " + ", ".join(extra_messages)
                    event_type = "proctor_alert" # Change event type if alerts found
                else:
                     event_type = "proctor_ok" # More specific type for successful checks

            except Exception as e:
                # Log the full error from process_proctoring
                print(f"[ERROR] CRITICAL: Exception during process_proctoring execution: {e}") #
                print(traceback.format_exc()) # <--- Print the full traceback for this error! #
                details = f"Error during AI processing: {e}"
                event_type = "proctor_error"
                # Return 500 status to indicate server error during processing
                return JsonResponse({'status': 'failed', 'error': details}, status=500)

        elif not frame_data:
            details = "Frame data not provided by client."
            event_type = "proctor_warning" # Or error, depending on expectation
            print(f"[WARN] {details} for session {session_id}") #
        elif not registered_face_path:
             details = "Registered face data missing or inaccessible for comparison."
             event_type = "proctor_warning"
             print(f"[WARN] {details} for session {session_id}") #

        # Log the event
        try:
             ProctorLog.objects.create(session=session, event_type=event_type, details=details)
             # print(f"[DEBUG] Proctor log created: Type={event_type}, Details={details[:100]}...")
        except Exception as log_e:
             print(f"[ERROR] Failed to create ProctorLog entry: {log_e}") #
             print(traceback.format_exc()) # <--- Uses traceback #
             # Decide if this failure should also return 500
             # return JsonResponse({'status': 'failed', 'error': 'Failed to log proctor event.'}, status=500)


        # Return success even if warnings occurred, but include AI results
        return JsonResponse({'status': 'success', 'ai_result': ai_result})

    else: # Not POST
        print("[ERROR] Proctoring endpoint accessed via non-POST method.") #
        return JsonResponse({'status': 'failed', 'error': 'Invalid request method'}, status=405) # Method Not Allowed

# --- Add a simple message view if needed for redirects ---
def message_view(request):
    message = request.GET.get('message', 'An unspecified error occurred.')
    return render(request, 'exam/message.html', {'message': message})