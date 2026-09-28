import pytest

from naver_searchad_mcp.spec import get_registry
from naver_searchad_mcp.validation import (
    AmbiguousOfficialTypeError,
    ValidationError,
    _validate_schema_value,
    validate_operation_input,
)


def op(operation_key: str):
    return get_registry().get_operation(operation_key)


@pytest.mark.parametrize("operation_id,identity", [
    ("getSingleEntityStatUsingGET", {"id": "cmp-example"}),
    ("getBulkEntityStatUsingGET", {"ids": "cmp-example,cmp-other"}),
])
def test_statistics_accept_documented_json_array_string(operation_id, identity):
    operation = op(f"ncc-report:{operation_id}")
    query = {**identity, "fields": '["impCnt","clkCnt","purchaseRor"]', "datePreset": "yesterday"}
    assert validate_operation_input(operation, query=query).query == query


@pytest.mark.parametrize("fields", ['impCnt', '["notAnOfficialMetric"]', '[1]', '{"impCnt":true}'])
def test_statistics_reject_invalid_json_fields(fields):
    with pytest.raises(ValidationError, match="JSON array string"):
        validate_operation_input(op("ncc-report:getSingleEntityStatUsingGET"), query={"id": "cmp-example", "fields": fields})


def test_updated_adgroup_schema_accepts_ai_ads_opt_in():
    prepared = validate_operation_input(op("ncc-heroes-ncc:addUsingPOST_6"), body={"aiAdsOptIn": False})
    assert prepared.body == {"aiAdsOptIn": False}


def test_new_managed_keyword_post_body():
    body = {"keywords": ["example"], "disablePattern": False}
    prepared = validate_operation_input(op("ncc-heroes-ncc:postKeywordAttributesUsingPOST"), body=body)
    assert prepared.body == body


def vsv(value, schema, field_path="x"):
    """_validate_schema_value 짧은 호출 헬퍼."""
    return _validate_schema_value(value, schema, field_path)


def test_rejects_unknown_query_parameter():
    operation = op("ncc-report:getSingleEntityStatUsingGET")
    with pytest.raises(ValidationError, match="unknown query"):
        validate_operation_input(operation, query={"id": "cmp-a", "notOfficial": "x"})


def test_rejects_wrong_integer_query_type_without_coercion():
    operation = op("ncc-heroes-ncc:getGroupsUsingGET_2")
    with pytest.raises(ValidationError, match="query.recordSize: must be integer"):
        validate_operation_input(operation, query={"nccCampaignId": "cmp-a001", "recordSize": "10"})


def test_accepts_correct_integer_query_type():
    operation = op("ncc-heroes-ncc:getGroupsUsingGET_2")
    prepared = validate_operation_input(operation, query={"nccCampaignId": "cmp-a001", "recordSize": 10})
    assert prepared.query["recordSize"] == 10


def test_rejects_missing_required_path_parameter():
    operation = op("ncc-heroes-ncc:getUsingGET_16")
    with pytest.raises(ValidationError, match="path_params.adgroupId"):
        validate_operation_input(operation)


def test_prepares_required_path_parameter():
    operation = op("ncc-heroes-ncc:getUsingGET_16")
    prepared = validate_operation_input(operation, path_params={"adgroupId": "grp-a001"})
    assert prepared.path == "/api/ncc/adgroups/grp-a001"


def test_path_parameter_is_percent_encoded_as_path_segment():
    operation = op("ncc-heroes-ncc:getUsingGET_16")
    prepared = validate_operation_input(operation, path_params={"adgroupId": "grp/a?b#c d"})
    assert prepared.path == "/api/ncc/adgroups/grp%2Fa%3Fb%23c%20d"


def test_rejects_body_when_operation_has_no_body():
    operation = op("ncc-heroes-ncc:getUsingGET_16")
    with pytest.raises(ValidationError, match="does not define a request body"):
        validate_operation_input(operation, path_params={"adgroupId": "grp-a001"}, body={})


