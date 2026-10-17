# ADR 0006 — Evidence is Stored Separately from AcceptanceReport

## Status
Accepted.

## Context
During conversion and validation, extensive evidence is generated, including large binary vertex arrays, raw Smokeview (.smv) files, and verbose solver execution logs. Embedding these multi-megabyte payloads directly inside `AcceptanceReport` or `GateResult.evidence` causes extreme JSON serialization bloat, network transfer bottlenecks, and high RAM usage.

## Decision
Store raw evidence artifacts (solver logs, SMV files, binary mesh packages) in an external `ArtifactRepository` (filesystem or object storage). The `AcceptanceReport` retains only compact cryptographic references:
```json
{
  "solver_log": {
    "artifact_path": "solver/stdout.log",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "size_bytes": 1048576,
    "media_type": "text/plain"
  }
}
```

## Alternatives Considered
- Inline base64 or string embedding: Rejected due to memory and payload bloat.
- Omission of evidence: Rejected because scientific reproducibility requires full traceability.

## Consequences
- Reports remain compact, fast to serialize, and lightweight over REST APIs.
- Deep evidence remains auditable via checksums and reproducible artifacts.
