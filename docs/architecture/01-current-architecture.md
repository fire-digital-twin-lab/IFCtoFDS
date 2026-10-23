# 01 - Kiến trúc đang chạy

Cập nhật 22/10/2026 sau kế hoạch P00–P10. Backend phát hành trong một package, frontend đóng kèm bản phân phối. Đường dẫn dưới đây tương đối với `ifc_to_fds/`.

| Module | Implementation chính |
| --- | --- |
| BIM | `modules/bim/infrastructure/ifc/`: inventory, placement, units, source_loader, preview, reader và MEP; so graph thuần trong `domain/mep_comparison.py` |
| Simulation | `modules/simulation/application/`: mapping_policy, spatial_scope, boundary_policy, plan_validation; boundary cases trong domain; implementation digest trong infrastructure |
| Geometry | `modules/geometry/algorithms/`: mesh, boolean, metrics, sealing; native extraction/cache/payload trong infrastructure; package_service trong application |
| FDS | `modules/fds/application/`: serializer, manifest_builder; `parsing/namelist.py` độc lập exporter; infrastructure chứa exporter adapter |
| Verification | `modules/verification/application/`: engine, runner/checkers, saved_evidence, boundary acceptance/certification; infrastructure chứa solver process và engine adapter |
| Reference | `modules/reference/application/`: parity, projections, integrity; infrastructure chứa bundle_io, registry, filesystem_repository |
| Artifacts | `modules/artifacts/infrastructure/`: filesystem_repository, conversion_workspace; contracts định nghĩa checkpoint payload |
| Jobs | `modules/jobs/application/service.py`: queue/supervision; infrastructure chứa SQLite, worker process, retention; factory nối dependencies |

Caller ngoài module dùng `api.py`/`contracts.py`. Mỗi module có README mô tả owner và public surface. Domain model Pydantic vẫn có một định nghĩa trong `domain/`; ownership theo stage được ghi trong [ADR 0001](decisions/0001-module-ownership.md), chưa phải các model context độc lập.

`application/workflows/` điều phối convert/audit/save/prepare xuyên context; ports nằm trực tiếp trong `application/ports/`. `bootstrap/` ghép adapters qua public API. HTTP nằm trong `interfaces/http/`, chia routes health/jobs/previews/artifacts/reference; CLI và worker ở `interfaces/cli/`, `interfaces/worker/`.

Các import cũ là facade một bước tới implementation cuối, giữ cùng module object khi cần cache/monkeypatch. Registry ghi đường dẫn/hash/đích cụ thể. `results.py` giữ wrappers để duy trì override semantics của caller cũ.

Luồng Verified chuẩn bị model, lập MappingPlan, serialize, lưu checkpoint, giải phóng mesh converter rồi mở lại IFC và đầu ra đã lưu để audit độc lập. Engine active là `modules/verification/application/engine.py`; chưa đổi sang runner/checkers.

Frontend dùng IIFE. `frontend/src/app/bootstrap.js` ghép state, viewer và feature dependencies; launcher, shell, workbench bindings tách riêng. Feature trả teardown handle; API clients sở hữu transport, viewer sở hữu tài nguyên 3D. Root HTML vẫn là launcher tương thích. [Báo cáo 14](14-ket-qua-to-chuc-ma.md) ghi kiểm tra và giới hạn nghiệm thu.