def test_rejects_array_body_when_object_expected():
    operation = op("ncc-heroes-ncc:addUsingPOST_3")
    with pytest.raises(ValidationError, match="body: must be object"):
        validate_operation_input(operation, body=[])


def test_rejects_unknown_object_body_field_unless_officially_allowed():
    operation = op("ncc-heroes-ncc:addUsingPOST_3")
    with pytest.raises(ValidationError, match="unknown object field"):
        validate_operation_input(operation, body={"name": "campaign", "notOfficial": "x"})


def test_rejects_array_item_type_when_known():
    operation = op("estimate:getExposureMinimumBid")
    body = {"device": "PC", "period": "MONTH", "items": [123]}
    with pytest.raises(ValidationError, match=r"body.items\[0\]: must be string"):
        validate_operation_input(operation, path_params={"type": "keyword"}, body=body)


def test_manual_override_makes_report_job_id_integer():
    """MANUAL_PARAM_OVERRIDES 가 reportJobId 를 long integer 로 변환했는지."""
    operation = op("ncc-report:getReportJobByReportJobIdUsingGET")
    # 정수 통과
    prepared = validate_operation_input(operation, path_params={"reportJobId": 123456789})
    assert prepared.path == "/api/stat-reports/123456789"
    # 문자열 거부
    with pytest.raises(ValidationError, match="must be integer"):
        validate_operation_input(operation, path_params={"reportJobId": "abc"})


@pytest.mark.parametrize("codes", [["example:1", "example:2"], "example:1,example:2", 1])
def test_ambiguous_bid_weight_codes_are_rejected_before_network(codes):
    import httpx
    from naver_searchad_mcp.auth import NaverSearchAdCredentials
    from naver_searchad_mcp.client import CONFIRM_ACTION, NaverSearchAdClient

    operation = op("ncc-heroes-ncc:modifyBidWeightUsingPUT")

    def no_network(request):
        pytest.fail("Ambiguous official input must fail before any HTTP request")

    credentials = NaverSearchAdCredentials(customer_id="123", access_license="example", secret_key="example")
    with httpx.Client(transport=httpx.MockTransport(no_network)) as http_client:
        client = NaverSearchAdClient(credentials, http_client=http_client)
        with pytest.raises(AmbiguousOfficialTypeError, match="ambiguous type 'ref'"):
            client.execute_operation(
                operation,
                path_params={"ownerId": "grp-example"},
                query={"codes": codes, "bidWeight": 150},
                confirm_action=CONFIRM_ACTION,
            )


def test_manual_override_metadata_preserved():
    """override 적용 시 _manual_override_reason 메타데이터가 parameter 에 남는지."""
    operation = op("ncc-report:getReportJobByReportJobIdUsingGET")
    path_param = next(p for p in operation.parameters if p.get("name") == "reportJobId")
    assert "_manual_override_reason" in path_param
    assert path_param["type"] == "integer"
    assert path_param.get("format") == "int64"


@pytest.mark.parametrize("operation_id", ["getReportJobByReportJobIdUsingGET", "deleteReportJobByReportJobIdUsingDELETE"])
def test_report_job_id_override_matches_official_response_definition(operation_id):
    official = get_registry().documents["ncc-report"]["definitions"]["ReportJobResponse"]["properties"]["reportJobId"]
    parameter = next(p for p in op(f"ncc-report:{operation_id}").parameters if p.get("name") == "reportJobId")
    assert (parameter["type"], parameter["format"]) == (official["type"], official["format"])


# === Phase 6: autobidStrategy / Adgroup body nested validation ===

def test_adgroup_request_schema_has_autobid_strategy_field():
    """sanity check — AdgroupRequest 스키마에 autobidStrategy 필드 + ref 가 있어야 한다."""
    doc = get_registry().documents["ncc-heroes-ncc"]
    schema = doc["definitions"]["AdgroupRequest"]
    assert "autobidStrategy" in schema["properties"]
    assert schema["properties"]["autobidStrategy"]["$ref"] == "#/definitions/AutobidStrategyRequest"


