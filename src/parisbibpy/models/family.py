"""Family overview facade model aggregating primary and linked accounts."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from parisbibpy.models.account import AccountLoans
from parisbibpy.models.booking import Booking, BookingCollection
from parisbibpy.models.loan import LibraryTrip, Loan, LoanCollection


class FamilyOverview(BaseModel):
    """Convenience facade aggregating all family members' accounts, loans, and bookings."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    primary_account: AccountLoans
    paired_accounts: list[AccountLoans] = Field(default_factory=list)
    failed_accounts: list[Any] = Field(default_factory=list)

    @property
    def accounts(self) -> list[AccountLoans]:
        """All loaded family accounts (primary + paired)."""
        return [self.primary_account] + self.paired_accounts

    @property
    def loans(self) -> LoanCollection:
        """Flattened collection of all family loans retaining cardholder context."""
        items: list[Loan] = list(self.primary_account.loans)
        for pa in self.paired_accounts:
            items.extend(pa.loans)
        return LoanCollection(items)

    @property
    def bookings(self) -> BookingCollection:
        """Flattened collection of all family reservations."""
        items: list[Booking] = list(self.primary_account.bookings)
        for pa in self.paired_accounts:
            items.extend(pa.bookings)
        return BookingCollection(items)

    def plan_library_trips(self) -> list[LibraryTrip]:
        """Plan and prioritize drop-off visits across all family loans."""
        return self.loans.plan_library_trips()
