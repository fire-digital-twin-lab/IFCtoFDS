# R10-11 — Lưu bền vững trước khi nhận công việc mới

## Lỗi cần khắc phục

Finding `IO-PERSISTENCE` (P2): phương thức
`JobRepository._persist_job()` từng ghi log rồi trả về khi SQLite
báo lỗi. Đường tiếp nhận `JobService.submit()` vẫn đưa công việc vào
bộ nhớ và có thể khởi chạy worker, mặc dù metadata không được ghi bền vững
và công việc sẽ biến mất sau khi khởi động lại.

## Thiết kế fail-closed tại biên tiếp nhận

1. `JobRepository.register()` dành cho **job mới**: kiểm tra ID chưa có,
   thử ghi SQLite với cơ chế retry hiện hữu, chỉ đưa vào bộ nhớ sau khi
   transaction đã thành công.
2. Nếu lỗi SQLite không khắc phục được, ném `JobPersistenceError`; job
   không tồn tại trong hàng đợi trong bộ nhớ và worker không được khởi động.
3. `JobService.submit()` phải đăng ký thành công trước khi tạo thread
   điều phối; giữ nguyên cách bảo vệ tải lên và giới hạn hàng đợi.
4. Các endpoint tiếp nhận job/inventory/preview/scenario và endpoint
   chuyển đổi đồng bộ trả HTTP 503 cùng thông báo không tiết lộ cấu trúc
   SQLite; xóa thư mục upload nếu việc đăng ký thất bại.
5. Các đường cập nhật trạng thái hiện hữu vẫn giữ cách ghi best-effort để
   không thay đổi một lần quá nhiều hành vi của background worker.

## Kiểm thử và điều kiện nghiệm thu

- Lỗi SQLite vĩnh viễn: `register` ném lỗi, không tạo job ma trong RAM,
  khởi tạo lại repository không tìm thấy job.
- Thành công: commit SQLite xảy ra trước khi job hiển thị trong cache.
- Service: lỗi đăng ký không khởi chạy worker, không tăng số job chờ.
- API: lỗi đăng ký được trả HTTP 503, không để lại bản upload; kiểm thử
  ít nhất các endpoint `/api/jobs`, `/api/preview-jobs`, `/api/inventory`.
- Cần chạy test trên Python 3.10–3.13 Windows/Linux; đồng thời xác minh
  regression, lint, JavaScript, browser và solver hiện hữu không bị ảnh hưởng.

## Giới hạn còn mở

Bản sửa này bảo vệ **admission**, chưa giải quyết hoàn toàn:
- Cập nhật trạng thái `QUEUED → RUNNING → COMPLETED/FAILED` vẫn có
  thể chỉ ghi log khi SQLite bị lỗi sau khi job được nhận.
- Xóa metadata và dọn thư mục artifact cần được đồng bộ giao dịch.
- Tách verify SHA-256/JSON khỏi scheduler lock là công việc độc lập, cần
  kiểm thử concurrency và đo peak RSS/latency trước–sau.

Không thể đóng toàn bộ finding `IO-PERSISTENCE` chỉ bằng đợt này.
Giữ trạng thái **SỬA MỘT PHẦN / CHỜ CI** cho tới khi có bằng chứng cụ thể.
Không tác động tới `MAPPING_VERIFIED`, `SIMULATION_VERIFIED`,
`INCONCLUSIVE`, `REJECTED` hay `NOT_RUN`.
