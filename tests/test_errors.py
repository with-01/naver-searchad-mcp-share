from naver_searchad_mcp.errors import get_error_code, load_error_codes, search_error_codes


def test_error_code_map_loads_known_code():
    mapping = load_error_codes()
    assert "1001" in mapping
    assert mapping["1001"]["english"] == "Cannot find the requested resource(ID or entity)."


def test_get_error_code_splits_multiple_code_cell():
    assert get_error_code("1004")["found"] is True
    assert get_error_code("1005")["found"] is True
    assert get_error_code("1004")["codes_cell"] == "1004,1005"


def test_get_error_code_unknown():
    assert get_error_code("NOPE") == {"found": False, "code": "NOPE"}


def test_search_error_codes_korean_substring():
    results = search_error_codes("그룹")
    assert results, "한국어 부분 매칭이 동작해야 한다"
    for entry in results:
        assert "그룹" in entry["korean"] or "그룹" in entry["english"].lower()


def test_search_error_codes_english_substring_case_insensitive():
    upper = search_error_codes("GROUP")
    lower = search_error_codes("group")
    assert upper and lower
    assert {e["line_no"] for e in upper} == {e["line_no"] for e in lower}


def test_search_error_codes_empty_returns_empty_list():
    assert search_error_codes("") == []
    assert search_error_codes("   ") == []


def test_search_error_codes_dedupes_multi_code_lines():
    """Lines with codes_cell like '1004,1005' must appear once in search results."""
    # Pick a fragment that appears in such a line if any exists
    results = search_error_codes("Cannot find the requested resource")
    line_nos = [e["line_no"] for e in results]
    assert len(line_nos) == len(set(line_nos)), "duplicate line_no in search results"
