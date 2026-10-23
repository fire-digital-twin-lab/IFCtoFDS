# Artifacts và checkpoint

Lưu kết quả, geometry package và checkpoint với trạng thái nghiệm thu rõ ràng.

## Tổ chức

infrastructure/ không tính portable inventory; workflow chuẩn bị CheckpointPayload. TemporaryDirectory owner được chuyển cho geometry package để giữ payload sống đủ lâu.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `contracts.py` | Hợp đồng công khai |
| `infrastructure/conversion_workspace.py` | Implementation nội bộ |
| `infrastructure/filesystem_repository.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `LocalConversionWorkspaces`, `LocalFilesystemArtifactRepository`.

Module phụ thuộc: geometry. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/artifacts -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
