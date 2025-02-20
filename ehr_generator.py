# ehr_generator.py
import json
from datetime import datetime

def merge_patient_information(structured_data):
    for page in structured_data:
        patient_info = page.get("Patient Information", {})
        if patient_info:
            return patient_info
    return {}

def aggregate_tests(structured_data):
    all_tests = []
    for page in structured_data:
        page_tests = page.get("Tests", [])
        all_tests.extend(page_tests)
    return all_tests

def aggregate_report_notes(structured_data):
    interpretations = []
    comments = []
    disclaimers = []
    quality_control = []
    for page in structured_data:
        notes = page.get("Report Notes", {})
        interpretations.extend(notes.get("Interpretations", []))
        comments.extend(notes.get("Comments", []))
        disclaimers.extend(notes.get("Disclaimers", []))
        quality_control.extend(notes.get("Quality Control", []))
    return {
        "Interpretations": interpretations,
        "Comments": comments,
        "Disclaimers": disclaimers,
        "Quality Control": quality_control,
    }

def generate_ehr(structured_data):
    if not structured_data:
        print("No structured data provided.")
        return None
    patient_info = merge_patient_information(structured_data)
    tests = aggregate_tests(structured_data)
    report_notes = aggregate_report_notes(structured_data)
    ehr_record = {
        "Patient": {
            "Name": patient_info.get("Name", ""),
            "Age": patient_info.get("Age", ""),
            "Sex": patient_info.get("Sex", ""),
            "Lab ID": patient_info.get("Lab ID", ""),
            "Sample Details": patient_info.get("Sample Details", {})
        },
        "Lab Results": tests,
        "Report Notes": report_notes,
        "Report Generated On": datetime.now().isoformat()
    }
    return ehr_record
