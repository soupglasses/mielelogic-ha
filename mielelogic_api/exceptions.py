"""Package exception hierarchy."""


class MieleLogicError(Exception):
    """Base exception for MieleLogic API errors."""


class MieleLogicAuthError(MieleLogicError):
    """Authentication failed."""


class MieleLogicConnectionError(MieleLogicError):
    """Connection or communication error."""
