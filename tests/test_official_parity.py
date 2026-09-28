import shutil

from naver_searchad_mcp.review import run_official_parity_review, scan_for_forbidden_truncation_patterns, verify_snapshot_files
from naver_searchad_mcp.spec import official_spec_dir


def test_official_parity_review_passes_core_checks():
    result = run_official_parity_review()
    assert result["ok"], result["problems"]
    assert result["spec"]["total_operations"] == 127
    assert result["snapshot"]["verified_files"] == 12
    assert result["snapshot"]["sources"]["gh_pages_commit"] == "ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8"


def test_no_forbidden_truncation_patterns_in_runtime_code():
    assert scan_for_forbidden_truncation_patterns() == []


def test_unverified_bid_weight_parameter_remains_explicitly_blocked():
    result = run_official_parity_review()
    ambiguous = result["ambiguous_official_types"]
    assert ambiguous == [{
        "operation_key": "ncc-heroes-ncc:modifyBidWeightUsingPUT",
        "parameter": "codes",
        "in": "query",
        "type": "ref",
        "status": "blocked_until_official_type_is_verified",
    }]


def test_snapshot_review_detects_changed_official_document(tmp_path):
    snapshot = tmp_path / "official-spec"
    shutil.copytree(official_spec_dir(), snapshot)
    with (snapshot / "ncc-report.json").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    result = verify_snapshot_files(snapshot)
    assert not result["ok"]
    assert result["problems"] == ["Official snapshot checksum mismatch: ncc-report.json"]
