"""Data-driven engine for the v2.0 mapping tables (Phase 11 Map, MAP-03, D-08).

One parametrized test covers every row of every ``tables/phase_*.yaml`` file. The
marks (``v2_pending`` plus a strict xfail pinned to ``NotBuilt``) come from
``build_params``, driven by each table's ``pending`` flag, so this module never
imports a target at the top, never catches ``NotBuilt`` and never skips.

``PARAMS`` is built at import on purpose: a malformed table is a collection
error, not a quietly shrinking suite.
"""

import pytest

from tests.targets._support import build_params, load_tables, observe_row

PARAMS = build_params(load_tables())


@pytest.mark.parametrize(("table", "table_name", "row"), PARAMS)
def test_mapping_row(table, table_name, row):
    """The named target returns exactly the expected projection for this row's input."""
    observed = observe_row(table.tables[table_name]["target"], row)
    assert set(observed) == set(row["expect"])
    assert observed == row["expect"]
