# ADR 0004 — JavaScript Quick Path is Legacy / Non-Authoritative

## Status
Accepted.

## Context
The JavaScript conversion code originated in early browser prototypes. While fast for interactive 3D viewing, it uses heuristic approximations for openings and does not perform rigorous 3-tier validation or solver proofs.

## Decision
Classify the JavaScript client-side export path as **Legacy / Quick / Experimental**. It is decoupled from the authoritative verification pipeline and clearly labeled in the user interface.

## Alternatives Considered
- Attempting to bring the JS engine to 100% parity with Python/OpenCASCADE: Rejected as prohibitively expensive and unnecessary given the Python core's availability.

## Consequences
- Quick conversions are clearly badged as unverified previews.
- Users seeking verified simulation-ready FDS models must execute the Verified conversion path.
