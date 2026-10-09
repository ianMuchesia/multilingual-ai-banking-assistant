"""Service-level errors. The API layer maps them to HTTP status codes (see api/errors.py)."""


class ServiceError(Exception):
    """Base class; the message is safe to show to the customer."""


class NotFoundError(ServiceError):
    """404: does not exist, or does not belong to this customer."""


class ConflictError(ServiceError):
    """409: the resource is in the wrong state (expired, already executed, cancelled)."""


class InvalidInputError(ServiceError):
    """400: missing slots, bad values, insufficient funds."""
