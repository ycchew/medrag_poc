import pandas as pd
import random
from faker import Faker

fake = Faker()

# Load diagnosis dataset generated earlier
diagnoses = pd.read_csv("diagnoses.csv")
visits = pd.read_csv("visits.csv")

# Join diagnosis with visit dates
data = diagnoses.merge(visits, on="visit_id")

# Sample subset for notes
notes_sample = data.sample(n=300)

# Symptom templates
SYMPTOMS = {
    "Hypertension": ["headache", "dizziness", "blurred vision"],
    "Type 2 Diabetes": ["fatigue", "frequent urination", "increased thirst"],
    "Upper respiratory infection": ["cough", "sore throat", "runny nose"],
    "Back pain": ["lower back pain", "stiffness"],
    "Dengue fever": ["high fever", "muscle pain", "joint pain"],
    "GERD": ["heartburn", "acid reflux", "chest discomfort"],
    "Asthma": ["wheezing", "shortness of breath", "chest tightness"],
    "UTI": ["burning urination", "frequent urination", "pelvic pain"],
    "Flu": ["fever", "body aches", "fatigue"]
}

notes = []

for i, row in notes_sample.iterrows():

    disease = row["description"]
    symptoms = ", ".join(random.sample(SYMPTOMS[disease], min(2, len(SYMPTOMS[disease]))))

    note = f"""
Subjective:
Patient reports {symptoms} for the past {random.randint(1,5)} days.

Objective:
Vital signs stable. Physical examination consistent with suspected {disease.lower()}.

Assessment:
Diagnosis: {disease}

Plan:
Prescribe {disease.lower()} treatment. Advise rest and hydration.
Follow-up if symptoms worsen.
"""

    notes.append({
        "note_id": i,
        "visit_id": row["visit_id"],
        "diagnosis": disease,
        "clinical_note": note.strip()
    })

notes_df = pd.DataFrame(notes)

notes_df.to_csv("clinical_notes.csv", index=False)

print("Clinical notes generated: clinical_notes.csv")