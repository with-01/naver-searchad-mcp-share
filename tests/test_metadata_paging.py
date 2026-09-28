import json

import pytest

from naver_searchad_mcp.server import get_operation_schema, list_operations, mcp, search_operations
from naver_searchad_mcp.spec import get_registry


@pytest.mark.parametrize("search", [False, True])
def test_operation_pages_reconstruct_the_complete_registry(search):
    expected = get_registry().search_operations("/") if search else get_registry().list_operations()
    query_page = (lambda **kwargs: search_operations("/", **kwargs)) if search else list_operations
    first = query_page()
    assert first["returned"] == 25
    assert first["total"] == len(expected)
    assert first["next_offset"] == 25
    observed = first["operations"]
    next_offset = first["next_offset"]
    while next_offset is not None:
        page = query_page(offset=next_offset)
        assert page["returned"] == len(page["operations"]) <= 25
        assert page["total"] == len(expected)
        observed += page["operations"]
        next_offset = page["next_offset"]
    assert observed == expected


def test_page_totals_are_computed_after_filtering():
    expected = get_registry().list_operations(section="ncc-heroes-ncc", tag="AdKeyword")
    page = list_operations(section="ncc-heroes-ncc", tag="AdKeyword", offset=2, limit=3)
    assert page["operations"] == expected[2:5]
    assert page["total"] == len(expected)
    assert page["returned"] == 3
    assert page["next_offset"] == 5


def test_empty_and_exhausted_pages_have_no_continuation():
    for page in (search_operations(""), search_operations("no-such-operation-fixture"), list_operations(offset=1000)):
        assert page["operations"] == []
        assert page["returned"] == 0
        assert page["next_offset"] is None


@pytest.mark.parametrize("kwargs", [{"offset": -1}, {"offset": True}, {"limit": 0}, {"limit": 101}, {"limit": 1.5}])
def test_metadata_pages_reject_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        list_operations(**kwargs)
    with pytest.raises(ValueError):
        search_operations("keyword", **kwargs)


def test_schema_tool_defaults_to_input_and_full_remains_available():
    key = "ncc-heroes-ncc:getByAdgroupIdUsingGET_1"
    compact = get_operation_schema(key)
    full = get_operation_schema(key, view="full")
    assert "raw" not in compact
    assert "responses" not in compact
    assert compact["parameters"] == full["parameters"]
    assert full == get_registry().get_operation_schema(key)
    size = lambda value: len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    assert size(compact) < size(full) / 2


def test_schema_tool_rejects_unknown_view():
    with pytest.raises(ValueError, match="view"):
        get_operation_schema("ncc-heroes-ncc:getByAdgroupIdUsingGET_1", view="unknown")


@pytest.mark.asyncio
async def test_mcp_metadata_calls_preserve_structured_and_text_content():
    for name, arguments in (
        ("list_operations", {"limit": 2}),
        ("search_operations", {"query": "keyword", "limit": 2}),
        ("get_operation_schema", {"operation_key": "ncc-heroes-ncc:getByAdgroupIdUsingGET_1"}),
    ):
        content, structured = await mcp.call_tool(name, arguments)
        assert json.loads(content[0].text) == structured
        if name == "get_operation_schema":
            assert "raw" not in structured
            assert "responses" not in structured
        else:
            assert structured["returned"] == 2
            assert structured["next_offset"] == 2
