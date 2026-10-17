# ADR 0003 — Python Verified Core is Authoritative

## Status
Accepted.

## Context
IFCtoFDS has two engines: a JavaScript client-side implementation and a Python-based pipeline. Maintaining two divergent sources of truth for research findings causes ambiguity in scientific reporting.

## Decision
Designate the **Python Verified Core** as the single authoritative source of ground truth for conversion, mapping, validation, and scientific research. The JavaScript pipeline is designated as a quick preview and web workbench adapter only.

## Alternatives Considered
- Maintaining two authoritative engines in tandem: Rejected because JavaScript engines lack robust CAD CSG kernels and diverge in precision and representation.
- Completely deleting the JavaScript code: Rejected to maintain client-side viewer capabilities and backward compatibility.

## Consequences
- Research publications and benchmarks must reference results produced by the Python Verified Core.
- The web interface communicates with the Python engine via local API for all verified operations.
