"""Existence checks for migrations.

Why this exists: revision ``0001_baseline`` builds the schema from the live ORM
metadata (``Base.metadata.create_all``). That makes a *fresh* database arrive
already carrying every table and column the current models define — including
ones introduced by later revisions. An *existing* database, however, only has
what its metadata contained when it was first migrated.

So both states must be supported by every revision after the baseline:

* fresh install  → the object usually exists already; the step is a no-op;
* upgrade path   → the object is missing and must actually be created.

Writing later migrations through these helpers keeps both paths working.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def has_table(table: str) -> bool:
    return table in _inspector().get_table_names()


def has_column(table: str, column: str) -> bool:
    if not has_table(table):
        return False
    return column in {c["name"] for c in _inspector().get_columns(table)}


def has_index(table: str, index: str) -> bool:
    if not has_table(table):
        return False
    return index in {i["name"] for i in _inspector().get_indexes(table)}


def has_constraint(table: str, name: str) -> bool:
    if not has_table(table):
        return False
    insp = _inspector()
    names = {c["name"] for c in insp.get_unique_constraints(table)}
    names |= {f["name"] for f in insp.get_foreign_keys(table)}
    check = insp.get_check_constraints(table)
    names |= {c["name"] for c in check}
    return name in names


def unique_constraints_on(table: str, column: str) -> list[str]:
    """Names of single-column unique constraints covering `column`."""
    if not has_table(table):
        return []
    return [
        uq["name"]
        for uq in _inspector().get_unique_constraints(table)
        if uq["column_names"] == [column] and uq["name"]
    ]


def unique_indexes_on(table: str, column: str) -> list[str]:
    """Names of single-column unique *indexes* covering `column`."""
    if not has_table(table):
        return []
    return [
        ix["name"]
        for ix in _inspector().get_indexes(table)
        if ix["column_names"] == [column] and ix.get("unique") and ix["name"]
    ]
