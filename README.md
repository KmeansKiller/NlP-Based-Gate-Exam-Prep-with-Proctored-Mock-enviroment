# NLP-Based GATE Exam Prep with Proctored Mock Environment 🧠🧪

An AI-powered platform designed to simulate a real GATE exam experience using **Natural Language Processing (NLP)**, face detection, and intelligent result tracking.

---

## 🚀 Features

- ✅ Proctored mock test environment with face tracking
- 📊 Result analysis with performance trends
- 🧠 NLP-based adaptive question recommendation
- 🔐 Secure test submission and timing control
- 🧾 Upload and analyze past question papers

---

## 🛠️ Tech Stack

- **Python** / **Django**
- **OpenCV** + **YOLOv3** for face recognition
- **NLP** for text classification and question recommendation
- **SQLite** for data storage

---

## 📂 Project Structure
## 🚀 Installation & Setup Guide

Follow the steps below to set up the project on your local machine:

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/NLP-Based-Gate-Exam-Prep-with-Proctored-Mock-Environment.git
cd NLP-Based-Gate-Exam-Prep-with-Proctored-Mock-Environment

2. Install Python and Virtual Environment
Make sure you have Python 3.8+ installed. Then set up a virtual environment:

bash
Copy
Edit
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies
bash
Copy
Edit
pip install -r requirements.txt

If requirements.txt is missing, create it with:
bash
pip freeze > requirements.txt

4.Set up the database
Run the Django migrations to set up the SQLite database:

bash
python manage.py migrate


5.Run the development server
bash
python manage.py runserver
Visit http://127.0.0.1:8000 in your browser to access the application.

📁 Project Structure Overview
bash
├── exam/           # Exam app logic
├── face_data/      # Face recognition data (for proctoring)
├── gate_exam/      # GATE exam module
├── media/          # Media and uploads
├── db.sqlite3      # SQLite database
├── manage.py       # Django management script

📌 Notes
The file yolov3.weights is managed via Git LFS. Make sure to install Git LFS if you're cloning this repo.
bash
git lfs install
git lfs pull
face_data/ might require a webcam or simulated environment to test proctoring functionality.

You can customize settings.py for database, email config, etc.
