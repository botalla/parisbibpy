"""Booking (reservation) models and collection."""

from collections import UserList, defaultdict
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from parisbibpy.utils import parse_syracuse_date


class Booking(BaseModel):
    """Represents a patron reservation/booking."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default="", alias="Id")
    holding_id: str | None = Field(default=None, alias="HoldingId")
    record_id: str = Field(default="", alias="RecordId")
    title: str = Field(alias="Title")
    title_link: str | None = Field(default=None, alias="TitleLink")
    type_of_document: str = Field(default="Livre", alias="TypeOfDocument")
    pickup_location: str = Field(default="", alias="LocationLabel")
    state: str = Field(default="En attente", alias="State")
    is_available: bool = Field(default=False, alias="IsAvailable")
    booking_date: datetime | None = Field(default=None, alias="BookingDate")
    availability_date: datetime | None = Field(default=None, alias="AvailabilityDate")
    available_until: date | None = Field(default=None, alias="AvailableUntilDate")
    rank_in_queue: int | None = Field(default=None, alias="RankSort")
    can_cancel: bool = Field(default=True, alias="CanCancel")
    cannot_cancel_reason: str | None = Field(default=None, alias="CannotCancelReason")
    thumbnail_url: str | None = Field(default=None, alias="ThumbnailUrl")

    # Family context
    account_name: str | None = None
    account_barcode: str | None = None
    user_unique_identifier: str | None = None

    @field_validator("pickup_location", mode="before")
    @classmethod
    def _fallback_pickup_location(cls, v: Any, info: Any) -> str:
        if v:
            return str(v)
        data = info.data
        if holding_place := data.get("HoldingPlace"):
            return str(holding_place)
        if pickup_loc := data.get("PickupLocation"):
            return str(pickup_loc)
        return ""

    @field_validator("available_until", mode="before")
    @classmethod
    def _parse_until(cls, v: Any, info: Any) -> date | None:
        target = v
        if not target and "AvailableUntil" in info.data:
            target = info.data["AvailableUntil"]
        if isinstance(target, str):
            dt = parse_syracuse_date(target)
            return dt.date() if dt else None
        if isinstance(target, datetime):
            return target.date()
        if isinstance(target, date):
            return target
        return None

    @field_validator("booking_date", "availability_date", mode="before")
    @classmethod
    def _parse_datetimes(cls, v: Any) -> datetime | None:
        if isinstance(v, str):
            return parse_syracuse_date(v)
        if isinstance(v, datetime):
            return v
        return None

    @field_validator("rank_in_queue", mode="before")
    @classmethod
    def _parse_rank(cls, v: Any, info: Any) -> int | None:
        if v is not None:
            try:
                return int(v)
            except (ValueError, TypeError):
                pass
        data = info.data
        if "RankInQueue" in data and data["RankInQueue"] is not None:
            try:
                return int(data["RankInQueue"])
            except (ValueError, TypeError):
                pass
        if "Rank" in data and data["Rank"] is not None:
            try:
                return int(data["Rank"])
            except (ValueError, TypeError):
                pass
        return None


class BookingCollection(UserList[Booking]):
    """Collection of patron reservations with filtering and grouping."""

    @property
    def total_count(self) -> int:
        """Total number of bookings in collection."""
        return len(self.data)

    @property
    def ready_for_pickup(self) -> "BookingCollection":
        """All items currently available for pickup at library branches."""
        return BookingCollection([b for b in self.data if b.is_available])

    def group_by_pickup_library(self) -> dict[str, "BookingCollection"]:
        """Group bookings by pickup location library."""
        groups: dict[str, list[Booking]] = defaultdict(list)
        for b in self.data:
            groups[b.pickup_location].append(b)
        return {lib: BookingCollection(items) for lib, items in sorted(groups.items())}

    def group_by_account(self) -> dict[str, "BookingCollection"]:
        """Group bookings by family member account name."""
        groups: dict[str, list[Booking]] = defaultdict(list)
        for b in self.data:
            key = b.account_name or "Primary Account"
            groups[key].append(b)
        return {acc: BookingCollection(items) for acc, items in sorted(groups.items())}
