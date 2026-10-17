# 07 — Run Artifact Model

## 1. Directory Layout
For each conversion or audit run, artifacts are organized under a standard run directory:

```text
runs/<run-id>/
├── metadata.json              # Run timing, environment, git SHA, command options
├── source/
│   └── sources.json           # Hashes and coordinate metadata of source IFC files
├── canonical/
│   ├── inventory.json         # Normalized elements metadata (without binary vertices)
│   ├── mep.json               # Topologically resolved MEP graph
│   └── geometry/              # Sidecar binary meshes and package index
│       ├── model_geometry.json
│       ├── model_geometry.zip
│       └── payloads/*.bin
├── mapping/
│   ├── plan.json              # Abstract MappingPlan decisions
│   ├── manifest.json          # Bidirectional IFC-FDS provenance manifest
│   └── manifest.csv           # Tabular export for spreadsheets / auditing
├── fds/
│   └── model.fds              # Serialized FDS input file
├── validation/
│   ├── report.json            # Final AcceptanceReport
│   ├── report.md              # Markdown summary report
│   ├── findings.json          # List of all validation findings
│   └── metrics.json           # Computed geometric and residual metrics
├── solver/
│   ├── stdout.log             # FDS solver stdout
│   ├── stderr.log             # FDS solver stderr
│   └── model.smv              # Smokeview visualization file (reference only)
└── checksums.json             # SHA-256 digests of all generated files in run
```

## 2. Decoupling Evidence from Results
Large binary or text payloads (such as multi-megabyte Smokeview files or solver logs) are stored in the filesystem or object storage as dedicated artifact files. The JSON report retains only an `ArtifactReference(path, sha256, size_bytes, media_type)`, preventing payload bloat and memory exhaustion.
