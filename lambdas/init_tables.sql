CREATE TABLE IF NOT EXISTS patient (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    medications TEXT NOT NULL,
    allergies TEXT DEFAULT '',
    health_conditions TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS careplan (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    care_plan_text TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
