"""Shared helper for serving stored files.

Freight paperwork routinely carries non-ASCII names (Persian, Arabic, Chinese),
which cannot go into an HTTP header verbatim — so the filename is sent both as
an ASCII fallback and as the RFC 5987 UTF-8 form.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import Response


def file_response(content: bytes, *, filename: str, content_type: str) -> Response:
    ascii_name = (
        filename.encode("ascii", "replace").decode("ascii").replace('"', "_") or "file"
    )
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    return Response(
        content=content,
        media_type=content_type or "application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            # The content is customer-supplied; never let a browser sniff it
            # into something executable.
            "X-Content-Type-Options": "nosniff",
        },
    )
