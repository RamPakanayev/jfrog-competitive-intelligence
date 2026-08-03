from app.config import Settings
from app.config_data import AppConfig


def cfg() -> AppConfig:
    return AppConfig.load(Settings(_env_file=None).config_dir)


def test_competitors_load_core5():
    c = cfg()
    slugs = [comp["slug"] for comp in c.competitors]
    assert slugs == ["sonatype", "gitlab", "github", "docker", "snyk"]
    for comp in c.competitors:
        assert comp["name"] and comp["color"]
        assert isinstance(comp["sources"].get("rss", []), list)
        base = comp["battlecard_base"]
        assert base["strengths"] and base["weaknesses"] and base["how_jfrog_wins"]


def test_industry_feeds_load():
    c = cfg()
    assert len(c.industry_feeds) >= 3
    assert all(f["url"].startswith("http") for f in c.industry_feeds)


def test_capabilities_and_matrix():
    c = cfg()
    assert len(c.jfrog_capabilities) >= 8
    assert all(cap["name"] and cap["notes"] for cap in c.jfrog_capabilities)
    assert c.matrix["vendors"][0] == "jfrog"
    caps = {r["capability"] for r in c.matrix["rows"]}
    assert len(caps) == len(c.matrix["rows"])  # no duplicate rows
    for row in c.matrix["rows"]:
        assert set(row["values"]) == set(c.matrix["vendors"])
    # matrix must stay in sync with the competitor list (config-as-code maintenance path)
    assert set(c.matrix["vendors"]) - {"jfrog"} == set(c.slugs())
    assert set(c.matrix["vendor_labels"]) == set(c.matrix["vendors"])


def test_capabilities_text_grounds_delta_analysis():
    text = cfg().capabilities_text()
    assert "Xray contextual analysis" in text
    assert "Artifactory universal repository" in text
    assert text.startswith("- ")


def test_slug_helpers():
    c = cfg()
    assert c.competitor_by_slug("snyk")["name"] == "Snyk"
    assert c.slugs() == ["sonatype", "gitlab", "github", "docker", "snyk"]
