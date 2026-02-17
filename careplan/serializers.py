def serialize_careplan(p):
    order = p.order
    patient = order.patient
    provider = order.provider
    return {
        'id': p.id,
        'patient_name': f"{patient.first_name} {patient.last_name}",
        'patient_mrn': patient.mrn,
        'medication': order.medication_name,
        'icd10_code': order.icd10_code,
        'provider_name': provider.name,
        'provider_npi': provider.npi,
        'status': p.status,
        'care_plan_text': p.care_plan_text if p.status == 'completed' else '',
        'created_at': p.created_at.isoformat(),
    }
