"""사용설명서 스킬 (SKILL.md + references/) 로딩 검증."""
from naver_searchad_mcp.usage_guide import (
    _parse_frontmatter,
    get_chapter,
    load_skill_index,
    references_dir,
    skill_dir,
)


EXPECTED_CHAPTERS = {
    "tools-cheatsheet",
    "workflow-patterns",
    "sections-tags-map",
    "large-response",
    "write-safety",
    "enums-reference",
    "response-shapes",
    "pitfalls",
    "manual-overrides",
}


def test_skill_dir_and_skill_md_exist():
    assert skill_dir().is_dir()
    assert (skill_dir() / "SKILL.md").is_file()
    assert references_dir().is_dir()


def test_load_skill_index_returns_frontmatter_body_and_chapters():
    idx = load_skill_index()
    skill = idx["skill"]
    assert skill["name"] == "naver-searchad-usage"
    assert skill["description"]
    assert skill["when_to_use"]
    assert skill["body"]  # SKILL.md 본문이 비어있지 않음

    topics = {ch["topic"] for ch in idx["chapters"]}
    assert EXPECTED_CHAPTERS.issubset(topics), f"missing chapters: {EXPECTED_CHAPTERS - topics}"


def test_load_skill_index_chapter_metadata_complete():
    idx = load_skill_index()
    for ch in idx["chapters"]:
        assert ch["topic"]
        assert ch["title"]
        assert ch["description"]


def test_get_chapter_index_returns_skill_body():
    out = get_chapter()
    assert out["found"] is True
    assert out["topic"] == "index"
    assert "skill" in out
    assert out["skill"]["body"]
    assert "chapters" in out


def test_get_chapter_index_via_explicit_keyword():
    for keyword in (None, "", "index", "INDEX", "skill"):
        out = get_chapter(keyword)
        assert out["topic"] == "index"
        assert out["found"] is True


def test_get_chapter_each_known_topic_loads_body():
    for topic in EXPECTED_CHAPTERS:
        out = get_chapter(topic)
        assert out["found"] is True, f"chapter {topic} not found"
        assert out["topic"] == topic
        assert out["title"]
        assert out["body"], f"chapter {topic} body is empty"


def test_get_chapter_unknown_topic_returns_available_list():
    out = get_chapter("does-not-exist")
    assert out["found"] is False
    assert out["topic"] == "does-not-exist"
    assert "available" in out
    assert EXPECTED_CHAPTERS.issubset(set(out["available"]))


def test_frontmatter_parser_handles_basic_yaml():
    text = """---
name: foo
description: bar baz
when_to_use: "when x"
---

본문 내용
"""
    fm, body = _parse_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["description"] == "bar baz"
    assert fm["when_to_use"] == "when x"
    assert "본문 내용" in body


def test_frontmatter_parser_no_frontmatter_returns_full_body():
    text = "no frontmatter here"
    fm, body = _parse_frontmatter(text)
    assert fm == {}
    assert body == text


def test_get_usage_guide_tool_routes_to_chapter():
    """server.py 의 get_usage_guide 도구가 usage_guide.get_chapter 와 동일 결과를 반환."""
    from naver_searchad_mcp.server import get_usage_guide
    direct = get_chapter("large-response")
    via_tool = get_usage_guide("large-response")
    assert direct == via_tool


def test_guide_rejects_paths_outside_chapter_names():
    for topic in ("../../../README", "../SKILL", "/tmp/example", "..\\SKILL"):
        out = get_chapter(topic)
        assert out["found"] is False
        assert "body" not in out


def test_guide_prefers_packaged_resources(monkeypatch, tmp_path):
    from naver_searchad_mcp import usage_guide

    package = tmp_path / "naver_searchad_mcp"
    guide = package / "data" / "usage-guide"
    guide.mkdir(parents=True)
    monkeypatch.setattr(usage_guide, "__file__", str(package / "usage_guide.py"))
    assert usage_guide.skill_dir() == guide
