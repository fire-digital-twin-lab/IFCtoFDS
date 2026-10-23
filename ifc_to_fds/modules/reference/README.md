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

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `FILES`, `FilesystemReferenceRepository`, `bundle_digest`, `create_candidate`, `golden_gate`, `inspect_case`, `is_approved_reference`, `registered_cases`, `research_context`, `resolve_case`, `resolve_sources`, `serialized_geometry`, `source_signature`.

Module phụ thuộc: fds, geometry. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Quy trình và bằng chứng

1. `create_candidate` tạo một revision mới ở trạng thái DRAFT và từ chối ghi đè bundle đã có dữ liệu.
2. `inspect_case` kiểm tra checksum, byte của mọi payload geometry và các liên kết sources/domain/inventory/ports/openings/FDS với golden manifest. Tính lại checksum không làm hợp lệ một bundle tự mâu thuẫn.
3. Phê duyệt cần `status=APPROVED`, reviewer và rationale là chuỗi không chỉ chứa khoảng trắng, evidence là danh sách không rỗng gồm các chuỗi có nội dung. CLI, parity và registry dùng chung `is_approved_reference`. DRAFT, SUPERSEDED hoặc khai báo phê duyệt thiếu/sai kiểu không được coi là đã phê duyệt.
4. `golden_gate` đối chiếu nguồn, bản xuất FDS và gói hình học đang audit với bộ chuẩn. Delta phải gắn đúng digest, chỉ rõ entity/field/before/after và bằng chứng; alias còn phải chứng minh biến đổi cứng và tương đương hình học. Delta không miễn các gate độc lập của đầu ra.

`registered_cases` kiểm tra nội dung và payload trước khi công bố `integrity_status=VERIFIED`. Bundle lỗi trả CORRUPTED/UNVERIFIED_CORRUPT; khai báo APPROVED thiếu bằng chứng hợp lệ trả UNVERIFIED_APPROVAL. Một cấu hình case lỗi không che các case hợp lệ khác. Kiểm tra này đọc toàn bộ payload, nên chi phí phụ thuộc kích thước vault.

`python -m ifc_to_fds reference-check CASE_DIRECTORY` trả 0 khi integrity và khai báo phê duyệt hợp lệ, 2 khi chưa được phê duyệt, 3 khi bundle lỗi. `data_integrity_verified` và `human_approval_verified` được công bố riêng.

Đây là hồ sơ xét duyệt cục bộ, không xác thực danh tính reviewer bằng chữ ký số. Phần mềm không tự phê duyệt candidate. Reference của fixture chỉ chứng minh phạm vi fixture; nghiệm thu dự án thực vẫn cần bộ chuẩn độc lập và người thẩm tra có thẩm quyền. Schema 0.4.0 còn đọc được nhưng parity yêu cầu revision mới trước khi PASS.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/reference -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
