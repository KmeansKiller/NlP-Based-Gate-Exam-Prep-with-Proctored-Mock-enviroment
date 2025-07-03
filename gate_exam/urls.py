# (Inside gate_exam/urls.py - the one in the project root)

from django.contrib import admin
from django.urls import path, include
# --- Add these imports ---
from django.conf import settings
from django.conf.urls.static import static
# -----------------------

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('exam.urls')), # Includes urls from the 'exam' app
]

# --- Add this line to serve media files during development ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# -------------------------------------------------------------