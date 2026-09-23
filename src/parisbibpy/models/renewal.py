"""Renewal reporting models for batch operations."""

from pydantic import BaseModel, Field

from parisbibpy.models.loan import Loan


class RenewalFailure(BaseModel):
    """Details of a failed loan renewal attempt."""

    loan: Loan
    reason: str


class RenewalReport(BaseModel):
    """Summary report of a batch renewal operation across accounts."""

    succeeded: list[Loan] = Field(default_factory=list)
    failed: list[RenewalFailure] = Field(default_factory=list)
    skipped_not_renewable: list[Loan] = Field(default_factory=list)

    @property
    def total_attempted(self) -> int:
        """Total number of renewal API calls made."""
        return len(self.succeeded) + len(self.failed)

    @property
    def is_all_successful(self) -> bool:
        """True if every attempted renewal succeeded."""
        return len(self.failed) == 0 and len(self.succeeded) > 0
