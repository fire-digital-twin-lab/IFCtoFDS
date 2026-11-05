# P1 — Metadata access timestamp durability

**Ngày:** 05/11/2026. **Finding:** IO-PERSISTENCE / retention-vs-download race.

## Lỗi hiện hữu

`JobService.touch()` trước đây thay trực tiếp `job["last_accessed"]`
trong cache, rồi gọi `JobRepository.set()` (best-effort). Khi SQLite
gặp lỗi, cache có thể chứa thời điểm truy cập mới nhưng database vẫn
giữ giá trị cũ. Khởi động lại có nguy cơ hết retention sớm và xóa
artifacts mà HTTP trước đó đã ngầm coi là được bảo vệ.

## Hợp đồng mới

- Tạo bản sao của job và cập nhật `last_accessed` trên bản sao.
- Gọi `set_durable()`, chỉ phát hành bản ghi mới trong RAM sau commit
  SQLite thành công.
- Khi SQLite lỗi, `touch()` ném `JobPersistenceError`. FastAPI trả
  HTTP 503 có thông báo tổng quát; không phát response tải thành công
  khi không thể đảm bảo kéo dài retention.
- Các route đọc result/diagnostics và download hiện dùng chung hàm
  `touch()` nên hưởng cùng điều kiện commit-first.
- Không thay đổi cách hash hoặc verdict khoa học của mô hình IFC/FDS.

## Regression

`tests/test_job_touch_durability.py`:

1. SQLite disk-full khi `touch`: cache và DB vẫn giữ timestamp cũ.
2. SQLite phục hồi: timestamp mới được commit và xuất hiện đồng nhất.
3. HTTP result/diagnostics khi disk-full: trả 503, không phải 200 và
   không sửa sai cache/SQLite.

## Giới hạn còn mở

- Cơ chế hiện tại chỉ quản lý một JobService trong một process; chưa
  có distributed transaction hoặc exclusive lease giữa các replica.
- FileResponse và retention sweep vẫn có khả năng chạy cạnh nhau trên
  filesystem; cần test stress/download streaming và chính sách
  pin/snapshot artifact trước khi tuyên bố an toàn multi-instance.
- Không thay thế toàn bộ các đường `JobRepository.set()` best-effort
  khác (nếu còn), không đóng G05/G06.
- Cần CI đúng HEAD trước khi merge. Không phát hành production bằng
  một PASS unit test.
