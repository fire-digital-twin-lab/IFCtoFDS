# Audit đang mở

Thư mục này chỉ chứa **audit còn hiệu lực**. Agent đọc mọi tệp ở đây trước khi lập kế hoạch hoặc sửa mã (quy tắc trong `AGENTS.md`).

## Thêm một audit
- Đặt tên `AUDIT_<YYYY-MM-DD>_<chủ-đề>.md`, ví dụ `AUDIT_2026-11-20_hvac.md`. Tệp `.docx` hoặc `.pdf` cũng được, nhưng nên kèm một bản `.md` tóm tắt để agent đọc được.
- Đầu tệp ghi: ngày, commit đã audit (`git rev-parse --short HEAD`), người hoặc công cụ audit, phạm vi.
- Mỗi phát hiện có ID riêng (ví dụ `F1`, `F2`), mức độ, vị trí (tệp và dòng), ca tái hiện, đề xuất sửa. Agent giữ nguyên ID khi báo cáo và commit.
- Không ghi tên tệp IFC thật, đường dẫn riêng hay dữ liệu khách hàng; dùng bí danh A/B/C như phần còn lại của repo.

## Khi xử lý xong
- Ghi kết quả từng ID vào [kế hoạch production](../plans/production-roadmap.md) (Phần A) hoặc commit sửa lỗi.
- Khi mọi ID đã xử lý hoặc đã chuyển thành mục trong kế hoạch, **xóa tệp audit** khỏi thư mục này (lịch sử git vẫn giữ). Audit đã đóng mà còn nằm đây sẽ làm agent tưởng lỗi còn mở.
- Gói audit cũ có bằng chứng cần giữ thì chuyển sang `docs/history/`.
