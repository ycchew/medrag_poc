import random
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()

# ----------------------------
# CONFIG
# ----------------------------

NUM_PATIENTS = 10000
NUM_VISITS = 50000
NUM_CLINICS = 10

START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2025, 12, 31)

# Disease base probabilities
DISEASES = {
    "Hypertension": 0.15,
    "Type 2 Diabetes": 0.12,
    "Upper respiratory infection": 0.25,
    "Back pain": 0.10,
    "Dengue fever": 0.03,
    "GERD": 0.08,
    "Asthma": 0.10,
    "UTI": 0.07,
    "Flu": 0.10
}

ICD = {
    "Hypertension": "I10",
    "Type 2 Diabetes": "E11",
    "Upper respiratory infection": "J06",
    "Back pain": "M54",
    "Dengue fever": "A90",
    "GERD": "K21",
    "Asthma": "J45",
    "UTI": "N39",
    "Flu": "J10"
}

DRUG_MAP = {
    "Hypertension": "Lisinopril",
    "Type 2 Diabetes": "Metformin",
    "Upper respiratory infection": "Paracetamol",
    "Back pain": "Ibuprofen",
    "Dengue fever": "Paracetamol",
    "GERD": "Omeprazole",
    "Asthma": "Salbutamol",
    "UTI": "Amoxicillin",
    "Flu": "Oseltamivir"
}

# Clinic specialization (affects disease distribution)
CLINIC_SPECIALTY = {
    1: "Dengue fever",
    2: "Type 2 Diabetes",
    3: "Hypertension",
    4: "Asthma",
    5: "GERD",
}

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------

def random_date():
    delta = END_DATE - START_DATE
    return START_DATE + timedelta(days=random.randint(0, delta.days))

def patient_age(dob):
    today = datetime.today().date()
    return today.year - dob.year

def choose_disease(age, visit_date, clinic_id):

    weights = DISEASES.copy()

    month = visit_date.month

    # Dengue season (rainy months)
    if month in [10, 11, 12]:
        weights["Dengue fever"] *= 4

    # Flu season
    if month in [6, 7, 8]:
        weights["Flu"] *= 3

    # Elderly hypertension
    if age > 50:
        weights["Hypertension"] *= 2
        weights["Type 2 Diabetes"] *= 1.5

    # Children asthma
    if age < 12:
        weights["Asthma"] *= 2

    # Clinic specialty
    if clinic_id in CLINIC_SPECIALTY:
        specialty = CLINIC_SPECIALTY[clinic_id]
        weights[specialty] *= 2

    diseases = list(weights.keys())
    probs = list(weights.values())

    total = sum(probs)
    probs = [p / total for p in probs]

    return random.choices(diseases, probs)[0]

# ----------------------------
# CLINICS
# ----------------------------

clinics = []

for i in range(NUM_CLINICS):
    clinics.append({
        "clinic_id": i + 1,
        "clinic_name": f"{fake.city()} Medical Clinic",
        "location": fake.city()
    })

clinics_df = pd.DataFrame(clinics)

# ----------------------------
# PATIENTS
# ----------------------------

patients = []

for i in range(NUM_PATIENTS):

    dob = fake.date_of_birth(minimum_age=1, maximum_age=90)

    patients.append({
        "patient_id": i + 1,
        "name": fake.name(),
        "dob": dob,
        "gender": random.choice(["Male", "Female"])
    })

patients_df = pd.DataFrame(patients)

# ----------------------------
# VISITS / DIAGNOSES / PRESCRIPTIONS
# ----------------------------

visits = []
diagnoses = []
prescriptions = []

diagnosis_id = 1
prescription_id = 1

for visit_id in range(1, NUM_VISITS + 1):

    patient = patients[random.randint(0, NUM_PATIENTS - 1)]
    patient_id = patient["patient_id"]
    dob = patient["dob"]

    clinic_id = random.randint(1, NUM_CLINICS)
    visit_date = random_date()

    age = patient_age(dob)

    visits.append({
        "visit_id": visit_id,
        "patient_id": patient_id,
        "clinic_id": clinic_id,
        "visit_date": visit_date
    })

    # Some visits have multiple diagnoses
    num_diagnoses = random.choices([1, 2], [0.8, 0.2])[0]

    for _ in range(num_diagnoses):

        disease = choose_disease(age, visit_date, clinic_id)

        diagnoses.append({
            "diagnosis_id": diagnosis_id,
            "visit_id": visit_id,
            "icd_code": ICD[disease],
            "description": disease
        })

        drug = DRUG_MAP[disease]

        prescriptions.append({
            "prescription_id": prescription_id,
            "visit_id": visit_id,
            "drug_name": drug,
            "dosage": "Standard dose"
        })

        diagnosis_id += 1
        prescription_id += 1

# Convert to dataframes
visits_df = pd.DataFrame(visits)
diagnoses_df = pd.DataFrame(diagnoses)
prescriptions_df = pd.DataFrame(prescriptions)

# ----------------------------
# EXPORT
# ----------------------------

patients_df.to_csv("patients.csv", index=False)
clinics_df.to_csv("clinics.csv", index=False)
visits_df.to_csv("visits.csv", index=False)
diagnoses_df.to_csv("diagnoses.csv", index=False)
prescriptions_df.to_csv("prescriptions.csv", index=False)

print("Realistic synthetic clinic dataset generated.")
print("Files:")
print("patients.csv")
print("clinics.csv")
print("visits.csv")
print("diagnoses.csv")
print("prescriptions.csv")