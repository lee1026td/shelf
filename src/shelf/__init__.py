"""shelf — local-first, TUI-first CLI research library agent.

The public surface intentionally stays small. Most functionality lives in
subpackages (`cli`, `config`, `workspace`, `store`, `ui`, `library`) with later
phases provided as clearly-interfaced stubs (`ingestion`, `llm`, `discovery`,
`watcher`, `tui`, `notion`, `mcp`). See ARCHITECTURE.md.
"""

from __future__ import annotations

__all__ = ["__version__"]

# Keep in lockstep with `version` in pyproject.toml.
__version__ = "0.0.1"
