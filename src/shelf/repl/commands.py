"""Slash-command registry for the REPL.

This is the single source of truth for what ``/help`` shows and which phase backs
each command. ``phase=None`` means the command works today. Phases align with
COMMANDS.md / IMPLEMENTATION_PLAN.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str
    summary: str
    phase: int | None = None  # None => available now

    @property
    def available(self) -> bool:
        return self.phase is None


# Ordered for display: available-now first, then by the phase that delivers them.
SLASH_COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand("status", "Show library status (sources / inbox / review)"),
    SlashCommand("clip", "Save a URL (http/https/file) as an Item"),
    SlashCommand("import", "Import local PDF/HTML/Markdown/text into Items"),
    SlashCommand("inbox", "List newly collected items (status='new')"),
    SlashCommand("search", "Keyword search over collected items"),
    SlashCommand("sources", "List the source universe"),
    SlashCommand("save", "Mark an item as saved: /save <id>"),
    SlashCommand("mute", "Mute an item: /mute <id>"),
    SlashCommand("ask", "Quick library-grounded answer (no tools; plain text routes the agent)"),
    SlashCommand("summarize", "LLM-summarize an item: /summarize <id>"),
    SlashCommand("model", "Pick model: /model (role->provider->model) | show | list | set | use"),
    SlashCommand("explore", "Discover + propose sources and write a cited brief for a topic"),
    SlashCommand("help", "List commands"),
    SlashCommand("exit", "Leave the REPL"),
    SlashCommand("track", "Mark a topic as tracked + set a refresh frequency"),
    SlashCommand("compile", "Compile a cited brief/landscape from the library"),
    SlashCommand("watch", "Manage watched sources", 4),
    SlashCommand("digest", "Generate a period / topic digest", 4),
    SlashCommand("diff", "Review snapshot / wiki / compilation changes", 4),
    SlashCommand("jobs", "Monitor background jobs", 4),
    SlashCommand("review", "Process the review queue", 5),
    SlashCommand("wiki", "Manage the local wiki", 5),
    SlashCommand("local", "Manage the local workspace", 5),
    SlashCommand("privacy", "Audit external egress", 5),
    SlashCommand("rules", "Manage classification / scoring rules", 5),
    SlashCommand("export", "Export Markdown / JSON / ZIP", 5),
    SlashCommand("rollback", "Revert recent transactions", 5),
    SlashCommand("notion", "Manage Notion connection", 6),
    SlashCommand("sync", "Sync to Notion / markdown output", 6),
    SlashCommand("mcp", "Register / inspect MCP servers", 7),
)

COMMANDS_BY_NAME: dict[str, SlashCommand] = {c.name: c for c in SLASH_COMMANDS}

# Built-ins handled directly by the session loop (not "coming soon").
EXIT_ALIASES = frozenset({"exit", "quit", "q"})
HELP_ALIASES = frozenset({"help", "", "?"})
