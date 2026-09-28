"""Load the bundled usage guide for any MCP client."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .spec import project_root


SKILL_NAME = "naver-searchad-usage"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def skill_dir() -> Path:
    packaged = Path(__file__).resolve().parent / "data" / "usage-guide"
    if packaged.is_dir():
        return packaged
    return project_root() / "skills" / SKILL_NAME


def references_dir() -> Path:
    return skill_dir() / "references"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """간단한 YAML-ish frontmatter 파서. `key: value` 라인만 처리."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fm_text, body = match.group(1), match.group(2)
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm, body


@lru_cache(maxsize=1)
def load_skill_index() -> dict[str, Any]:
    """SKILL.md 의 frontmatter + 본문 + references 챕터 목록 반환."""
    skill_path = skill_dir() / "SKILL.md"
    if not skill_path.is_file():
        raise FileNotFoundError(f"SKILL.md not found at: {skill_path}")
    skill_text = skill_path.read_text(encoding="utf-8")
    skill_fm, skill_body = _parse_frontmatter(skill_text)

    chapters: list[dict[str, Any]] = []
    refs = references_dir()
    if refs.is_dir():
        for chapter_path in sorted(refs.glob("*.md")):
            text = chapter_path.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(text)
            chapters.append(
                {
                    "topic": chapter_path.stem,
                    "title": fm.get("title", chapter_path.stem),
                    "description": fm.get("description", ""),
                }
            )

    return {
        "skill": {
            "name": skill_fm.get("name", SKILL_NAME),
            "description": skill_fm.get("description", ""),
            "when_to_use": skill_fm.get("when_to_use", ""),
            "version": skill_fm.get("version", ""),
            "body": skill_body.strip(),
        },
        "chapters": chapters,
    }


def get_chapter(topic: str | None = None) -> dict[str, Any]:
    """특정 챕터 본문 로드.

    topic=None / "" / "index" / "skill": SKILL.md 본문 + 챕터 목록 반환
    topic="<chapter-name>": references/<topic>.md 본문 반환
    잘못된 topic: {found: false, available: [...]}
    """
    if not topic or topic.lower() in {"index", "skill"}:
        idx = load_skill_index()
        return {
            "topic": "index",
            "found": True,
            "skill": idx["skill"],
            "chapters": idx["chapters"],
        }

    refs = references_dir()
    chapters = {p.stem: p for p in refs.glob("*.md") if p.is_file()}
    chapter_path = chapters.get(topic)
    if chapter_path is None:
        available = sorted(chapters)
        return {
            "topic": topic,
            "found": False,
            "available": available,
            "hint": "사용 가능한 chapter topic 목록은 'available' 필드 또는 get_usage_guide() (인덱스) 참조.",
        }

    text = chapter_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    return {
        "topic": topic,
        "found": True,
        "title": fm.get("title", topic),
        "description": fm.get("description", ""),
        "body": body.strip(),
    }
