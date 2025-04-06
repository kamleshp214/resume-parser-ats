# Import required modules
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import re
import docx2txt
import fitz
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(file_stream, filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        text = ''
        with fitz.open(stream=file_stream, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text
    elif ext == 'docx':
        return docx2txt.process(file_stream)
    return ''

def extract_info(text, filename=""):
    text = text.replace('\r', '').strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Extract name from resume
    name = ""
    for line in lines[:5]:
        if (len(line.split()) <= 3 and 
            re.match(r'^[A-Za-z\s\-\']+$', line) and
            not any(char in line for char in "@0123456789")):
            name = line.strip()
            break

    if not name and filename:
        cleaned = re.sub(r'[_\-\.]', ' ', filename.rsplit('.', 1)[0])
        words = cleaned.split()
        noise_words = {'resume', 'cv', 'draft', 'final', 'version', 'v1', 'v2'}
        filtered = [
            w for w in words 
            if w.lower() not in noise_words and re.match(r'^[A-Z][a-z]+$', w)
        ]
        name = ' '.join(filtered[:2]) if filtered else ""

    # Extracting email, phone, and skills 
    email = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    phone = re.findall(r'\+?\d{1,3}[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-()]?\d{4}', text)
    common_skills = [r'python', r'java', r'c\+\+', r'javascript|js', r'html', r'css', r'sql', r'react', r'node\.?js', r'django', r'flask']
    found_skills = [
        skill.split('|')[0].replace(r'\+\+', '++')  # Convert c\+\+ to c++
        for skill in common_skills if re.search(skill, text, re.IGNORECASE)
    ]

    return {
        "name": name.title() if name else "",
        "email": email[0] if email else "",
        "phone": phone[0] if phone else "",
        "skills": ', '.join(found_skills) if found_skills else "",
        "filename": filename
    }

# Calculate ATS Score of Resume
def calculate_ats_score(parsed_data):
    keywords = ['python', 'java', 'javascript', 'sql', 'html', 'css', 'react', 'node']
    resume_text = (parsed_data.get("skills", "") + " " + parsed_data.get("name", "")).lower()
    matches = sum(1 for kw in keywords if kw in resume_text)
    return int((matches / len(keywords)) * 100)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse-resumes', methods=['POST'])
def parse_resumes():
    if 'resumes' not in request.files:
        return jsonify({"error": "No files part in request"}), 400

    files = request.files.getlist('resumes')
    if not files or all(not allowed_file(f.filename) for f in files):
        return jsonify({"error": "No valid files uploaded. Please upload PDF or DOCX files."}), 400

    results = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            text = extract_text(io.BytesIO(file_bytes), filename)
            parsed = extract_info(text, filename)
            parsed["filename"] = filename
            parsed["ats_score"] = calculate_ats_score(parsed)
            results.append(parsed)

    return jsonify(results)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)