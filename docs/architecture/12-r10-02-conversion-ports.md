# R10-02 — Conversion Ports and Dependency Injection

**Base:** PR #22, R10-01 branch. **Status:** review pending.

## Purpose / Mục tiêu

Make the Python Verified conversion path depend on explicit narrow ports.
No change to the IFC/FDS geometry algorithm, FDS serialization rules,
mapping policy, or independent acceptance evaluator.

Luồng chuyển đổi chuẩn được tiêm adapter qua composition root thay vì
tự liên kết implementation ở tầng ứng dụng.

## Ports / Adapter

| Port | Production adapter | Original behavior |
|---|---|---|
| ModelPreparerPort | DefaultModelPreparer | prepare_model |
| MappingPlannerPort | DefaultMappingPlanner | build_mapping_plan + build_hvac_network |
| VerifiedFdsSerializerPort | DefaultFdsSerializer | serialize_fds |
| GeometryPackageWriterPort | DefaultGeometryPackageWriter | write_package |

The old `pipeline.convert` delegates to the container. Existing direct
`ConvertVerifiedUseCase()` construction still works by transitional fallback.

## Safety / An toàn

- Preserve FDS bytes, mapping plans, source SHA, geometry package checksum,
  output inventory, independent audit status and manifest behavior.
- The audit checkpoint remains NOT_RUN until the independent source re-read.
- Never treat successful conversion as scientific verification.

## Tests

See `tests/test_conversion_ports_di.py` for DI, serializer byte parity,
geometry-package integrity and the audit boundary.
Existing frozen baseline A–F plus browser and solver CI are required.

## Next steps

Move checkpoint/artifact handling to a dedicated repository port only
after baseline equivalence. Do not replace `validation.engine` without
full gate-by-gate parity with `ValidationRunner`.
