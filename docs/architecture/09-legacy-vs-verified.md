# 09 — Separation of Verified Core vs Legacy Quick Path

## 1. Clear Conceptual Boundary
The project maintains two distinct execution paths with explicitly different quality guarantees:

| Dimension | Verified Core (Python / IfcOpenShell) | Legacy Quick Path (JavaScript / Web) |
|---|---|---|
| **Primary Role** | Authoritative Research Engine & Ground Truth | Interactive Web Workbench & Quick Preview |
| **Ingestion** | IfcOpenShell + OpenCASCADE CSG | web-ifc (WASM) |
| **Validation** | 3-tier independent audit + golden parity | Static client-side sanity checks |
| **Geometry** | Manifold booleans, precise opening carving | Fast mesh approximation |
| **MEP Support** | Source-qualified port graph & systems | Basic visual display |
| **Acceptance** | Formal `MAPPING_VERIFIED` / `REJECTED` gates | No formal verification status |
| **Reproducibility** | Full `ExecutionEnvironment` and checksums | Browser-dependent |

## 2. Policy
The Quick JavaScript path **MUST NOT** be used as a research ground truth source. The Web UI must clearly badge conversions as either:
- **Verified Conversion** (backed by Python Verified Core via local API)
- **Quick Preview / Legacy Conversion** (client-side browser preview)
