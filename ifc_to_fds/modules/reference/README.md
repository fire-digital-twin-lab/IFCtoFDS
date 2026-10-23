# Bộ tham chiếu

Quản lý bundle/checksum/approval và so parity; nhận diện case không tự chọn hoặc chấp nhận profile.

## Tổ chức

application/ gồm parity/projections/integrity; infrastructure/ gồm bundle/repository/registry; production workflow inject case_reader.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `application/integrity.py` | Implementation nội bộ |
| `application/parity.py` | Implementation nội bộ |
| `application/projections.py` | Implementation nội bộ |
| `contracts.py` | Hợp đồng công khai |
| `infrastructure/bundle_io.py` | Implementation nội bộ |
| `infrastructure/filesystem_repository.py` | Implementation nội bộ |
| `infrastructure/registry.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `FILES`, `FilesystemReferenceRepository`, `bundle_digest`, `create_candidate`, `golden_gate`, `inspect_case`, `registered_cases`, `research_context`, `resolve_case`, `resolve_sources`, `serialized_geometry`, `source_signature`.

Module phụ thuộc: fds, geometry. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/reference -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
