"""
Unit tests for Patient get_or_create logic.

Tests the 2 branches in services.get_or_create_patient():
1. Patient with same name+DOB exists -> reuse and update meds/allergies/conditions
2. New patient -> create new
"""

import pytest
from careplan.models import Patient
from careplan.services import get_or_create_patient


@pytest.mark.django_db
def test_existing_patient_is_reused_and_updated():
    """Same name + DOB = reuse existing patient, update fields."""
    existing = Patient.objects.create(
        first_name='John', last_name='Doe', date_of_birth='1990-01-15',
        medications='Metformin', allergies='None', health_conditions='Diabetes',
    )

    patient = get_or_create_patient(
        'John', 'Doe', '1990-01-15',
        medications='Metformin, Lisinopril',
        allergies='Penicillin',
        health_conditions='Diabetes, Hypertension',
    )

    assert patient.id == existing.id
    assert patient.medications == 'Metformin, Lisinopril'
    assert patient.allergies == 'Penicillin'
    assert Patient.objects.count() == 1


@pytest.mark.django_db
def test_new_patient_is_created():
    """Completely new patient = create new."""
    patient = get_or_create_patient(
        'Alice', 'Wong', '1985-03-20',
        medications='Aspirin',
        allergies='',
        health_conditions='',
    )

    assert patient.first_name == 'Alice'
    assert patient.medications == 'Aspirin'
    assert Patient.objects.count() == 1
