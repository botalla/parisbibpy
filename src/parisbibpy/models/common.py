"""Common models and Syracuse envelope handling."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SyracuseEnvelope(BaseModel, Generic[T]):
    """Standard envelope returned by Archimed Syracuse WCF services."""

    d: T | None = None
    errors: list[Any] = Field(default_factory=list)
    message: str | None = None
    success: bool = True
