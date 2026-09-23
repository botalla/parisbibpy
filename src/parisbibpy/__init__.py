"""parisbibpy - Python client for the Paris public library system."""

from parisbibpy.client import ParisBibClient
from parisbibpy.exceptions import (
    AuthenticationError,
    ParisBibError,
    RenewalError,
    ResourceNotFoundError,
    SessionExpiredError,
    SyracuseApiError,
)
from parisbibpy.models import (
    AccountLoans,
    AccountSummary,
    Booking,
    BookingCollection,
    FamilyOverview,
    LibraryTrip,
    Loan,
    LoanCollection,
    PairedAccount,
    RenewalFailure,
    RenewalReport,
)

__version__ = "0.1.0"

__all__ = [
    "AccountLoans",
    "AccountSummary",
    "AuthenticationError",
    "Booking",
    "BookingCollection",
    "FamilyOverview",
    "LibraryTrip",
    "Loan",
    "LoanCollection",
    "PairedAccount",
    "ParisBibClient",
    "ParisBibError",
    "RenewalError",
    "RenewalFailure",
    "RenewalReport",
    "ResourceNotFoundError",
    "SessionExpiredError",
    "SyracuseApiError",
]
