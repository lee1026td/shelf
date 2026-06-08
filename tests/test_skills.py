"""Phase 3 skills: SKILL.md frontmatter parse + lazy body load."""

from __future__ import annotations

from shelf.skills import list_skills, load_skill


def test_list_skills_includes_builtin_explore():
    names = {s.name for s in list_skills()}
    assert "explore" in names


def test_load_explore_skill_has_body_and_toolset():
    skill = load_skill("explore")
    assert skill is not None
    assert skill.toolset == "discovery"
    assert skill.description  # frontmatter description parsed
    assert "propose_source" in skill.body  # body loaded from the markdown


def test_load_unknown_skill_returns_none():
    assert load_skill("does-not-exist") is None


def test_compile_skill_available_with_compile_toolset():
    skill = load_skill("compile")
    assert skill is not None
    assert skill.toolset == "compile"
    assert "cite" in skill.body.lower()
