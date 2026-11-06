# P1 — Download lease ngăn purge/retention cắt ngang artifact response

**Ngày:** 07/11/2026. **Finding:** `OPS-DOWNLOAD-01 / G06`. **Trạng thái:** `FIXED_PENDING_VERIFICATION`.

## Đường lỗi xác nhận

Server công bố `FileResponse` cho `diagnostics`, `artifacts`, `checkpoints`, `geometry`, và `StreamingResponse` cho geometry batch sau khi nhả khóa scheduler. Starlette mở file và truyền nội dung **sau khi** handler trả về. Vì vậy `DELETE /api/jobs/{jid}?purge=true` hoặc retention có thể xóa SQLite row và thư mục job trước/trong response. Bản hash pass ở bước tiền kiểm không giải quyết khoảng hở này.

## Bản sửa

- `JobService.acquire_artifact_lease()/release_artifact_lease()` đếm lượt đọc theo job, có khóa chung.
- `LeasedFileResponse` và `LeasedStreamingResponse` nhả lease trong `finally` khi response hoàn tất hoặc bị hủy.
- Các route phải lấy lease **trước khi** verify/hash dài ngoài `manager.lock`, và nhả khi validate hoặc khởi tạo response thất bại.
- Purge job terminal khi có lease báo HTTP `409`, không xóa row/tệp, không công bố `DELETED`. Live retention và startup/manual retention không xóa job đang có lease.
- Không thay đổi whitelist URL, evidence hashes, IFC geometry, scientific acceptance hoặc FDS output.

## Regression

`tests/test_job_artifact_download_lease.py`: response diagnostics chưa thực thi, HTTP purge phải 409; SQLite và artifact còn nguyên; response normal/disconnect đều giải phóng lease, purge tiếp theo 200; hai lượt tải song song vẫn giữ khóa; startup retention bỏ qua job đang được tải; geometry endpoint reject phải giải phóng lease.

## Giới hạn nghiệm thu

Cơ chế chỉ có hiệu lực trong **một process**. Staging/production hiện đòi exclusive job root, nhưng chưa chứng minh mọi external process/restore tool tôn trọng nó. Không bảo đảm trước xóa trực tiếp ngoài service, network filesystem không tương thích, crash OS, disk-full, hoặc shutdown cắt ngang streaming. Không thay đổi trạng thái G06 khỏi `INCONCLUSIVE` trước khi test matrix, staging fault-injection, race soak và sign-off. Solver CI PASS không phải chứng nhận CFD.
