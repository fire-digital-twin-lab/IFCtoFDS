# Nhật ký song ngữ và sự kiện chẩn đoán (R10-01)

## Mục tiêu

IFCtoFDS lưu **một luồng sự kiện chuẩn** dạng JSONL và sinh **hai bản hiển thị**
tiếng Việt / tiếng Anh. Trạng thái kiểm định, số liệu, source SHA, entity key
và bằng chứng **không được dịch hoặc thay đổi** theo ngôn ngữ.

## Các tệp trong thư mục job

- `progress.json`: trạng thái tiến độ cũ, được giữ tương thích.
- `events.jsonl`: mỗi dòng một sự kiện theo schema 1.0, là nguồn sự thật.
- `events.en.log`: bản tiếng Anh của cùng chuỗi sự kiện.
- `events.vi.log`: bản tiếng Việt của cùng chuỗi sự kiện.

Mỗi sự kiện có `schema_version`, `timestamp` UTC, `level`, `code`,
`stage`, `job_id`, `entity_key` và `params`. Không ghi toàn bộ
mesh, stack trace, API key hoặc mô hình IFC vào các tham số sự kiện.

## Mã sự kiện

Mã sự kiện là định danh ổn định, dạng `IFCFDS.<THÀNH_PHẦN>.<SỰ_KIỆN>`.
Ví dụ `IFCFDS.STAGE.COMPLETED` với `stage` và `elapsed_s`.
Danh mục nằm trong `ifc_to_fds/observability/locales/en.json` và
`vi.json`. CI kiểm tra đủ mã và tham số nội suy ở hai ngôn ngữ.

Tình trạng `PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_RUN` và
`MAPPING_VERIFIED` vẫn giữ nguyên ở artifact/JSON API, không biến thành
kết quả khác qua dịch thuật. Log không được dùng làm bằng chứng thay cho
kiểm định độc lập.

## Sử dụng API Python

```python
from ifc_to_fds.observability import DiagnosticEvent, append_event

append_event(job_directory, DiagnosticEvent(
    code="IFCFDS.STAGE.COMPLETED",
    level="INFO",
    stage="GEOMETRY",
    params={"stage": "GEOMETRY", "elapsed_s": 1.25},
))
```

`progress()` hiện tự tạo các sự kiện giai đoạn tương ứng mà không thay
đổi dữ liệu trong `progress.json`. Nếu ghi log phụ thất bại, chương trình
ghi warning nhưng không đổi kết quả của converter. Trường hợp log phụ bị
gián đoạn giữa các lần ghi, sinh lại hai bản từ JSONL:

```python
from ifc_to_fds.observability import rebuild_localized_logs
rebuild_localized_logs(job_directory)
```

## Ranh giới và việc cần làm tiếp

Đây là **pha đầu**, chưa dịch toàn bộ thông báo trong UI JavaScript,
API response hay mọi thông báo của FDS solver. Các bản human log là
sidecar; chưa được thêm vào danh sách artifact kiểm định có checksum.
Không sửa thủ công `events.jsonl`; không sử dụng bản dịch để ra quyết
định nghiệm thu.

[English version](../en/observability.md)
