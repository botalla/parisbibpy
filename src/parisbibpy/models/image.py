"""Cover image models and data structures."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoverImage:
    """Represents retrieved raw image data and metadata for a library item's book cover.

    Attributes:
        data: Raw binary content of the image (e.g. JPEG, PNG, WEBP bytes).
        content_type: MIME type of the image (e.g. 'image/jpeg', 'image/png').
        url: The source URL from which the image was fetched.
    """

    data: bytes
    content_type: str = "image/jpeg"
    url: str = ""

    def __bytes__(self) -> bytes:
        """Allow direct bytes(cover) conversion."""
        return self.data

    def __len__(self) -> int:
        """Return the size in bytes of the image data."""
        return len(self.data)

    @property
    def size_bytes(self) -> int:
        """Return the length of the binary payload in bytes."""
        return len(self.data)

    def to_bytesio(self) -> io.BytesIO:
        """Return an in-memory BytesIO stream, ready for PIL.Image.open()."""
        return io.BytesIO(self.data)

    def to_base64(self) -> str:
        """Return base64-encoded string of the image."""
        return base64.b64encode(self.data).decode("ascii")

    def to_data_uri(self) -> str:
        """Return a data URI string (e.g. 'data:image/jpeg;base64,...')."""
        return f"data:{self.content_type};base64,{self.to_base64()}"

    def save(self, target: str | Path) -> None:
        """Save the raw image data to a file path."""
        Path(target).write_bytes(self.data)
