"""Jinja2 HTML rendering with autoescape and embedded local CSS."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.config import REPORT_STATIC_DIR, REPORT_TEMPLATE_DIR


class ReportHtmlRenderer:
    TEMPLATE_NAME = "grievancehub_report.html.j2"

    @classmethod
    def _environment(cls) -> Environment:
        env = Environment(
            loader=FileSystemLoader(str(REPORT_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return env

    @classmethod
    def _embedded_css(cls) -> str:
        css_path = REPORT_STATIC_DIR / "report.css"
        return css_path.read_text(encoding="utf-8")

    @classmethod
    def render(cls, export_context: dict) -> str:
        env = cls._environment()
        template = env.get_template(cls.TEMPLATE_NAME)
        return template.render(
            export=export_context,
            embedded_css=cls._embedded_css(),
        )
