# exam/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone # Keep this import
from django.conf import settings # Keep this import

# Define choices for question types
QUESTION_TYPES = (
    ('MCQ', 'Multiple Choice Question'),
    ('MSQ', 'Multiple Select Question'),
    ('NAT', 'Numerical Answer Type'),
)

# Define choices for subjects (optional, but good for organization)
SUBJECT_CHOICES = (
    ('CS', 'Computer Science'),
    ('ME', 'Mechanical Engineering'),
    ('EE', 'Electrical Engineering'),
    ('IT', 'Information Technology'),
    ('CE', 'Civil Engineering'),
    ('AE', 'Automobile Engineering'),
    ('MA', 'Mathematics'),
    ('PH', 'Physics'),
    ('CH', 'Chemistry'),
    ('GA', 'General Aptitude'),
    ('OT', 'Other'),
)

class CandidateProfile(models.Model):
    """
    Extends the default User model to store additional candidate-specific data.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='candidateprofile') # Added related_name
    face_data = models.ImageField(upload_to='face_data/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True) # Added phone field
    is_phone_verified = models.BooleanField(default=False) # Added verification status
    # Store OTP session ID temporarily during verification process
    otp_session_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username

class Question(models.Model):
    """
    Represents a single exam question.
    """
    question_text = models.TextField()
    question_type = models.CharField(max_length=3, choices=QUESTION_TYPES)
    # Stores choices for MCQ/MSQ as JSON (e.g., {"A": "Option 1", "B": "Option 2"})
    choices = models.JSONField(blank=True, null=True)
    # Correct answer string. For MSQ, could be comma-separated (e.g., "A,C")
    correct_answer = models.CharField(max_length=255)
    # Marks awarded for a correct answer
    marks = models.FloatField(default=1.0)
    # Marks deducted for an incorrect answer (absolute value)
    # Typically applied only to MCQs in GATE. Set default accordingly.
    negative_marks = models.FloatField(default=0.33)

    def __str__(self):
        return f"{self.question_type} - {self.question_text[:50]}..."

class ExamSession(models.Model):
    """
    Represents a single attempt by a candidate to take the exam.
    """
    candidate = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)
    score = models.FloatField(default=0.0) # Use FloatField for potentially fractional scores

    def __str__(self):
        status = "Finished" if self.end_time else "Ongoing"
        return f"Exam for {self.candidate.username} starting {self.start_time} ({status})"

    @property
    def duration(self):
        if self.end_time:
            return self.end_time - self.start_time
        return None

class CandidateAnswer(models.Model):
    """
    Stores the answer submitted by a candidate for a specific question in an exam session.
    """
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    # Stores the submitted answer (e.g., "A", "A,B", "12.34")
    answer = models.CharField(max_length=255, blank=True, null=True)
    # Optional: Store score achieved for this specific answer (could be positive or negative)
    # score_awarded = models.FloatField(default=0.0)

    def __str__(self):
        return f"Answer by {self.session.candidate.username} for Q{self.question.id} in Session {self.session.id}"

class ProctorLog(models.Model):
    """
    Logs proctoring events during an exam session.
    """
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='proctor_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=100)  # e.g., "proctor_check", "proctor_alert", "proctor_error"
    details = models.TextField(blank=True, null=True) # e.g., AI results, error messages

    def __str__(self):
        return f"{self.event_type} at {self.timestamp} for Session {self.session.id}"

    class Meta:
        ordering = ['timestamp'] # Show logs chronologically

class Note(models.Model):
    """
    Represents study notes uploaded by users or admins.
    """
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    subject = models.CharField(max_length=2, choices=SUBJECT_CHOICES, default='OT')
    file = models.FileField(upload_to='notes/') # Files will be saved in MEDIA_ROOT/notes/
    uploaded_at = models.DateTimeField(default=timezone.now)
    # Track who uploaded, set to null if user is deleted
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_notes')

    def __str__(self):
        return f"{self.title} ({self.get_subject_display()})"

    class Meta:
        ordering = ['-uploaded_at'] # Show newest first

class PreviousQuestionPaper(models.Model):
    """
    Represents previous year question papers uploaded by users or admins.
    """
    title = models.CharField(max_length=200) # e.g., "GATE CS 2023 Question Paper"
    year = models.PositiveIntegerField()
    subject = models.CharField(max_length=2, choices=SUBJECT_CHOICES)
    file = models.FileField(upload_to='previous_papers/') # Files will be saved in MEDIA_ROOT/previous_papers/
    uploaded_at = models.DateTimeField(default=timezone.now)
    # Track who uploaded, set to null if user is deleted
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_papers')

    def __str__(self):
        return f"{self.get_subject_display()} - {self.year}"

    class Meta:
        ordering = ['-year', 'subject'] # Show newest year first, then by subject