def test_adgroup_create_accepts_arbitrary_jsonnode_target_fields():
    operation = op("ncc-heroes-ncc:addUsingPOST_6")
    body = {
        "targets": [
            {
                "targetTp": "PC_MOBILE_TARGET",
                "target": {"pc": True, "mobile": False},
            }
        ]
    }

    prepared = validate_operation_input(operation, body=body)

    assert prepared.body == body


def test_adgroup_create_accepts_valid_autobid_strategy_enum():
    """광고그룹 create body 에 autobidStrategy 의 정상 enum 값 → 통과."""
    operation = op("ncc-heroes-ncc:addUsingPOST_6")
    body = {
        "name": "test-adgroup",
        "nccCampaignId": "cmp-x",
        "bidAmt": 1000,
        "autobidStrategy": {
            "autobidBidGoal": "MAX_CLICK",
            "autobidBidStrategy": "NO_CAP",
        },
    }
    prepared = validate_operation_input(operation, body=body)
    assert prepared.body["autobidStrategy"]["autobidBidGoal"] == "MAX_CLICK"
    assert prepared.body["autobidStrategy"]["autobidBidStrategy"] == "NO_CAP"


def test_adgroup_create_rejects_invalid_autobid_bid_goal_enum():
    """잘못된 autobidBidGoal enum 값은 ValidationError 로 차단되어야 한다."""
    operation = op("ncc-heroes-ncc:addUsingPOST_6")
    body = {
        "name": "x",
        "autobidStrategy": {"autobidBidGoal": "INVALID_GOAL"},
    }
    with pytest.raises(ValidationError, match="enum"):
        validate_operation_input(operation, body=body)


def test_adgroup_create_rejects_invalid_autobid_bid_strategy_enum():
    """잘못된 autobidBidStrategy enum 값은 ValidationError 로 차단되어야 한다."""
    operation = op("ncc-heroes-ncc:addUsingPOST_6")
    body = {
        "name": "x",
        "autobidStrategy": {"autobidBidStrategy": "NOT_A_REAL_STRATEGY"},
    }
    with pytest.raises(ValidationError, match="enum"):
        validate_operation_input(operation, body=body)


def test_campaign_create_validates_campaign_type_enum():
    """캠페인 생성 시 campaignTp enum 검증 (WEB_SITE/SHOPPING/BRAND_SEARCH/...)."""
    # 캠페인 생성 op 찾기
    reg = get_registry()
    create_ops = [
        op_obj for op_obj in reg.operations.values()
        if op_obj.method == "POST" and "Campaign" in op_obj.tags
        and op_obj.path == "/api/ncc/campaigns"
    ]
    assert create_ops, "Campaign POST op not found"
    create_op = create_ops[0]
    # 잘못된 enum
    with pytest.raises(ValidationError, match="enum"):
        validate_operation_input(create_op, body={"campaignTp": "INVALID_CAMPAIGN_TYPE"})


# === Phase 3: format / min·max / length / pattern / nullable / default / additionalProperties / allOf / oneOf/anyOf ===

def test_string_min_max_length():
    schema = {"type": "string", "minLength": 3, "maxLength": 5}
    assert vsv("abcd", schema) == "abcd"
    with pytest.raises(ValidationError, match="minLength"):
        vsv("ab", schema)
    with pytest.raises(ValidationError, match="maxLength"):
        vsv("abcdef", schema)


def test_string_pattern_regex():
    schema = {"type": "string", "pattern": r"^cmp-[a-z0-9]+$"}
    assert vsv("cmp-abc123", schema) == "cmp-abc123"
    with pytest.raises(ValidationError, match="does not match pattern"):
        vsv("CMP-ABC", schema)


def test_string_format_date():
    schema = {"type": "string", "format": "date"}
    assert vsv("2026-05-03", schema) == "2026-05-03"
    with pytest.raises(ValidationError, match="date format"):
        vsv("2026/05/03", schema)


