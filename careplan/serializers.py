def serialize_careplan(p):
    patient = p.patient
    return {
        'id': p.id,
        'patient_name': f"{patient.first_name} {patient.last_name}",
        'medications': patient.medications,
        'allergies': patient.allergies,
        'health_conditions': patient.health_conditions,
        'status': p.status,
        'care_plan_text': p.care_plan_text if p.status == 'completed' else '',
        'created_at': p.created_at.isoformat(),
    }
