# 10 — Reproducibility and Execution Environment

## 1. Research Reproducibility Guarantee
Scientific research using BIM-to-FDS conversion requires absolute provenance and deterministic reproducibility. Different versions of underlying geometric kernels (e.g. OpenCASCADE, Trimesh, Manifold3D) or Python runtime environments may produce minute topological variations.

## 2. ExecutionEnvironment Value Object
Every conversion and audit run records an `ExecutionEnvironment` object inside run metadata and acceptance evidence:

```json
{
  "tool_version": "0.5.0",
  "git_sha": "d68d38e30b23dee012ba9c2541b7bb4238f2ddae",
  "schema_version": "0.5.0",
  "python_version": "3.12.10",
  "platform": "Windows-11-10.0.26200-SP0",
  "dependencies": {
    "ifcopenshell": "0.8.0",
    "trimesh": "4.6.4",
    "manifold3d": "3.0.1",
    "numpy": "2.1.2",
    "scipy": "1.14.1"
  },
  "fds_solver_version": null,
  "tolerances": {
    "surface_tolerance_m": 0.005,
    "relative_volume_tolerance": 0.05,
    "min_solid_iou": 0.95
  },
  "source_digests": {
    "model.ifc": "sha256:..."
  }
}
```

This ensures that any future audit can compare both the software environment and the mathematical tolerances under which a result was accepted.
