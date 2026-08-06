from server import content


def test_load_content_defaults_when_absent(monkeypatch, tmp_path):
    """No content.config.json -> the built-in Travel copy, not an error."""
    monkeypatch.setenv("CONTENT_CONFIG_FILE", str(tmp_path / "nope.json"))
    assert content.load_content() == content.DEFAULT_CONTENT


def test_load_content_failsoft_on_bad_json(monkeypatch, tmp_path):
    bad = tmp_path / "content.config.json"
    bad.write_text("{ not valid json")
    monkeypatch.setenv("CONTENT_CONFIG_FILE", str(bad))
    assert content.load_content() == content.DEFAULT_CONTENT


def test_load_content_failsoft_on_non_object(monkeypatch, tmp_path):
    bad = tmp_path / "content.config.json"
    bad.write_text("[1, 2, 3]")
    monkeypatch.setenv("CONTENT_CONFIG_FILE", str(bad))
    assert content.load_content() == content.DEFAULT_CONTENT


def test_partial_content_merges_over_defaults(monkeypatch, tmp_path):
    """A config that sets only the hero keeps the default KPI tiles."""
    partial = tmp_path / "content.config.json"
    partial.write_text('{"hero": {"title": "Vendor Performance"}}')
    monkeypatch.setenv("CONTENT_CONFIG_FILE", str(partial))
    c = content.load_content()
    assert c["hero"]["title"] == "Vendor Performance"
    # Subtitle inherited from defaults rather than dropped.
    assert c["hero"]["subtitle"] == content.DEFAULT_CONTENT["hero"]["subtitle"]
    assert len(c["kpis"]) == len(content.DEFAULT_CONTENT["kpis"])


def test_kpi_list_is_replaced_not_merged(monkeypatch, tmp_path):
    """A vertical defining 2 tiles must NOT inherit a 3rd/4th from Travel."""
    cfg = tmp_path / "content.config.json"
    cfg.write_text(
        '{"kpis": ['
        '{"key": "spend", "label": "Net Sales", "format": "currency"},'
        '{"key": "margin", "label": "Gross Margin", "format": "currency"}'
        "]}"
    )
    monkeypatch.setenv("CONTENT_CONFIG_FILE", str(cfg))
    c = content.load_content()
    assert [k["label"] for k in c["kpis"]] == ["Net Sales", "Gross Margin"]


def test_empty_kpi_list_falls_back_to_defaults(monkeypatch, tmp_path):
    """An empty list is treated as "unset" so the page is never tile-less."""
    cfg = tmp_path / "content.config.json"
    cfg.write_text('{"kpis": []}')
    monkeypatch.setenv("CONTENT_CONFIG_FILE", str(cfg))
    assert content.load_content()["kpis"] == content.DEFAULT_CONTENT["kpis"]
