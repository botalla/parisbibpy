"""Account models representing patron metrics and paired family cards."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parisbibpy.utils import parse_syracuse_date


class AccountSummary(BaseModel):
    """Patron summary metrics for loans and reservations."""

    model_config = ConfigDict(populate_by_name=True)

    barcode: str = Field(alias="Barcode")
    display_name: str = Field(alias="DisplayName")
    loans_total_count: int = Field(default=0, alias="LoansTotalCount")
    loans_not_late_count: int = Field(default=0, alias="LoansNotLateCount")
    loans_late_count: int = Field(default=0, alias="LoansLateCount")
    loans_next_handing_count: int = Field(default=0, alias="LoansNextHandingCount")
    loans_next_handing_date: datetime | None = Field(default=None, alias="LoansNextHandingDate")
    loans_next_handing_is_soon_late: bool = Field(default=False, alias="LoansNextHandingIsSoonLate")
    bookings_total_count: int = Field(default=0, alias="BookingsTotalCount")
    bookings_available_count: int = Field(default=0, alias="BookingsAvailableCount")
    bookings_not_available_count: int = Field(default=0, alias="BookingsNotAvailableCount")

    @field_validator("loans_next_handing_date", mode="before")
    @classmethod
    def _parse_date(cls, v: Any) -> datetime | None:
        if isinstance(v, str):
            return parse_syracuse_date(v)
        if isinstance(v, datetime):
            return v
        return None

    @property
    def has_overdue(self) -> bool:
        """True if the patron has one or more overdue loans."""
        return self.loans_late_count > 0

    @property
    def days_until_next_due(self) -> int | None:
        """Number of calendar days until the next scheduled item return date."""
        if not self.loans_next_handing_date:
            return None
        now_dt = datetime.now(self.loans_next_handing_date.tzinfo)
        return (self.loans_next_handing_date.date() - now_dt.date()).days


class PairedAccount(BaseModel):
    """Represents a linked family member's card account."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="Id")
    barcode: str = Field(alias="UserBarcode")
    display_name: str = Field(alias="UserDisplayName")
    user_unique_identifier: str = Field(alias="UserUniqueIdentifier")
    is_reciprocal: bool = Field(default=False, alias="IsReciprocal")
    state: int = Field(default=2, alias="State")
    modification_date: datetime | None = Field(default=None, alias="ModificationDate")

    @field_validator("modification_date", mode="before")
    @classmethod
    def _parse_mod_date(cls, v: Any) -> datetime | None:
        if isinstance(v, str):
            return parse_syracuse_date(v)
        if isinstance(v, datetime):
            return v
        return None


class AccountLoans(BaseModel):
    """Aggregate of account details, summary metrics, loans, and reservations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_name: str
    barcode: str
    unique_identifier: str | None = None
    summary: AccountSummary
    loans: Any  # "LoanCollection"
    bookings: Any = Field(default_factory=list)  # "BookingCollection"
