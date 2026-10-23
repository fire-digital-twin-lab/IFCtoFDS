# Ý định mô phỏng và mapping

Xác định scope, chiến lược biểu diễn và boundary theo policy đã có.

## Tổ chức

application/ giữ mapping/scope/plan policies; domain/boundary_cases.py là dữ liệu fixture của chứng nhận; infrastructure/implementation_digest.py bind implementation thực.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `application/boundary_policy.py` | Implementation nội bộ |
| `application/mapping_policy.py` | Implementation nội bộ |
| `application/plan_validation.py` | Implementation nội bộ |
| `application/spatial_scope.py` | Implementation nội bộ |
| `contracts.py` | Hợp đồng công khai |
| `domain/boundary_cases.py` | Implementation nội bộ |
| `infrastructure/implementation_digest.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `EXACT_POLICY`, `FIXTURES`, `POLICY`, `SpatialScope`, `VERSION`, `adapter_digest`, `apply_spatial_scope`, `determine_element_strategy`, `fixture_cases`, `fixture_text`, `plan_mapping`, `planned_model`, `target_mesh`, `validate_decisions`.

Module phụ thuộc: geometry. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/simulation -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
