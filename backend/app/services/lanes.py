"""Lane identity — how the system recognises "we have quoted this before".

Answering an enquiry in thirty minutes is only possible if the rate is already
known. Waiting for a carrier to reply by email puts the clock back where it
was, so a rate quoted once has to be findable the next time the same lane comes
in. That requires deciding when two lanes are *the same* lane.

The normalisation here is deliberately conservative. Fuzzy place matching would
happily decide that Dubai and Jebel Ali, or Shanghai and Ningbo, are close
enough — and a wrong rate shown as a suggestion becomes a wrong price shown to
a customer. So only unambiguous noise is removed (case, punctuation, a trailing
country, "Port of" prefixes), and anything else must match exactly. Suggestions
that are merely on the same route but differ in mode or equipment are returned
separately and clearly labelled, never merged with exact matches.
"""
from __future__ import annotations

import re
import unicodedata

# Words that carry no routing information. Removed only as whole tokens.
_NOISE_TOKENS = {"port", "of", "seaport", "airport", "terminal"}

# Equipment written a dozen ways on rate sheets; the digits + type are what
# matter. "1x40HC", "40'HC", "40 hc" all mean the same box.
_CONTAINER_PATTERN = re.compile(r"^\s*\d+\s*[x×]\s*", re.IGNORECASE)


def _strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def normalize_place(value: str | None) -> str:
    """Reduce a place name to a comparable form.

    ``"Port of Shanghai, China"`` and ``"SHANGHAI"`` both become ``"shanghai"``;
    ``"Jebel Ali"`` never becomes ``"dubai"``.
    """
    if not value:
        return ""
    text = _strip_accents(str(value)).casefold()
    # "Shanghai, China" → "shanghai"; "Dubai (Jebel Ali)" → "dubai"
    text = text.split(",")[0]
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    tokens = [token for token in text.split() if token not in _NOISE_TOKENS]
    return " ".join(tokens)


def normalize_equipment(value: str | None) -> str:
    """Normalise container / service type. Empty means 'unspecified'."""
    if not value:
        return ""
    text = _CONTAINER_PATTERN.sub("", str(value))
    text = _strip_accents(text).casefold()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _mode_value(mode) -> str:
    """Accepts the TransportMode enum or a plain string."""
    if mode is None:
        return ""
    return str(getattr(mode, "value", mode)).casefold().strip()


def route_key(origin: str | None, destination: str | None) -> str | None:
    """Origin → destination only. The looser 'same route' grouping."""
    start, end = normalize_place(origin), normalize_place(destination)
    if not start or not end:
        return None
    return f"{start}>{end}"


def lane_key(
    origin: str | None,
    destination: str | None,
    mode=None,
    equipment: str | None = None,
) -> str | None:
    """The full lane identity: route + mode + equipment.

    Returns None when the route is unknown — an RFQ missing its origin or
    destination has no lane, and must not silently match everything.
    """
    route = route_key(origin, destination)
    if route is None:
        return None
    return f"{route}|{_mode_value(mode)}|{normalize_equipment(equipment)}"


def describe_lane(
    origin: str | None,
    destination: str | None,
    mode=None,
    equipment: str | None = None,
) -> str:
    """Human-readable lane, for the UI and drafts."""
    parts = [f"{origin or '?'} → {destination or '?'}"]
    detail = " ".join(
        str(getattr(item, "value", item))
        for item in (mode, equipment)
        if item
    )
    if detail:
        parts.append(f"({detail})")
    return " ".join(parts)


def lane_fields(obj) -> dict[str, object]:
    """Lane columns copied from an RFQ onto a rate, so history stays stable
    even if the RFQ is edited afterwards."""
    return {
        "origin": obj.origin,
        "destination": obj.destination,
        "transport_mode": obj.transport_mode,
        "container_type": obj.container_type,
        "lane_key": lane_key(
            obj.origin, obj.destination, obj.transport_mode, obj.container_type
        ),
        "route_key": route_key(obj.origin, obj.destination),
    }
