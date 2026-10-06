"""KPI_MEASURES parsing — the seam that points one build at any vertical's metric view.

Measure and key names are interpolated into SQL, so the parser must reject anything that
isn't a plain identifier.
"""
from server.routes.kpis import _DEFAULT_MEASURES, _parse_measures


def test_none_and_empty_use_travel_defaults():
    assert _parse_measures(None) == _DEFAULT_MEASURES
    assert _parse_measures("") == _DEFAULT_MEASURES
    assert _parse_measures("   ") == _DEFAULT_MEASURES


def test_parses_retail_measures():
    got = _parse_measures("net_sales:spend,gross_margin:margin,units_sold:units")
    assert got == [
        ("net_sales", "spend"),
        ("gross_margin", "margin"),
        ("units_sold", "units"),
    ]


def test_tolerates_surrounding_whitespace():
    assert _parse_measures(" net_sales : spend ,  gross_margin:margin ") == [
        ("net_sales", "spend"),
        ("gross_margin", "margin"),
    ]


def test_skips_entries_without_a_key():
    # "bogus" has no ":key" and is dropped; the valid pair survives.
    assert _parse_measures("net_sales:spend,bogus") == [("net_sales", "spend")]


def test_all_malformed_falls_back_to_defaults():
    assert _parse_measures("bogus") == _DEFAULT_MEASURES
    assert _parse_measures(",,,") == _DEFAULT_MEASURES


def test_rejects_sql_injection_attempts():
    """Anything that isn't a bare identifier is refused, not interpolated."""
    for hostile in (
        "a;DROP TABLE x:k",
        "net_sales:spend); DELETE FROM t--",
        "1 OR 1=1:k",
        "sum(x):k",
        "a.b:k",
        "a-b:k",
    ):
        assert _parse_measures(hostile) == _DEFAULT_MEASURES, hostile


def test_partially_hostile_input_keeps_only_safe_pairs():
    assert _parse_measures("net_sales:spend,a;DROP:k") == [("net_sales", "spend")]
