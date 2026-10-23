# BIM và nguồn IFC

Đọc source identity, inventory, units, placements, federation và MEP; preview không tự tạo chứng nhận mapping.

## Tổ chức

infrastructure/ifc/ chứa code native; domain/mep_comparison.py so quan hệ theo entity key. Native handle không thuộc inventory query contract.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `contracts.py` | Hợp đồng công khai |
| `domain/mep_comparison.py` | Implementation nội bộ |
| `infrastructure/ifc/diagnostics.py` | Implementation nội bộ |
| `infrastructure/ifc/inventory.py` | Implementation nội bộ |
| `infrastructure/ifc/mep/classifier.py` | Implementation nội bộ |
| `infrastructure/ifc/mep/graph_reader.py` | Implementation nội bộ |
| `infrastructure/ifc/placement.py` | Implementation nội bộ |
| `infrastructure/ifc/preview.py` | Implementation nội bộ |
| `infrastructure/ifc/reader.py` | Implementation nội bộ |
| `infrastructure/ifc/source_loader.py` | Implementation nội bộ |
| `infrastructure/ifc/units.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `IfcOpenShellReader`, `classify_mep_element`, `compute_file_sha256`, `extract_inventory`, `extract_mep_graph`, `extract_placement`, `get_length_unit_scale`, `graph_differences`, `load_sources`, `preview_model`.

Module phụ thuộc: geometry. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/bim -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
