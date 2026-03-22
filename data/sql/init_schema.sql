-- Initialize relational schema for Clinic AI Assistant
-- Run this before importing CSV data

-- Drop tables if they exist (for clean re-import)
DROP TABLE IF EXISTS clinical_notes CASCADE;
DROP TABLE IF EXISTS prescriptions CASCADE;
DROP TABLE IF EXISTS diagnoses CASCADE;
DROP TABLE IF EXISTS visits CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS clinics CASCADE;

-- Clinics table
CREATE TABLE clinics (
    clinic_id INTEGER PRIMARY KEY,
    clinic_name VARCHAR(255) NOT NULL,
    location VARCHAR(255)
);

-- Patients table
CREATE TABLE patients (
    patient_id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    dob DATE,
    gender VARCHAR(50)
);

-- Visits table
CREATE TABLE visits (
    visit_id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    clinic_id INTEGER NOT NULL,
    visit_date DATE NOT NULL,
    CONSTRAINT fk_visits_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    CONSTRAINT fk_visits_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(clinic_id)
);

-- Diagnoses table
CREATE TABLE diagnoses (
    diagnosis_id INTEGER PRIMARY KEY,
    visit_id INTEGER NOT NULL,
    icd_code VARCHAR(50),
    description VARCHAR(255),
    CONSTRAINT fk_diagnoses_visit
        FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- Prescriptions table
CREATE TABLE prescriptions (
    prescription_id INTEGER PRIMARY KEY,
    visit_id INTEGER NOT NULL,
    drug_name VARCHAR(255),
    dosage VARCHAR(255),
    CONSTRAINT fk_prescriptions_visit
        FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- Clinical Notes table
CREATE TABLE clinical_notes (
    note_id INTEGER PRIMARY KEY,
    visit_id INTEGER NOT NULL,
    diagnosis VARCHAR(255),
    clinical_note TEXT,
    CONSTRAINT fk_notes_visit
        FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- Indexes for performance
CREATE INDEX idx_visits_visit_date ON visits (visit_date);
CREATE INDEX idx_visits_patient_id ON visits (patient_id);
CREATE INDEX idx_visits_clinic_id ON visits (clinic_id);
CREATE INDEX idx_diagnoses_visit_id ON diagnoses (visit_id);
CREATE INDEX idx_diagnoses_description ON diagnoses (description);
CREATE INDEX idx_prescriptions_visit_id ON prescriptions (visit_id);
CREATE INDEX idx_notes_visit_id ON clinical_notes (visit_id);
