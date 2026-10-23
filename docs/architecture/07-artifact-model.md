# 07 — Artifacts và checkpoint

`modules/artifacts/repository.py` quản lý xuất bundle/checksum. Conversion workspace quản lý checkpoint trước và sau audit. Geometry index và binary payload nằm trong Geometry; result JSON không nhúng toàn bộ mesh/FDS lớn.

Trước audit, lưu FDS, geometry, manifest, inventory, MEP graph, configuration và audit-state. Checkpoint mang trạng thái NOT_RUN/DRAFT_NOT_SEALED và không được xem là output verified. Auditor đọc lại FDS/manifest đã ghi, rồi lưu kết quả hoàn thiện theo logic hiện tại.

Temporary directory owner được giữ trong geometry package. Payload có hash và kiểm tra cấu trúc; hash đúng không tự chứng minh hình học đúng. Kiểm tra độc lập phải đối chiếu nguồn, representation, openings, role và bounds.

Artifacts của job hoàn tất và checkpoint của job chưa hoàn tất có endpoint khác nhau. Endpoint checkpoint giữ header cảnh báo unaccepted. Chỉ phục vụ tên artifact/payload được liên kết và cho phép; không mount repository hoặc job directory thành static server.

Các kiểm tra chính: artifact storage/lifecycle, corruption, zip-slip, rollback, inventory sanitization và checkpoint resealing.
