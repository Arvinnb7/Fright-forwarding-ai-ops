"""Tenant-scoped file storage for uploads and email attachments.

Two rules drive the design:

1. **Files are namespaced per organization.** A stored path always begins with
   ``org-<id>/``, and reads verify that the requesting organization owns the
   prefix — so a tampered ``file_path`` in the database cannot be used to read
   another customer's documents.
2. **The client never chooses the path.** Uploaded names are only kept as a
   display label; the name on disk is a generated UUID, which removes path
   traversal, collisions and unicode-filename problems in one step.

The backend is local disk (a mounted volume in production). Swapping it for S3
later means replacing this module only — callers hold an opaque relative path.
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

from app.core.config import settings


class StorageError(RuntimeError):
    """Raised when a file cannot be stored or read back."""


def storage_root() -> Path:
    root = Path(settings.storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_display_name(filename: str | None) -> str:
    """A human-readable label for the original file name.

    Only used for display and Content-Disposition — never to build a path.
    """
    name = unicodedata.normalize("NFKC", (filename or "").strip())
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return name[:255] or "attachment"


def _resolve(relative_path: str, org_id: int) -> Path:
    prefix = f"org-{org_id}/"
    if not relative_path.startswith(prefix):
        raise StorageError("File does not belong to this organization")
    root = storage_root()
    target = (root / relative_path).resolve()
    # Belt and braces: even with the prefix check, refuse anything that escapes.
    if not target.is_relative_to(root / f"org-{org_id}"):
        raise StorageError("Refusing to read outside the organization's storage")
    return target


def save_bytes(
    *, org_id: int, category: str, filename: str | None, content: bytes
) -> tuple[str, str]:
    """Store bytes and return ``(relative_path, display_name)``."""
    display_name = safe_display_name(filename)
    suffix = Path(display_name).suffix[:16]
    relative = f"org-{org_id}/{category}/{uuid.uuid4().hex}{suffix}"
    target = storage_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(content)
    except OSError as exc:  # pragma: no cover - disk full / permissions
        raise StorageError(f"Could not store file: {exc}") from exc
    return relative, display_name


def read_bytes(relative_path: str, org_id: int) -> bytes:
    target = _resolve(relative_path, org_id)
    if not target.is_file():
        raise StorageError("Stored file is missing")
    return target.read_bytes()


def delete_file(relative_path: str | None, org_id: int) -> None:
    """Best-effort removal; a missing file is not an error."""
    if not relative_path:
        return
    try:
        _resolve(relative_path, org_id).unlink(missing_ok=True)
    except StorageError:
        return
