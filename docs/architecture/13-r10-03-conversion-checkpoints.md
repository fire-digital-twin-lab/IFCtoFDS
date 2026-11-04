# R10-03 — Conversion Workspace and Audit Checkpoints

**Based on:** R10-02 PR #23. **Status:** staged for review.

## Why / Vì sao

The verified conversion use case previously performed direct filesystem
reads/writes of the FDS text, mapping plan, manifest, inventory, source MEP
graph, configuration and audit checkpoint. It mixed orchestration with local
artifact persistence, making review and alternative storage difficult.

Đợt này tách các thao tác I/O thành adapter có hợp đồng rõ ràng và **không**
thay đổi thuật toán chuyển đổi hình học, lựa chọn FDS, hoặc kiểm định độc lập.

## Architecture / Kiến trúc

- Application port: \`application/ports/conversion_workspace.py\`
- Local adapter: \`adapters/storage/conversion_workspace.py\`
- Pure inventory projection: \`application/services/portable_inventory.py\`
- Composition root: \`bootstrap/container.py\`
- Legacy direct-constructor bridge: \`legacy_conversion_workspace.py\`

\`\`\`text
ConvertVerifiedUseCase
  -> ConversionWorkspaceFactoryPort.create(output_directory)
  -> ConversionWorkspacePort.write_prepared(fds_text, mapping_plan)
  -> GeometryPackageWriterPort.write(model, workspace.geometry_path, workspace.owner)
  -> manifest.reseal()  # unchanged science + integrity semantics
  -> ConversionWorkspacePort.write_draft(model, configuration, manifest)
  -> release converter meshes
  -> ConversionWorkspacePort.read_fds()
  -> Independent AuditConversionUseCase.execute(...)
  -> ConversionWorkspacePort.finish_audit(manifest, status, timings)
\`\`\`

## Behavior freeze / Bảo toàn hành vi

The adapter preserves the following existing filenames and encodings:

| Artifact | Persistence contract |
|---|---|
| \`model.fds\` | UTF-8 bytes written before audit and re-read from disk |
| \`mapping_plan.json\` | \`MappingPlan.model_dump_json()\` |
| \`model_geometry.json\` | unchanged geometry writer with external payloads |
| \`model_manifest.json\` | \`MappingManifest.model_dump_json()\`, rehydrated for audit |
| \`model_inventory.json\` | canonical dump excluding inline mesh payloads |
| \`model_mep_graph.json\` | JSON copy of source MEP graph |
| \`model_configuration.json\` | JSON conversion configuration |
| \`audit-state.json\` | \`NOT_RUN\` and \`DRAFT_NOT_SEALED\` until audit completes |

A mapping checkpoint is sealed **only** when the independent audit returns
\`MAPPING_VERIFIED\`. Never convert \`NOT_RUN\` / \`INCONCLUSIVE\` to \`PASS\`.

Không ghi dữ liệu chưa kiểm định thành dữ liệu được chấp thuận. Trước khi
auditor kiểm tra nguồn IFC độc lập, trạng thái luôn là \`NOT_RUN\`.

## Compatibility / Tương thích

The production container injects \`LocalConversionWorkspaceFactory\`.
External callers that instantiate \`ConvertVerifiedUseCase()\` directly are
temporarily supported via a compatibility bridge. This bridge is isolated
from the application implementation and should be retired in a subsequent
migration once all consumers are known.

## Verification / Kiểm thử

- \`tests/test_conversion_workspace.py\`: output format, file naming,
  checkpoint invariants, portable inventory, and no filesystem I/O in use case.
- Existing \`tests/test_conversion_ports_di.py\` for port invocation order
  and draft checkpoint before independent audit.
- Frozen A–F semantic baselines, Python / browser / JavaScript / FDS solver CI.

## Next phase

Further decomposition of independent validation is out of scope and requires
gate-by-gate parity. The current \`validation.engine\` remains authoritative.
