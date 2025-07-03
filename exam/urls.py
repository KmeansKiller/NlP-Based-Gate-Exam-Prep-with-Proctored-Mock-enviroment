# exam/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register, name='register'),
    path('verify-otp/', views.verify_otp, name='verify_otp'), # Add this line
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('exam/', views.exam_view, name='exam'),
    path('submit/', views.submit_exam, name='submit_exam'),
    path('result/<int:session_id>/', views.result_view, name='result'),
    path('record_proctor_event/', views.record_proctor_event, name='record_proctor_event'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('profile/', views.profile, name='profile'),
    path('question-papers/', views.view_question_papers, name='view_question_papers'),
    path('notes/', views.notes, name='notes'),
]