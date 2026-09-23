"""Loan models, collections, and library trip planning."""

from collections import UserList, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parisbibpy.utils import parse_syracuse_date


class Loan(BaseModel):
    """Represents a borrowed item from the library."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default="", alias="Id")
    holding_id: str = Field(alias="HoldingId")
    record_id: str = Field(alias="RecordId")
    title: str = Field(alias="Title")
    type_of_document: str = Field(alias="TypeOfDocument")
    location: str = Field(alias="Location")
    when_back: datetime = Field(alias="WhenBack")
    state: str = Field(default="En cours", alias="State")
    is_late: bool = Field(default=False, alias="IsLate")
    is_soon_late: bool = Field(default=False, alias="IsSoonLate")
    can_renew: bool = Field(default=False, alias="CanRenew")
    cannot_renew_reason: str | None = Field(default=None, alias="CannotRenewReason")
    thumbnail_url: str | None = Field(default=None, alias="ThumbnailUrl")
    title_link: str | None = Field(default=None, alias="TitleLink")
    is_renewal: bool = Field(default=False)

    # Family context fields
    account_name: str | None = None
    account_barcode: str | None = None
    user_unique_identifier: str | None = None

    @field_validator("when_back", mode="before")
    @classmethod
    def _parse_when_back(cls, v: Any) -> datetime | None:
        if isinstance(v, str):
            return parse_syracuse_date(v)
        if isinstance(v, datetime):
            return v
        return None

    @field_validator("id", mode="before")
    @classmethod
    def _default_id(cls, v: Any, info: Any) -> str:
        if not v and "HoldingId" in info.data:
            return str(info.data["HoldingId"])
        return str(v) if v is not None else ""

    @property
    def is_renewable(self) -> bool:
        """Alias for can_renew."""
        return self.can_renew

    @property
    def due_date(self) -> date:
        """Calendar due date."""
        return self.when_back.date()

    @property
    def days_remaining(self) -> int:
        """Number of calendar days remaining until item is due (negative if overdue)."""
        now_dt = datetime.now(self.when_back.tzinfo)
        return (self.due_date - now_dt.date()).days

    def to_syracuse_dict(self) -> dict[str, Any]:
        """Convert Loan model back to Syracuse JSON dictionary for RenewLoans requests."""
        offset_str = "+0000"
        if self.when_back.tzinfo:
            offset = self.when_back.utcoffset()
            if offset is not None:
                total_seconds = int(offset.total_seconds())
                sign = "+" if total_seconds >= 0 else "-"
                hours = abs(total_seconds) // 3600
                minutes = (abs(total_seconds) % 3600) // 60
                offset_str = f"{sign}{hours:02d}{minutes:02d}"

        timestamp_ms = int(self.when_back.timestamp() * 1000)
        return {
            "Id": self.id or self.holding_id,
            "HoldingId": self.holding_id,
            "RecordId": self.record_id,
            "RecordBase": "SYRACUSE",
            "Title": self.title,
            "TypeOfDocument": self.type_of_document,
            "Location": self.location,
            "WhenBack": f"/Date({timestamp_ms}{offset_str})/",
            "State": self.state,
            "IsLate": self.is_late,
            "IsSoonLate": self.is_soon_late,
            "CanRenew": self.can_renew,
            "CannotRenewReason": self.cannot_renew_reason,
            "ThumbnailUrl": self.thumbnail_url,
            "TitleLink": self.title_link,
            "AdditionalProperties": {
                "IsRenewal": "1" if self.is_renewal else "0",
            },
        }


class LibraryTrip(BaseModel):
    """Represents a drop-off visit to a specific library branch."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    library: str
    loans: "LoanCollection"
    earliest_due_date: date | None = None
    days_until_first_due: int | None = None
    overdue_count: int = 0
    total_items: int = 0

    def has_urgency(self, within_days: int = 7) -> bool:
        """Check if trip requires attention (items overdue or due within N days)."""
        if self.overdue_count > 0:
            return True
        if self.days_until_first_due is not None:
            return self.days_until_first_due <= within_days
        return False


