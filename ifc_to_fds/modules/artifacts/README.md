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

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `LocalConversionWorkspaces`, `LocalFilesystemArtifactRepository`, `verify_run_artifacts`.

Module phụ thuộc: geometry. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ghi và mở lại bundle

Đích xuất phải có phần mở rộng `.fds`, để không đè IFC/JSON hoặc trùng namespace file bằng chứng được sinh kèm. Publisher giữ khóa `.publish-<stem>.lock` bằng thao tác tạo file độc quyền; một writer/inspector đang giữ khóa làm yêu cầu cùng đích bị từ chối, không ghi xen kẽ. Các stem khác nhau vẫn độc lập.

Trước khi thay file đích, adapter mở lại geometry index đã staging và kiểm tra byte payload, không tin riêng object package còn trong bộ nhớ. Payload không được index tham chiếu được loại khỏi bản staging; nguồn không bị sửa. Nếu xuất lại dạng inline, thư mục payload cũ của bundle được loại bỏ. Khi publication lỗi, rollback khôi phục cả file và payload cũ; nếu rollback cũng lỗi, backup được giữ và đường dẫn phục hồi được báo rõ.

```python
from ifc_to_fds.modules.artifacts.api import verify_run_artifacts

integrity = verify_run_artifacts("out/model.fds")
```

API này mở lại 12 artifact thuộc hợp đồng, kiểm các SHA-256 đã ghi và mọi payload được geometry index tham chiếu. Checksum inventory thiếu/thừa tên, đường dẫn lạ hoặc file hỏng bị từ chối. File khác trong thư mục không thuộc phạm vi kiểm tra. `status=PASS` có scope `ARTIFACT_BYTES_AND_GEOMETRY_PAYLOAD_INTEGRITY`, không phải kết luận mapping hay mô phỏng đạt. Checksum manifest là bằng chứng toàn vẹn cục bộ, không phải chữ ký phê duyệt độc lập.

Workspace hạ checkpoint về DRAFT trước khi ghi lại geometry, manifest hoặc metadata của lượt mới. Metadata JSON/state được thay bằng file tạm cùng thư mục để người đọc không nhận JSON dở dang. SEALED chỉ được ghi khi report đạt mapping, manifest báo output hoàn chỉnh và bundle hash vẫn khớp; hoàn tất không hợp lệ giữ INCONCLUSIVE/DRAFT.

## Giới hạn vận hành

Đây là khóa cho các thao tác hợp tác qua API và rollback khi có exception, không phải transaction nhiều file chống mất điện. Nếu tiến trình chết, khóa có thể còn lại; cần kiểm tra writer/backup rồi phục hồi thủ công. Không tự xóa khóa theo tuổi file. Inspector cần quyền ghi thư mục để giữ cùng khóa với publisher. Chưa có bằng chứng soak/crash hoặc filesystem mạng.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/artifacts -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
