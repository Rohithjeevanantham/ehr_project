import os
import threading
import time
import uuid
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from extractor import extract_text_from_pdf
from genai_concurrent import process_blood_report
from ehr_generator import generate_ehr
from ehr_db import merge_new_report, load_database
from llm_analysis import analyze_patient_report, stream_analysis
from dashboard import generate_lab_plots

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Global dictionary for per-job processing status.
processing_status = {}
status_lock = threading.Lock()

def background_processing(job_id, file_path, patient_id):
    # 1. Extract text.
    text_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_extracted.txt")
    extract_text_from_pdf(file_path, text_file_path)
    
    # 2. Process text into structured JSON.
    def progress_callback(current, total):
        with status_lock:
            processing_status[job_id]['progress'] = int((current / total) * 100)
    structured_data = process_blood_report(text_file_path, progress_callback=progress_callback)
    
    # 3. Generate final EHR.
    new_ehr = generate_ehr(structured_data)
    
    # Save job JSON.
    ehr_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_ehr.json")
    with open(ehr_file, 'w', encoding='utf-8') as f:
        json.dump(new_ehr, f, indent=4)
    
    # 4. Merge into persistent database.
    merge_new_report(new_ehr, patient_id)
    
    with status_lock:
        processing_status[job_id]['status'] = 'Completed'
        processing_status[job_id]['ehr_file'] = ehr_file
        processing_status[job_id]['patient_id'] = patient_id

@app.route('/', methods=['GET'])
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    patient_id = request.form.get("patient_id")
    if not patient_id:
        return "Unique Patient ID is required", 400
    job_id = str(uuid.uuid4())
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{file.filename}")
    file.save(upload_path)
    with status_lock:
        processing_status[job_id] = {'progress': 0, 'status': 'Processing', 'ehr_file': None}
    threading.Thread(target=background_processing, args=(job_id, upload_path, patient_id)).start()
    return redirect(url_for('progress', job_id=job_id))

@app.route('/progress/<job_id>')
def progress(job_id):
    return render_template('progress.html', job_id=job_id)

@app.route('/progress_status/<job_id>')
def progress_status(job_id):
    with status_lock:
        status = processing_status.get(job_id, {})
    return jsonify(status)

def load_ehr_by_patient(patient_id):
    db = load_database()
    return db.get("patients", {}).get(patient_id)

@app.route('/dashboard/<patient_id>')
def dashboard(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient record not found", 404
    return render_template('dashboard.html', ehr=ehr, patient_id=patient_id)

@app.route('/patients/<patient_id>')
def patients(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient record not found", 404
    return render_template('patients.html', ehr=ehr, patient_id=patient_id)

@app.route('/lab_results/<patient_id>')
def lab_results(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient record not found", 404
    return render_template('lab_results.html', ehr=ehr, patient_id=patient_id)

@app.route('/notes/<patient_id>')
def notes(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient record not found", 404
    return render_template('notes.html', ehr=ehr, patient_id=patient_id)

@app.route('/settings/<patient_id>', methods=['GET', 'POST'])
def settings(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if request.method == 'POST':
        # Dummy settings handler.
        return redirect(url_for('settings', patient_id=patient_id))
    return render_template('settings.html', ehr=ehr, patient_id=patient_id)

# New SSE route for streaming analysis.
@app.route('/analysis_stream/<patient_id>')
def analysis_stream(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient record not found", 404
    def generate():
        for event in stream_analysis(ehr):
            yield event
    return Response(generate(), mimetype="text/event-stream")

# Regular analysis page that uses JS to stream analysis.
@app.route('/analysis/<patient_id>')
def analysis(patient_id):
    # This page will use JavaScript to connect to /analysis_stream/<patient_id>
    return render_template('analysis.html', patient_id=patient_id)

@app.route('/all_patients')
def all_patients():
    db = load_database()
    patients = db.get("patients", {})
    return render_template('all_patients.html', patients=patients)

@app.route('/patient/<patient_id>')
def patient(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient not found", 404
    return render_template('patient_detail.html', patient=ehr)

@app.route('/new_upload')
def new_upload():
    return redirect(url_for('index'))

@app.route('/dashboard_analysis/<patient_id>')
def dashboard_analysis(patient_id):
    ehr = load_ehr_by_patient(patient_id)
    if not ehr:
        return "Patient record not found", 404
    charts = generate_lab_plots(ehr)
    return render_template('dashboard_analysis.html', charts=charts, patient_id=patient_id)




if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
