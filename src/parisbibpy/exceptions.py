"""Exceptions hierarchy for parisbibpy."""

from typing import Any


class ParisBibError(Exception):
    """Base exception for all errors raised by the parisbibpy library."""

    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class AuthenticationError(ParisBibError):
    """Raised when authentication fails (invalid credentials or rejected login)."""


class SessionExpiredError(AuthenticationError):
    """Raised when an existing session cookie (_syrSessGuid) has expired."""


class SyracuseApiError(ParisBibError):
    """Raised when the Syracuse API returns success=false or an error payload."""

    def __init__(
        self,
        message: str,
        errors: list[Any] | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        err_list = errors or []
        detailed_msg = message
        if err_list and isinstance(err_list[0], dict) and err_list[0].get("msg"):
            first_err = str(err_list[0]["msg"])
            if message and message != "Syracuse returned an error.":
                detailed_msg = f"{message}: {first_err}"
            else:
                detailed_msg = first_err

        super().__init__(detailed_msg, details=err_list)
        self.errors = err_list
        self.raw_response = raw_response


class ResourceNotFoundError(ParisBibError):
    """Raised when a specific patron record, holding, or loan is not found."""


class RenewalError(ParisBibError):
    """Raised when a loan renewal fails or is rejected by Syracuse."""

    def __init__(self, message: str, holding_id: str, reason: str | None = None) -> None:
        super().__init__(message, details={"holding_id": holding_id, "reason": reason})
        self.holding_id = holding_id
        self.reason = reason
