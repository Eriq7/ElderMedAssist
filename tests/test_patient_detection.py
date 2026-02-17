"""
Unit tests for Patient duplicate detection logic.

Tests the 4 branches in services.get_or_create_patient():
1. MRN exists + same name/DOB → reuse patient, no warning
2. MRN exists + different name/DOB → reuse patient, WITH warning
3. MRN new + name/DOB matches existing patient → create new, WITH warning
4. Completely new patient → create new, no warning
"""

import pytest
from careplan.models import Patient
from careplan.services import get_or_create_patient


# ── Case 1: MRN exists, same name + DOB → reuse, no warning ──

@pytest.mark.django_db
def test_exact_match_reuses_patient():
    """Same MRN + same name + same DOB = reuse existing patient."""
    existing = Patient.objects.create(
        first_name='John', last_name='Doe', mrn='MRN001', date_of_birth='1990-01-15',
    )

    patient, warning = get_or_create_patient('John', 'Doe', 'MRN001', '1990-01-15')

    assert patient.id == existing.id    # same DB record
    assert warning is None              # no warning
    assert Patient.objects.count() == 1  # no new patient created


# ── Case 2: MRN exists, different name or DOB → reuse, WITH warning ──

@pytest.mark.django_db
def test_mrn_exists_different_name_returns_warning():
    """Same MRN but different name = reuse existing patient + warning."""
    existing = Patient.objects.create(
        first_name='John', last_name='Doe', mrn='MRN001', date_of_birth='1990-01-15',
    )

    patient, warning = get_or_create_patient('Jane', 'Smith', 'MRN001', '1990-01-15')

    assert patient.id == existing.id       # reused existing patient
    assert warning is not None             # got a warning
    assert 'MRN MRN001 exists' in warning['warning']
    assert Patient.objects.count() == 1    # no new patient created


@pytest.mark.django_db
def test_mrn_exists_different_dob_returns_warning():
    """Same MRN but different DOB = reuse existing patient + warning."""
    Patient.objects.create(
        first_name='John', last_name='Doe', mrn='MRN001', date_of_birth='1990-01-15',
    )

    patient, warning = get_or_create_patient('John', 'Doe', 'MRN001', '2000-12-25')

    assert warning is not None
    assert 'MRN MRN001 exists' in warning['warning']
    assert Patient.objects.count() == 1


# ── Case 3: MRN is new, but name+DOB matches existing → create new, WITH warning ──

@pytest.mark.django_db
def test_name_dob_match_different_mrn_creates_new_with_warning():
    """New MRN but same name+DOB as existing patient = create new + warning."""
    existing = Patient.objects.create(
        first_name='John', last_name='Doe', mrn='MRN001', date_of_birth='1990-01-15',
    )

    patient, warning = get_or_create_patient('John', 'Doe', 'MRN002', '1990-01-15')

    assert patient.id != existing.id        # new patient created
    assert warning is not None              # got a warning
    assert 'already exists with MRN MRN001' in warning['warning']
    assert Patient.objects.count() == 2     # now 2 patients in DB


# ── Case 4: Completely new patient → create, no warning ──

@pytest.mark.django_db
def test_new_patient_creates_without_warning():
    """Completely new patient = create new, no warning."""
    patient, warning = get_or_create_patient('Alice', 'Wong', 'MRN999', '1985-03-20')

    assert patient.first_name == 'Alice'
    assert patient.mrn == 'MRN999'
    assert warning is None
    assert Patient.objects.count() == 1
