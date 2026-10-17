# 15 — Chiến lược tích hợp: fork JS + Python IfcOpenShell

## Integration contract phải chứng minh

Luồng VERIFIED phải thực sự đi qua Python + IfcOpenShell, không chỉ thêm dependency rồi UI vẫn chạy geometry native parser. Source chuẩn ở `ifc-core/`, exporter phải tiêu thụ canonical geometry/approved `MappingDecision`.

## Lộ trình kỹ thuật

**Bước A — Fork baseline**

- Verify repo, parent, default branch, tag `v0.1.0`, commit SHA, clean worktree.
- Chạy tests gốc; giữ `index.html` mở được và viewer/quick mode hoạt động.

**Bước B — Python CLI extract**

- Pin phiên bản Python/IfcOpenShell sau khi cài thành công; đọc một IFC, xuất inventory/geometry references/source metadata.
- `ifcopenshell.geom.iterator` cho geometry batch, `ifcopenshell.util.*` cho units/placements/systems, test với IFC2x3/IFC4 fixtures.
- JSON/sidecar validate schema, tránh huge JSON; số đếm element không chỉ dựa vào các shape hợp lệ.

**Bước C — Canonical model**

- Dựng source transforms, MEP graph, status/reason cho mọi product; consistency tests.
- `CanonicalSceneAdapter` dịch schema Python sang format UI/exporter mà không nhân đôi geometry authority.

**Bước D — FDS exporter**

- Refactor `js/fds/fds-exporter.js` hoặc triển khai serializer canonical mới; có golden regressions với upstream.
- Chọn một serializer authoritative cho Verified để tránh hai code paths tạo results khác nhau.
- Khi sửa workers JS phải sinh lại inline bundles và chạy parity tests.

**Bước E — Audit CLI**

- `verify --source [IFC...] --fds converted.fds --manifest mapping-manifest.json --config conversion.json`.
- Reopen inputs, rebuild checks, generate findings/acceptance.

**Bước F — FastAPI bridge**

- API import → inventory → conversion jobs → artifacts → audit findings, phục vụ frontend cùng origin khi có thể.
- Không để frontend gọi `subprocess` trực tiếp; giới hạn input, timeouts, read-only source storage, cancellation.

## Endpoint đề xuất (cần điều chỉnh sau ADR)

```text
POST /api/v1/models/import
GET  /api/v1/models/{id}/inventory
GET  /api/v1/models/{id}/systems
POST /api/v1/conversions
GET  /api/v1/conversions/{run_id}
GET  /api/v1/conversions/{run_id}/audit
GET  /api/v1/conversions/{run_id}/artifacts/{artifact_name}
```

- `POST conversions` có input IDs, `scope`, `mappingPolicy`, `toleranceProfile`, `schemaVersion`; response có runId/status, không dối rằng task hoàn thành đồng bộ.
- Tất cả artifacts gắn checksum, `Content-Disposition` filename an toàn; failure có `errorCode`, `details` không leak filesystem secrets.
- FastAPI là lớp adapter, nghiệp vụ ở Python core độc lập với HTTP.

## Giao thức CLI dự kiến

```text
ifc-fds inspect --ifc A.ifc --ifc B.ifc --out RUN/inventory.json
ifc-fds convert --config conversion.json --output RUN/
ifc-fds validate --config conversion.json --source A.ifc --fds RUN/converted.fds --manifest RUN/mapping-manifest.json
ifc-fds report --run RUN/ --format html
```

Đây là **interface đề xuất**, không phải lệnh có sẵn. Agent phải triển khai và ghi docs/test tương ứng, không dùng các lệnh này làm bằng chứng đã tồn tại.

## Version / dependency strategy

- Pin các dependencies; ghi `pip freeze` / lock file và workflow package install reproducible.
- Kiểm tra license LGPL core, AGPL fork; không copy GPL BFDS files vào code runtime khi chưa có license review.
- CLI must work fully offline once dependencies installed. Legacy CDN behavior được xem xét riêng.
