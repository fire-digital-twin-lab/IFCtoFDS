"""Structured, language-neutral diagnostic events and bilingual renderers.

The canonical JSONL event stream is authoritative. Human-readable English and
Vietnamese logs are derived views and never determine audit acceptance.
"""

from .events import DiagnosticEvent
from .catalog import catalog, render_event, validate_catalogs
from .writer import append_event, rebuild_localized_logs

__all__ = [
    "DiagnosticEvent",
    "catalog",
    "render_event",
    "validate_catalogs",
    "append_event",
    "rebuild_localized_logs",
]
