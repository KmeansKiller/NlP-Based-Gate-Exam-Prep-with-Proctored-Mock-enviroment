from django.contrib import admin
# Import the new models
from .models import CandidateProfile, Question, ExamSession, CandidateAnswer, ProctorLog, Note, PreviousQuestionPaper

# Register existing models
admin.site.register(CandidateProfile)
admin.site.register(Question)
admin.site.register(ExamSession)
admin.site.register(CandidateAnswer)
admin.site.register(ProctorLog)

# Register new models
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'uploaded_at', 'uploaded_by')
    list_filter = ('subject', 'uploaded_at')
    search_fields = ('title', 'description')
    # Automatically set uploaded_by to the current user
    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(PreviousQuestionPaper)
class PreviousQuestionPaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'year', 'uploaded_at', 'uploaded_by')
    list_filter = ('subject', 'year', 'uploaded_at')
    search_fields = ('title', 'year')
     # Automatically set uploaded_by to the current user
    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)