class LoanCollection(UserList[Loan]):
    """Rich domain list of loans with multi-dimensional grouping and trip planning."""

    @property
    def total_count(self) -> int:
        """Total number of items in this collection."""
        return len(self.data)

    @property
    def overdue(self) -> "LoanCollection":
        """All items currently overdue."""
        return LoanCollection([loan for loan in self.data if loan.is_late])

    @property
    def overdue_count(self) -> int:
        """Number of overdue items."""
        return len(self.overdue)

    @property
    def renewable(self) -> "LoanCollection":
        """All items currently eligible for renewal."""
        return LoanCollection([loan for loan in self.data if loan.can_renew])

    @property
    def renewable_count(self) -> int:
        """Number of renewable items."""
        return len(self.renewable)

    @property
    def earliest_due_date(self) -> date | None:
        """Earliest due date among all items in collection."""
        if not self.data:
            return None
        return min(loan.due_date for loan in self.data)

    def due_soon(self, days: int = 5) -> "LoanCollection":
        """Items due within N days or already overdue."""
        return LoanCollection([loan for loan in self.data if loan.days_remaining <= days])

    def filter(
        self,
        due_within_days: int | None = None,
        is_renewable: bool | None = None,
        is_late: bool | None = None,
        library: str | None = None,
        doc_type: str | None = None,
        account_name: str | None = None,
    ) -> "LoanCollection":
        """Filter loans by any combination of criteria."""
        items = list(self.data)
        if due_within_days is not None:
            items = [item for item in items if item.days_remaining <= due_within_days]
        if is_renewable is not None:
            items = [item for item in items if item.can_renew == is_renewable]
        if is_late is not None:
            items = [item for item in items if item.is_late == is_late]
        if library is not None:
            items = [item for item in items if library.lower() in item.location.lower()]
        if doc_type is not None:
            items = [item for item in items if doc_type.lower() == item.type_of_document.lower()]
        if account_name is not None:
            items = [
                item
                for item in items
                if item.account_name and account_name.lower() in item.account_name.lower()
            ]
        return LoanCollection(items)

    def group_by_library(self) -> dict[str, "LoanCollection"]:
        """Group loans by physical library branch."""
        groups: dict[str, list[Loan]] = defaultdict(list)
        for loan in self.data:
            groups[loan.location].append(loan)
        return {lib: LoanCollection(items) for lib, items in sorted(groups.items())}

    def group_by_account(self) -> dict[str, "LoanCollection"]:
        """Group loans by family member / cardholder account name."""
        groups: dict[str, list[Loan]] = defaultdict(list)
        for loan in self.data:
            key = loan.account_name or "Primary Account"
            groups[key].append(loan)
        return {acc: LoanCollection(items) for acc, items in sorted(groups.items())}

    def group_by_type(self) -> dict[str, "LoanCollection"]:
        """Group loans by document type (BD, Livre, Jeu de société, etc.)."""
        groups: dict[str, list[Loan]] = defaultdict(list)
        for loan in self.data:
            groups[loan.type_of_document].append(loan)
        return {dt: LoanCollection(items) for dt, items in sorted(groups.items())}

    def sorted_by_due_date(self, descending: bool = False) -> "LoanCollection":
        """Return loans sorted by due date."""
        return LoanCollection(
            sorted(self.data, key=lambda l: l.when_back, reverse=descending)
        )

    def plan_library_trips(self) -> list[LibraryTrip]:
        """Group loans by library and sort trips by urgency of due dates."""
        trips: list[LibraryTrip] = []
        for lib, branch_loans in self.group_by_library().items():
            earliest = branch_loans.earliest_due_date
            days_until: int | None = None
            if earliest:
                today = datetime.now(timezone.utc).date()
                days_until = (earliest - today).days

            trips.append(
                LibraryTrip(
                    library=lib,
                    loans=branch_loans,
                    earliest_due_date=earliest,
                    days_until_first_due=days_until,
                    overdue_count=branch_loans.overdue_count,
                    total_items=branch_loans.total_count,
                )
            )

        # Prioritize: overdue branches first, then branches with closest due date
        return sorted(
            trips,
            key=lambda t: (
                0 if t.overdue_count > 0 else 1,
                t.days_until_first_due if t.days_until_first_due is not None else 9999,
            ),
        )
