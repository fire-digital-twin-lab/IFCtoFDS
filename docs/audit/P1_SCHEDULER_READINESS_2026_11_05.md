# Scheduler liveness / readiness probe — 05/11/2026

## Finding

Trước sửa đổi, `GET /api/health` trả HTTP 200 dù scheduler thread
có thể đã chết; do đó HTTP liveness không đại diện cho khả năng xử lý job.

## Cơ chế bổ sung

- `GET /api/health` giữ nguyên để phân biệt tiến trình HTTP còn sống.
- `GET /api/scheduler-health` trả HTTP 503 khi JobService đã đóng,
  khi thread đã từng khởi chạy nhưng không còn sống, hoặc khi có job
  QUEUED/RUNNING mà chưa có supervisor thread.
- Khi chưa nhận job nào, thread chưa tạo là trạng thái bình thường
  (scheduler lazy-start), trả 200.
- Endpoint thuộc `/api/*`, chịu cùng bảo vệ `IFCFDS_API_KEY` khi
  khóa được cấu hình; không công khai ID job, queue contents hoặc secret.
- Hàm kiểm tra chỉ đọc và không sửa trạng thái job/artifact.

## Bằng chứng và giới hạn

`tests/test_scheduler_readiness.py` kiểm thử:
- Idle healthy, missing thread, dead thread, closed service, active thread.
- Phân biệt `/api/health` 200 và `/api/scheduler-health` 503.
- Guard API key với endpoint monitoring.

**Chưa đủ nghiệm thu G14**: không thay thế kiểm tra SQLite write availability,
scheduler heartbeat liên tục, queue backlog age, metrics, external alerting,
process supervisor, load balancer readiness, dashboards hoặc runbook trực chiến.

Chưa có staging/runtime soak evidence; yêu cầu kiểm tra CI trên đúng HEAD
và chạy thử với supervisor đang hoạt động ở staging sau này.
