"""Discover and load skills from ``SKILL.md`` files (YAML frontmatter + body).

Built-in skills ship under ``skills/builtin/<name>/SKILL.md``. The frontmatter
(``name``, ``description``, ``toolset``) is cheap to scan for a menu; the body is the
guidance injected into the agent prompt when that skill is selected (progressive
disclosure — only the chosen skill's body enters context).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shelf.skills.base import Skill

_BUILTIN_DIR = Path(__file__).parent / "builtin"


def _parse(md_path: Path) -> tuple[dict, str]:
    text = md_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1])
            return (meta if isinstance(meta, dict) else {}), parts[2].strip()
    return {}, text.strip()


def _skill_files(extra_dirs: list[Path] | None = None) -> list[Path]:
    dirs = [_BUILTIN_DIR, *(extra_dirs or [])]
    files: list[Path] = []
    for directory in dirs:
        if directory.is_dir():
            for sub in sorted(directory.iterdir()):
                md = sub / "SKILL.md"
                if md.is_file():
                    files.append(md)
    return files


def list_skills(extra_dirs: list[Path] | None = None) -> list[Skill]:
    """All discoverable skills (built-in + any extra dirs, e.g. a workspace's)."""
    skills: list[Skill] = []
    for md in _skill_files(extra_dirs):
        meta, body = _parse(md)
        skills.append(
            Skill(
                name=str(meta.get("name") or md.parent.name),
                description=str(meta.get("description") or ""),
                toolset=meta.get("toolset"),
                body=body,
            )
        )
    return skills


def load_skill(name: str, extra_dirs: list[Path] | None = None) -> Skill | None:
    """Load a single skill by name, or None if not found."""
    for skill in list_skills(extra_dirs):
        if skill.name == name:
            return skill
    return None
