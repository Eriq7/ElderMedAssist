"""
Unit tests for Order duplicate detection logic.

Tests the 3 branches in services.check_duplicate_order():
1. Same patient + same medication + same day → raise BlockError
2. Same patient + same medication + different day + no confirm → raise WarningException
3. Same patient + same medication + different day + confirm=True → allow (no exception)
4. No previous order → allow (no exception)
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from careplan.exceptions import BlockError, WarningException
from careplan.models import Order, Patient, Provider
from careplan.services import check_duplicate_order


@pytest.fixture
def patient(db):
    """Create a test patient for order tests."""
    return Patient.objects.create(
        first_name='John', last_name='Doe', mrn='MRN001', date_of_birth='1990-01-15',
    )


@pytest.fixture
def provider(db):
    """Create a test provider for order tests."""
    return Provider.objects.create(name='Dr. Smith', npi='1234567890')


@pytest.mark.django_db
def test_same_day_duplicate_raises_block(patient, provider):
    """Same patient + same medication + same day = blocked."""
    Order.objects.create(
        patient=patient, provider=provider,
        medication_name='Lisinopril', icd10_code='I10',
    )

    with pytest.raises(BlockError) as exc_info:
        check_duplicate_order(patient, 'Lisinopril')

    assert exc_info.value.code == 'duplicate_order_same_day'


@pytest.mark.django_db
def test_previous_order_no_confirm_raises_warning(patient, provider):
    """Same medication from a previous day + no confirm = warning."""
    old_order = Order.objects.create(
        patient=patient, provider=provider,
        medication_name='Lisinopril', icd10_code='I10',
    )
    # Manually set created_at to yesterday (auto_now_add prevents setting in create)
    Order.objects.filter(id=old_order.id).update(
        created_at=timezone.now() - timedelta(days=7),
    )

    with pytest.raises(WarningException) as exc_info:
        check_duplicate_order(patient, 'Lisinopril', confirm=False)

    assert exc_info.value.code == 'duplicate_order_previous'


@pytest.mark.django_db
def test_previous_order_with_confirm_allows(patient, provider):
    """Same medication from a previous day + confirm=True = allowed."""
    old_order = Order.objects.create(
        patient=patient, provider=provider,
        medication_name='Lisinopril', icd10_code='I10',
    )
    Order.objects.filter(id=old_order.id).update(
        created_at=timezone.now() - timedelta(days=7),
    )

    # Should NOT raise any exception
    check_duplicate_order(patient, 'Lisinopril', confirm=True)


@pytest.mark.django_db
def test_no_previous_order_allows(patient):
    """No previous order for this medication = allowed."""
    # Should NOT raise any exception
    check_duplicate_order(patient, 'Lisinopril')


@pytest.mark.django_db
def test_different_medication_allows(patient, provider):
    """Same patient but different medication = allowed."""
    Order.objects.create(
        patient=patient, provider=provider,
        medication_name='Lisinopril', icd10_code='I10',
    )

    # Different medication should not raise
    check_duplicate_order(patient, 'Metformin')