def test_string_format_date_time():
    schema = {"type": "string", "format": "date-time"}
    assert vsv("2026-05-03T12:34:56Z", schema) == "2026-05-03T12:34:56Z"
    assert vsv("2026-05-03T12:34:56+09:00", schema) == "2026-05-03T12:34:56+09:00"
    with pytest.raises(ValidationError, match="date-time"):
        vsv("not-a-datetime", schema)


def test_integer_minimum_maximum():
    schema = {"type": "integer", "minimum": 70, "maximum": 100000}
    assert vsv(70, schema) == 70
    assert vsv(100000, schema) == 100000
    with pytest.raises(ValidationError, match="minimum"):
        vsv(69, schema)
    with pytest.raises(ValidationError, match="maximum"):
        vsv(100001, schema)


def test_integer_exclusive_minimum_maximum():
    schema = {"type": "integer", "minimum": 0, "exclusiveMinimum": True, "maximum": 100, "exclusiveMaximum": True}
    assert vsv(1, schema) == 1
    assert vsv(99, schema) == 99
    with pytest.raises(ValidationError, match="exclusiveMinimum"):
        vsv(0, schema)
    with pytest.raises(ValidationError, match="exclusiveMaximum"):
        vsv(100, schema)


def test_integer_format_int32_int64_range():
    schema_32 = {"type": "integer", "format": "int32"}
    schema_64 = {"type": "integer", "format": "int64"}
    assert vsv(2 ** 31 - 1, schema_32) == 2 ** 31 - 1
    with pytest.raises(ValidationError, match="int32 range"):
        vsv(2 ** 31, schema_32)
    # A synthetic example within the int32 range also fits int64.
    assert vsv(123456789, schema_64) == 123456789


def test_number_minimum_maximum():
    schema = {"type": "number", "minimum": 0.0, "maximum": 1.0}
    assert vsv(0.5, schema) == 0.5
    with pytest.raises(ValidationError):
        vsv(-0.1, schema)
    with pytest.raises(ValidationError):
        vsv(1.1, schema)


def test_array_min_max_items():
    schema = {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2}
    assert vsv(["a"], schema) == ["a"]
    with pytest.raises(ValidationError, match="minItems"):
        vsv([], schema)
    with pytest.raises(ValidationError, match="maxItems"):
        vsv(["a", "b", "c"], schema)


def test_nullable_allows_none():
    schema = {"type": "string", "nullable": True}
    assert vsv(None, schema) is None
    # 비-nullable string 은 None 거부
    with pytest.raises(ValidationError):
        vsv(None, {"type": "string"})


def test_default_value_injected_when_missing_in_object():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "lang": {"type": "string", "default": "ko"},
        },
        "required": ["name"],
    }
    result = vsv({"name": "x"}, schema)
    assert result == {"name": "x", "lang": "ko"}


def test_additional_properties_schema_validates_unknown_fields():
    schema = {
        "type": "object",
        "properties": {"known": {"type": "string"}},
        "additionalProperties": {"type": "integer"},
    }
    # unknown field "extra" 는 integer schema 로 검증
    result = vsv({"known": "ok", "extra": 42}, schema)
    assert result == {"known": "ok", "extra": 42}
    with pytest.raises(ValidationError, match="must be integer"):
        vsv({"known": "ok", "extra": "not-int"}, schema)


def test_one_of_any_of_blocked():
    with pytest.raises(AmbiguousOfficialTypeError, match="oneOf/anyOf"):
        vsv({}, {"oneOf": [{"type": "object"}]})
    with pytest.raises(AmbiguousOfficialTypeError, match="oneOf/anyOf"):
        vsv({}, {"anyOf": [{"type": "object"}]})


def test_all_of_merges_properties_and_required():
    schema = {
        "allOf": [
            {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
            {"type": "object", "properties": {"b": {"type": "integer"}}, "required": ["b"]},
        ]
    }
    result = vsv({"a": "x", "b": 1}, schema)
    assert result == {"a": "x", "b": 1}
    # 둘 다 required → 하나 빠지면 에러
    with pytest.raises(ValidationError, match="required field is missing"):
        vsv({"a": "x"}, schema)
