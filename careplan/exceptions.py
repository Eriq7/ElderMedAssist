class BaseAppException(Exception):
    """
    All custom exceptions inherit from this.
    Middleware only needs: isinstance(e, BaseAppException)
    """
    type = 'error'
    code = 'unknown_error'
    http_status = 500

    def __init__(self, message, detail=None, code=None):
        self.message = message
        self.detail = detail
        if code:
            self.code = code
        super().__init__(self.message)

    def to_dict(self):
        result = {
            'type': self.type,
            'code': self.code,
            'message': self.message,
        }
        if self.detail is not None:
            result['detail'] = self.detail
        return result


class ValidationError(BaseAppException):
    """User input format is wrong (NPI not 10 digits, MRN not 6 digits)."""
    type = 'validation_error'
    code = 'invalid_input'
    http_status = 400


class BlockError(BaseAppException):
    """Business rule blocks the operation (duplicate NPI with different name)."""
    type = 'block'
    code = 'business_rule_violation'
    http_status = 409


class WarningException(BaseAppException):
    """
    Something suspicious but user can confirm to proceed.
    Returns 200 with needs_confirm=True.
    """
    type = 'warning'
    code = 'needs_confirmation'
    http_status = 200

    def to_dict(self):
        result = super().to_dict()
        result['needs_confirm'] = True
        return result
