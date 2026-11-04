"""Translate user-facing diagnostics; never translate machine status values."""

from functools import lru_cache
from importlib.resources import files
import json
from string import Formatter
from typing import Any, Mapping

LANGUAGES = ("en", "vi")


@lru_cache(maxsize=2)
def catalog(language: str) -> dict[str, str]:
    """Load a packaged message catalog; reject unsupported languages."""
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported diagnostic language: {language}")
    resource = files("ifc_to_fds.observability").joinpath("locales", f"{language}.json")
    data = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise ValueError(f"Invalid {language} diagnostic catalog")
    return data


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(template) if name is not None}


def validate_catalogs() -> None:
    """Fail CI if translations are incomplete or use different placeholders."""
    english, vietnamese = catalog("en"), catalog("vi")
    if english.keys() != vietnamese.keys():
        raise ValueError("English and Vietnamese diagnostic event codes differ")
    for code, english_text in english.items():
        if not code.startswith("IFCFDS."):
            raise ValueError(f"Invalid diagnostic code: {code}")
        if _placeholders(english_text) != _placeholders(vietnamese[code]):
            raise ValueError(f"Different placeholders in translations for {code}")


def render_event(event: Mapping[str, Any], language: str) -> str:
    """Render a single-line view of one canonical event; no data mutation."""
    code = str(event["code"])
    template = catalog(language).get(code)
    if template is None:
        raise ValueError(f"Missing {language} translation for event {code}")
    try:
        message = template.format_map(event.get("params", {}))
    except (KeyError, ValueError, IndexError) as exc:
        raise ValueError(f"Cannot render event {code} in {language}: {exc}") from exc
    # Prevent an untrusted parameter from injecting counterfeit log records.
    message = message.replace("\r", r"\r").replace("\n", r"\n")
    return (
        f'{event["timestamp"]} [{event["level"]}] [{code}] '
        f'{message}'
    )
