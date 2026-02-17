"""
Integration tests — test the full HTTP request → response cycle.

These tests hit the actual Django views (via test client),
go through middleware, services, and database.
"""

import json

import pytest
from unittest.mock import patch


VALID_PAYLOAD = {
    'provider_name': 'Dr. Smith',
    'provider_npi': '1234567890',
    'patient_first_name': 'John',
    'patient_last_name': 'Doe',
    'patient_mrn': 'MRN001',
    'date_of_birth': '1990-01-15',
    'medication_name': 'Lisinopril',
    'icd10_code': 'I10',
}


# ── Happy path ────────────────────────────────────────────

@pytest.mark.django_db
def test_generate_careplan_success(client):
    """POST valid data → 202 + care plan queued."""
    with patch('careplan.tasks.generate_careplan_task') as mock_task:
        response = client.post(
            '/api/generate/',
            data=json.dumps(VALID_PAYLOAD),
            content_type='application/json',
        )

    assert response.status_code == 202
    data = response.json()
    assert data['status'] == 'pending'
    assert 'id' in data
    mock_task.delay.assert_called_once()  # Celery task was triggered


# ── Provider block (NPI conflict) ─────────────────────────

@pytest.mark.django_db
def test_generate_duplicate_npi_returns_409(client):
    """Same NPI + different name → 409 block."""
    # First request creates provider
    with patch('careplan.tasks.generate_careplan_task'):
        client.post(
            '/api/generate/',
            data=json.dumps(VALID_PAYLOAD),
            content_type='application/json',
        )

    # Second request: same NPI, different name
    payload2 = {**VALID_PAYLOAD, 'provider_name': 'Dr. Johnson'}
    response = client.post(
        '/api/generate/',
        data=json.dumps(payload2),
        content_type='application/json',
    )

    assert response.status_code == 409
    data = response.json()
    assert data['type'] == 'block'
    assert data['code'] == 'duplicate_npi'


# ── Order block (same day duplicate) ─────────────────────

@pytest.mark.django_db
def test_generate_same_day_duplicate_returns_409(client):
    """Same patient + same medication + same day → 409 block."""
    with patch('careplan.tasks.generate_careplan_task'):
        client.post(
            '/api/generate/',
            data=json.dumps(VALID_PAYLOAD),
            content_type='application/json',
        )

    # Same exact request again
    with patch('careplan.tasks.generate_careplan_task'):
        response = client.post(
            '/api/generate/',
            data=json.dumps(VALID_PAYLOAD),
            content_type='application/json',
        )

    assert response.status_code == 409
    data = response.json()
    assert data['type'] == 'block'
    assert data['code'] == 'duplicate_order_same_day'


# ── List and Status endpoints ─────────────────────────────

@pytest.mark.django_db
def test_list_careplans_empty(client):
    """GET /api/careplans/ with no data → empty list."""
    response = client.get('/api/careplans/')

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_list_careplans_returns_created_plans(client):
    """Create a plan, then list → should appear."""
    with patch('careplan.tasks.generate_careplan_task'):
        create_resp = client.post(
            '/api/generate/',
            data=json.dumps(VALID_PAYLOAD),
            content_type='application/json',
        )

    plan_id = create_resp.json()['id']

    response = client.get('/api/careplans/')
    data = response.json()

    assert len(data) == 1
    assert data[0]['id'] == plan_id
    assert data[0]['status'] == 'pending'


@pytest.mark.django_db
def test_careplan_status_endpoint(client):
    """GET /api/careplans/<id>/status/ → returns plan details."""
    with patch('careplan.tasks.generate_careplan_task'):
        create_resp = client.post(
            '/api/generate/',
            data=json.dumps(VALID_PAYLOAD),
            content_type='application/json',
        )

    plan_id = create_resp.json()['id']

    response = client.get(f'/api/careplans/{plan_id}/status/')

    assert response.status_code == 200
    data = response.json()
    assert data['id'] == plan_id
    assert data['patient_name'] == 'John Doe'
