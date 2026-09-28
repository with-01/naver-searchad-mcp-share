from naver_searchad_mcp.spec import (
    EXPECTED_ENDPOINT_COUNTS,
    get_registry,
    list_tags,
    search_operations,
    validate_official_spec,
)


USER_25_OFFICIAL_TAGS = {
    "AdExtension", "Adgroup", "Ad", "BrandNewContract", "Campaign",
    "BusinessChannel", "Criterion", "AdKeyword", "LabelRef", "Label",
    "ManagedKeyword", "ProductGroup", "SharedBudget", "Target", "TimeContract",
    "IpExclusion", "Bizmoney", "AdAccounts", "ManagerAccounts", "StatReport",
    "Stat", "MasterReport", "RelKwdStat", "Estimate", "InspectHistory",
}


def test_endpoint_counts_match_official_sections():
    result = validate_official_spec()
    assert result["ok"], result["problems"]
    assert result["section_counts"] == EXPECTED_ENDPOINT_COUNTS
    assert result["total_operations"] == sum(EXPECTED_ENDPOINT_COUNTS.values()) == 127


def test_operation_keys_are_unique_and_prefixed_by_section():
    registry = get_registry()
    keys = list(registry.operations)
    assert len(keys) == len(set(keys))
    for key, operation in registry.operations.items():
        assert key.startswith(operation.section + ":")
        assert operation.method in {"GET", "POST", "PUT", "DELETE", "PATCH"}
        assert operation.path.startswith("/")


def test_list_sections_has_stable_order_and_counts():
    registry = get_registry()
    sections = registry.list_sections()
    assert [s["section"] for s in sections] == list(EXPECTED_ENDPOINT_COUNTS)
    assert {s["section"]: s["endpoint_count"] for s in sections} == EXPECTED_ENDPOINT_COUNTS


def test_get_operation_schema_contains_official_details():
    registry = get_registry()
    ops = registry.list_operations(section="ncc-report")
    stat = next(op for op in ops if op["operationId"] == "getSingleEntityStatUsingGET")
    schema = registry.get_operation_schema(stat["operation_key"])
    assert schema["method"] == "GET"
    assert schema["path"].startswith("/api/stats")
    assert schema["parameters"]
    assert schema["raw"]["operationId"] == "getSingleEntityStatUsingGET"


def test_list_tags_includes_all_25_official_user_tags():
    tags = {t["tag"] for t in list_tags()}
    missing = USER_25_OFFICIAL_TAGS - tags
    assert not missing, f"Missing official user tags: {sorted(missing)}"


def test_list_tags_returns_operation_count_and_sections():
    tags = list_tags()
    assert tags, "registry must expose at least one tag"
    for entry in tags:
        assert isinstance(entry["tag"], str) and entry["tag"]
        assert isinstance(entry["operation_count"], int) and entry["operation_count"] >= 1
        assert isinstance(entry["sections"], list) and entry["sections"]


def test_list_operations_filter_by_tag_returns_only_matching():
    ops = get_registry().list_operations(tag="Campaign")
    assert ops, "Campaign tag must have at least one op"
    for op in ops:
        assert "Campaign" in op["tags"]
    # Sanity: distinct from full set
    assert len(ops) < 127


def test_list_operations_filter_by_section_and_tag_combined():
    ops = get_registry().list_operations(section="ncc-heroes-ncc", tag="Adgroup")
    assert ops
    for op in ops:
        assert op["section"] == "ncc-heroes-ncc"
        assert "Adgroup" in op["tags"]


def test_search_operations_matches_summary_or_description():
    results = search_operations("campaign")
    assert results, "search 'campaign' must hit Campaign-related ops"
    # Case-insensitive
    results_upper = search_operations("CAMPAIGN")
    assert {r["operation_key"] for r in results} == {r["operation_key"] for r in results_upper}


def test_search_operations_empty_query_returns_empty_list():
    assert search_operations("") == []
    assert search_operations("   ") == []


def test_search_operations_matches_korean_in_description():
    # spec의 description에 흔히 등장하는 한글 단어. modifyBidWeight 등에 "입찰가" 표현 존재.
    results = search_operations("입찰")
    assert results, "한글 부분 매칭이 동작해야 한다"


def test_legacy_keys_keep_the_same_paths_after_upstream_operation_id_reuse():
    registry = get_registry()
    group = registry.get_operation("ncc-heroes-ncc:getUsingGET_16")
    assert group.path == "/api/ncc/adgroups/{adgroupId}"
    assert group.operation_id == "getUsingGET_18"
    channels = registry.get_operation("ncc-heroes-ncc:getUsingGET_18")
    assert channels.path == "/api/ncc/channels"
    assert channels.operation_id == "getUsingGET_22"
    partial = registry.get_operation("ncc-heroes-ncc:modifyUsingPUT_10")
    assert partial.path == "/api/ncc/adgroups/{adgroupId}{?fields}"
    assert partial.operation_id == "modifyUsingPUT_11"
    complete = registry.get_operation("ncc-heroes-ncc:modifyUsingPUT_11")
    assert complete.path == "/api/ncc/adgroups/{adgroupId}"
    assert complete.operation_id == "modifyUsingPUT_10"


def test_schema_includes_transitively_referenced_definitions():
    schema = get_registry().get_operation_schema("ncc-heroes-ncc:addUsingPOST_6")
    assert schema["requestBody"]["$ref"] == "#/definitions/AdgroupRequest"
    definitions = schema["definitions"]
    assert "AdgroupRequest" in definitions
    assert "AutobidStrategyRequest" in definitions
    assert "aiAdsOptIn" in definitions["AdgroupRequest"]["properties"]
    assert "CampaignRequest" not in definitions


def test_new_managed_keyword_post_is_registered():
    operation = get_registry().get_operation("ncc-heroes-ncc:postKeywordAttributesUsingPOST")
    assert operation.method == "POST"
    assert operation.path == "/api/ncc/managedKeyword"


def test_input_schema_preserves_request_constraints_and_transitive_definitions():
    registry = get_registry()
    key = "ncc-heroes-ncc:addUsingPOST_6"
    schema = registry.get_operation_schema(key, view="input")
    full = registry.get_operation_schema(key)
    assert "raw" not in schema
    assert "responses" not in schema
    assert schema["parameters"] == full["parameters"]
    assert schema["requestBody"] == full["requestBody"]
    assert schema["definitions"]["AdgroupRequest"] == full["definitions"]["AdgroupRequest"]
    assert schema["definitions"]["AutobidStrategyRequest"] == full["definitions"]["AutobidStrategyRequest"]
    assert len(schema["definitions"]) < len(full["definitions"])


def test_input_schema_omits_response_only_definitions_and_keeps_manual_overrides():
    registry = get_registry()
    schema = registry.get_operation_schema("ncc-report:getReportJobByReportJobIdUsingGET", view="input")
    assert "definitions" not in schema
    parameter = next(p for p in schema["parameters"] if p["name"] == "reportJobId")
    assert parameter["type"] == "integer"
    assert parameter["format"] == "int64"
    assert parameter["_manual_override_reason"]


def test_every_input_schema_includes_all_referenced_definitions():
    def references(value):
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/definitions/"):
                yield ref.removeprefix("#/definitions/")
            for child in value.values():
                yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)

    registry = get_registry()
    for key in registry.operations:
        schema = registry.get_operation_schema(key, view="input")
        missing = set(references(schema)) - set(schema.get("definitions", {}))
        assert not missing, (key, missing)
