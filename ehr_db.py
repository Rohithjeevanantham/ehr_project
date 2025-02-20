import json
import os

DB_FILE = "ehr_database.json"

def load_database():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {"patients": {}}

def save_database(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4)

def merge_new_report(new_ehr, patient_id):
    """
    Merge a new report (new_ehr) into the database under patient_id.
    Each patient record contains:
      - "Patient": basic patient info (from the first or latest report)
      - "Reports": list of successive reports (each with its own date/time and lab results)
    """
    db = load_database()
    patients = db.get("patients", {})
    
    # Force the Lab ID to be the manually entered patient_id
    new_ehr["Patient"]["Lab ID"] = patient_id
    
    if patient_id in patients:
        # Append new report
        patients[patient_id]["Reports"].append(new_ehr)
        # Optionally update basic info
        patients[patient_id]["Patient"] = new_ehr.get("Patient", {})
    else:
        patients[patient_id] = {
            "Patient": new_ehr.get("Patient", {}),
            "Reports": [new_ehr]
        }
    db["patients"] = patients
    save_database(db)
    return db
