"""
Unit tests for Provider duplicate detection logic.

Tests the 3 branches in services.get_or_create_provider():
1. NPI exists + same name → reuse provider
2. NPI exists + different name → raise BlockError
3. New NPI → create new provider
"""

import pytest
from careplan.exceptions import BlockError
from careplan.models import Provider
from careplan.services import get_or_create_provider


@pytest.mark.django_db
def test_same_npi_same_name_reuses_provider():
    """Same NPI + same name = reuse existing provider."""
    existing = Provider.objects.create(name='Dr. Smith', npi='1234567890')

    result = get_or_create_provider('Dr. Smith', '1234567890')

    assert result.id == existing.id
    assert Provider.objects.count() == 1


@pytest.mark.django_db
def test_same_npi_different_name_raises_block():
    """Same NPI + different name = BlockError (NPI is a unique license)."""
    Provider.objects.create(name='Dr. Smith', npi='1234567890')

    with pytest.raises(BlockError) as exc_info:
        get_or_create_provider('Dr. Johnson', '1234567890')

    assert exc_info.value.code == 'duplicate_npi'
    assert '1234567890' in exc_info.value.message


@pytest.mark.django_db
def test_new_npi_creates_provider():
    """New NPI = create new provider."""
    result = get_or_create_provider('Dr. Smith', '1234567890')

    assert result.name == 'Dr. Smith'
    assert result.npi == '1234567890'
    assert Provider.objects.count() == 1
