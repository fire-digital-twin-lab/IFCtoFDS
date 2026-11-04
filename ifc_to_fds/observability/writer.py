"""Append canonical JSONL and regenerate English/Vietnamese human-readable logs.

JSONL is the source of truth. The two .log files are derived views, so they can
be regenerated after an interrupted append without changing audit artifacts.
"""

import json
from pathlib import Path
from typing import Any

from .catalog import LANGUAGES, render_event
from .events import DiagnosticEvent

CANONICAL_NAME = "events.jsonl"


def append_event(directory: str | Path, event: DiagnosticEvent) -> None:
    """Append a structured event and its two localized text representations.

    Callers manage error policy: logging failures must not silently change any
    geometry or acceptance verdict.
    """
    destination = Path(directory)
    record = event.to_record()
    # Validate both translations before writing any event bytes.
    formatted = {lang: render_event(record, lang) for lang in LANGUAGES}
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
    with (destination / CANONICAL_NAME).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(raw + "\n")
    for language, text in formatted.items():
        with (destination / f"events.{language}.log").open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(text + "\n")


def rebuild_localized_logs(directory: str | Path) -> dict[str, Path]:
    """Deterministically derive the two human logs from authoritative JSONL.

    Each human log is atomically replaced independently. An incomplete JSONL
    line raises an error rather than fabricating a successful job.
    """
    root = Path(directory)
    source = root / CANONICAL_NAME
    lines: dict[str, list[str]] = {language: [] for language in LANGUAGES}
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"Blank JSONL event line: {line_number}")
            record: dict[str, Any] = json.loads(line)
            for language in LANGUAGES:
                lines[language].append(render_event(record, language))
    outputs = {}
    for language in LANGUAGES:
        output = root / f"events.{language}.log"
        temporary = root / f"events.{language}.log.tmp"
        content = "\n".join(lines[language]) + ("\n" if lines[language] else "")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(output)
        outputs[language] = output
    return outputs
