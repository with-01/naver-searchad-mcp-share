"""Exercise a built wheel outside the checkout to detect missing package data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


def test_wheel_contains_working_specs_errors_and_guide(tmp_path):
    root = Path(__file__).resolve().parents[1]
    dist = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(dist), str(root)],
        check=True, capture_output=True, text=True,
    )
    wheel = next(dist.glob("*.whl"))
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        assert "naver_searchad_mcp/data/official-spec/SOURCE.json" in archive.namelist()
        assert "naver_searchad_mcp/data/usage-guide/SKILL.md" in archive.namelist()
        archive.extractall(installed)
    env = {key: value for key, value in os.environ.items() if not key.startswith("NAVER_SEARCHAD_")}
    env.pop("PYTHONPATH", None)
    script = """
import json, sys
sys.path.insert(0, sys.argv[1])
import naver_searchad_mcp
from naver_searchad_mcp.spec import get_registry
from naver_searchad_mcp.errors import get_error_code
from naver_searchad_mcp.usage_guide import get_chapter
from naver_searchad_mcp.server import mcp
from naver_searchad_mcp.review import verify_snapshot_files
print(json.dumps({
    'module': naver_searchad_mcp.__file__,
    'sections': len(get_registry().list_sections()),
    'operations': len(get_registry().list_operations()),
    'error_found': get_error_code('1001')['found'],
    'guide_found': get_chapter('tools-cheatsheet')['found'],
    'server_name': mcp.name,
    'snapshot_ok': verify_snapshot_files(get_registry().spec_dir)['ok'],
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(installed)],
        cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    )
    observed = json.loads(result.stdout)
    assert Path(observed["module"]).is_relative_to(installed)
    assert observed["sections"] == 9
    assert observed["operations"] >= 126
    assert observed["error_found"] is True
    assert observed["guide_found"] is True
    assert observed["server_name"] == "naver-searchad"
    assert observed["snapshot_ok"] is True
