"""File storage — the layer that must not let one customer read another's files."""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.storage import (
    StorageError,
    delete_file,
    read_bytes,
    safe_display_name,
    save_bytes,
)


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))


def test_round_trip():
    path, name = save_bytes(
        org_id=7, category="documents", filename="packing-list.pdf", content=b"%PDF fake"
    )

    assert path.startswith("org-7/documents/")
    assert name == "packing-list.pdf"
    assert read_bytes(path, 7) == b"%PDF fake"


def test_another_organization_cannot_read_the_file():
    path, _ = save_bytes(
        org_id=7, category="documents", filename="bl.pdf", content=b"confidential"
    )

    with pytest.raises(StorageError):
        read_bytes(path, 8)


def test_traversal_in_a_stored_path_is_refused():
    """Defence in depth: even a tampered database row cannot escape the tenant's
    directory."""
    save_bytes(org_id=8, category="documents", filename="theirs.pdf", content=b"secret")

    for hostile in (
        "org-7/../org-8/documents/theirs.pdf",
        "org-7/../../etc/passwd",
        "../org-8/documents/theirs.pdf",
        "/etc/passwd",
    ):
        with pytest.raises(StorageError):
            read_bytes(hostile, 7)


def test_uploaded_name_never_becomes_the_path():
    path, name = save_bytes(
        org_id=3,
        category="documents",
        filename="../../../etc/passwd",
        content=b"x",
    )

    assert path.startswith("org-3/documents/")
    assert ".." not in path
    assert name == "passwd"
    assert read_bytes(path, 3) == b"x"


def test_identical_names_do_not_overwrite_each_other():
    first, _ = save_bytes(org_id=1, category="documents", filename="bl.pdf", content=b"one")
    second, _ = save_bytes(org_id=1, category="documents", filename="bl.pdf", content=b"two")

    assert first != second
    assert read_bytes(first, 1) == b"one"
    assert read_bytes(second, 1) == b"two"


def test_unicode_filenames_are_preserved_for_display():
    _, name = save_bytes(
        org_id=1, category="email", filename="بارنامه.pdf", content=b"x"
    )

    assert name == "بارنامه.pdf"


def test_missing_file_is_reported_not_silently_empty():
    with pytest.raises(StorageError):
        read_bytes("org-1/documents/nonexistent.pdf", 1)


def test_delete_is_idempotent_and_scoped():
    path, _ = save_bytes(org_id=1, category="documents", filename="a.pdf", content=b"x")

    delete_file(path, 2)  # wrong tenant: refused, but silently
    assert read_bytes(path, 1) == b"x"

    delete_file(path, 1)
    delete_file(path, 1)  # already gone
    delete_file(None, 1)
    with pytest.raises(StorageError):
        read_bytes(path, 1)


def test_display_name_strips_control_characters():
    assert safe_display_name("in\x00voice\r\n.pdf") == "invoice.pdf"
    assert safe_display_name("") == "attachment"
    assert safe_display_name(None) == "attachment"
