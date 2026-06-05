"""Render `/model` output: configured profiles + a reachability probe."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from shelf.config import Config
from shelf.llm import ProbeResult


def render_models(console: Console, config: Config, probe: ProbeResult | None = None) -> None:
    table = Table(title="models", title_style="bold cyan", expand=False)
    table.add_column("Role")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Base URL")
    table.add_column("Capabilities")
    for role, profile in config.models.items():
        caps = profile.capabilities
        cap_str = f"tools={caps.tools} json={caps.json_schema} emb={caps.embeddings}"
        table.add_row(
            role, profile.provider, profile.model or "(none)", profile.base_url, cap_str
        )
    console.print(table, highlight=False)

    if probe is not None:
        if probe.reachable:
            console.print(
                f"planner endpoint reachable: {probe.base_url} ({probe.model})", style="green"
            )
        else:
            console.print(
                f"planner endpoint not reachable: {probe.error}", style="yellow", highlight=False
            )


def render_model_list(console: Console, role: str, base_url: str, models: list[str]) -> None:
    console.print(
        f"models available for '{role}' at {base_url}:", style="bold cyan", highlight=False
    )
    if not models:
        console.print("  (endpoint returned no models)", style="dim")
        return
    for model in models:
        console.print(f"  - {model}", highlight=False)
    console.print(
        f"Select one:  /model set {role} <model>   (or `shelf model set {role} <model>`)",
        style="dim",
        highlight=False,
    )
