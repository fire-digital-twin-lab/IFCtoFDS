# Định dạng FDS

Serialize kế hoạch, tạo manifest và parse độc lập đầu ra FDS.

## Tổ chức

application/ gồm serializer và manifest_builder; parsing/namelist.py không phụ thuộc serializer; infrastructure/exporter.py là adapter cho workflow port.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `application/manifest_builder.py` | Implementation nội bộ |
| `application/serializer.py` | Implementation nội bộ |
| `infrastructure/exporter.py` | Implementation nội bộ |
| `parsing/namelist.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `FDSRecord`, `FdsExporter`, `MappingManifest`, `SerializationResult`, `build_manifest`, `parse_fds`, `serialize_fds`.

Module phụ thuộc: geometry, simulation. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/fds -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
