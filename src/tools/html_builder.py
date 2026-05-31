"""Jinja2 + Chart.js HTML rendering helpers."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


def build_environment(template_dir: Path | None = None) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(template_dir or TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env


def render_report(context: dict, *, template_name: str = "report.html.j2") -> str:
    env = build_environment()
    template = env.get_template(template_name)
    return template.render(**context)
