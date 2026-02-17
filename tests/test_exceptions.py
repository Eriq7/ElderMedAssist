"""
Tests for the unified exception handling system.

Tests two things:
1. Exception classes produce correct to_dict() output
2. Middleware catches exceptions and returns correct HTTP responses
"""

import json

import pytest
from django.test import RequestFactory

from careplan.exceptions import BaseAppException, BlockError, ValidationError, WarningException
from careplan.middleware import ExceptionHandlerMiddleware


# ── Exception class tests ─────────────────────────────────

def test_block_error_to_dict():
    """BlockError produces correct JSON structure."""
    error = BlockError(message='NPI conflict', code='duplicate_npi')

    result = error.to_dict()

    assert result == {
        'type': 'block',
        'code': 'duplicate_npi',
        'message': 'NPI conflict',
    }


def test_block_error_with_detail():
    """BlockError with detail includes it in output."""
    error = BlockError(
        message='NPI conflict',
        code='duplicate_npi',
        detail={'npi': '1234567890', 'existing_name': 'Dr. Smith'},
    )

    result = error.to_dict()

    assert result['detail'] == {'npi': '1234567890', 'existing_name': 'Dr. Smith'}


def test_warning_exception_includes_needs_confirm():
    """WarningException always includes needs_confirm=True."""
    warning = WarningException(message='Previous order exists')

    result = warning.to_dict()

    assert result['type'] == 'warning'
    assert result['needs_confirm'] is True


def test_validation_error_defaults():
    """ValidationError has correct defaults."""
    error = ValidationError(message='NPI must be 10 digits')

    assert error.http_status == 400
    assert error.type == 'validation_error'
    assert error.code == 'invalid_input'


def test_block_error_is_base_app_exception():
    """All custom exceptions inherit from BaseAppException."""
    error = BlockError(message='test')
    assert isinstance(error, BaseAppException)
    assert isinstance(error, Exception)


# ── Middleware tests ──────────────────────────────────────

def test_middleware_catches_block_error():
    """Middleware converts BlockError → 409 JsonResponse."""
    middleware = ExceptionHandlerMiddleware(get_response=lambda r: None)
    request = RequestFactory().get('/')

    exception = BlockError(message='NPI conflict', code='duplicate_npi')
    response = middleware.process_exception(request, exception)

    assert response.status_code == 409
    data = json.loads(response.content)
    assert data['type'] == 'block'
    assert data['code'] == 'duplicate_npi'


def test_middleware_catches_warning_exception():
    """Middleware converts WarningException → 200 JsonResponse."""
    middleware = ExceptionHandlerMiddleware(get_response=lambda r: None)
    request = RequestFactory().get('/')

    exception = WarningException(message='Duplicate order')
    response = middleware.process_exception(request, exception)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data['type'] == 'warning'
    assert data['needs_confirm'] is True


def test_middleware_ignores_non_app_exceptions():
    """Middleware returns None for non-BaseAppException (let Django handle it)."""
    middleware = ExceptionHandlerMiddleware(get_response=lambda r: None)
    request = RequestFactory().get('/')

    response = middleware.process_exception(request, ValueError('random error'))

    assert response is None  # middleware did NOT handle it
