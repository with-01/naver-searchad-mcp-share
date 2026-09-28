from pathlib import Path


def test_official_spec_files_preserved():
    root = Path(__file__).resolve().parents[1]
    spec_dir = root / "docs" / "official-spec"
    json_files = sorted(p.name for p in spec_dir.glob("*.json") if p.name != "SOURCE.json")
    assert json_files == [
        "atower.json",
        "estimate.json",
        "master-report.json",
        "ncc-heroes-billing.json",
        "ncc-heroes-ncc.json",
        "ncc-heroes-tool.json",
        "ncc-inspect-history.json",
        "ncc-keywordstool.json",
        "ncc-report.json",
    ]
    assert (spec_dir / "NaverSA_API_Error_Code_MAP.md").exists()
    assert (spec_dir / "official_signaturehelper.py").exists()
    assert (spec_dir / "SOURCE.json").exists()
