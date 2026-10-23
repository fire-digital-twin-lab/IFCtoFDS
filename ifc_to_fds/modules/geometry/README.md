# Hình học

Cung cấp mesh/boolean/metrics, native extraction, cache và portable geometry evidence.

## Tổ chức

algorithms/ không mở filesystem/process/network; infrastructure/ sở hữu native kernel và payloads/cache; application/package_service.py tiêu thụ StoredGeometryEvidence protocol. Seal/checksum thuần nằm ở algorithms/sealing.py.

| File/package | Vai trò |
| --- | --- |
| `algorithms/boolean.py` | Implementation nội bộ |
| `algorithms/mesh.py` | Implementation nội bộ |
| `algorithms/metrics.py` | Implementation nội bộ |
| `algorithms/sealing.py` | Implementation nội bộ |
| `api.py` | API công khai |
| `application/package_service.py` | Implementation nội bộ |
| `contracts.py` | Hợp đồng công khai |
| `infrastructure/cache.py` | Implementation nội bộ |
| `infrastructure/ifcopenshell/extraction.py` | Implementation nội bộ |
| `infrastructure/payload_store.py` | Implementation nội bộ |
| `infrastructure/preview_cache.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `DiskPackage`, `SolidCandidateIndex`, `archive_package`, `as_trimesh`, `audit_package`, `bounds_for_vertices`, `box_mesh`, `build_package`, `cached_geometry`, `calculate_bbox_iou`, `compare_solids`, `copy_package`, `create_geom_settings`, `digest`, `extract_element_geometry`, `file_hash`, `inspect_mesh_quality`, `intersects_box`, `is_axis_aligned_box`, `mesh_evidence_scope`, `mesh_from_geometry`, `metrics_pass`, `opening_residual`, `passage_metrics`, `payload_dir`, `process_model_geometry`, `process_reference_geometry`, `read_package`, `read_preview`, `restore_package`, `save_preview`, `seal`, `solid_boolean`, `store_mesh`, `valid_solid`, `verify_opening_retention`, `verify_package`, `write_package`.

Module phụ thuộc: không có module khác. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/geometry -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
