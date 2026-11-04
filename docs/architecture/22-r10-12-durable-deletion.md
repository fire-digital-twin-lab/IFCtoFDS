# R10-12 — Xóa công việc theo thứ tự xác nhận SQLite

## Vấn đề

Xóa một công việc có hai loại tài nguyên: metadata SQLite/cache và thư mục
artifact. Trước đợt này `JobRepository.delete()` bỏ cache trước khi xác
nhận SQL, trong khi đường retention/dọn khi khởi động có thể xóa artifact
trước SQL. Nếu SQLite lỗi, trạng thái trả về và dữ liệu trên đĩa mâu thuẫn.

## Biên giao dịch

1. Xóa hàng SQLite trong transaction, retry ngắn cho LOCKED/BUSY.
2. **Sau khi commit thành công**, mới loại ID khỏi cache.
3. Khi SQL lỗi, raise `JobPersistenceError`; API DELETE báo HTTP 503 và
   không xóa artifact, không tuyên bố xóa thành công.
4. Retention/cleanup chỉ dọn artifact sau SQL; khi DB lỗi vẫn giữ file và
   ghi log, vòng điều phối còn hoạt động.
5. Nếu SQLite đã commit nhưng dọn filesystem lỗi, thư mục mồ côi còn được
   giữ để bảo trì tường minh; không báo đã nghiệm thu toàn bộ cleanup.

## Bằng chứng và giới hạn

- `tests/test_job_deletion_persistence.py`: các đường lỗi SQLite và bảo
  toàn metadata/artifact; giữ phân biệt HTTP 503 với HTTP 404/409.
- Yêu cầu kiểm toàn bộ Python matrix, JS, browser, pinned FDS solver và
  workflow quality trên **HEAD** PR #34.
- Đây không phải giao dịch nguyên tử trải qua SQLite và filesystem.
  Cập nhật status `set()`, crash/restart, đa tiến trình, benchmark RSS/
  latency và scheduler lock vẫn cần giải pháp và bằng chứng riêng.
- Không chỉnh thuật toán khoa học, FDS, solver, sai số hoặc acceptance
  verdict; không chuyển `NOT_RUN`/`REJECTED`/`INCONCLUSIVE` thành PASS.
