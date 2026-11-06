# P1 — Cleanup lỗi I/O không được phá scheduler hoặc status đã commit

**Finding:** `IO-CLEANUP-01`, audit 05/11/2026.  
**Phụ thuộc:** PR #55 (`IO-RETENTION-01`) vì cùng sửa `adapters/jobs/service.py`.

## Bằng chứng

`JobService._cleanup()` xóa `source-*.ifc` và `request.json` bằng `Path.unlink()` nhưng trước bản sửa không bắt `OSError`. Đây là bước xảy ra sau nhiều chuyển trạng thái `set_durable()` và trong `JobService.cancel()`. Nếu thư mục bị lock/permission denied (đặc biệt Windows/antivirus), exception có thể thoát khỏi thread scheduler hoặc làm HTTP cancel trả lỗi mặc dù SQLite đã commit `CANCELLED`. Điều này gây sai lệch quan sát và gián đoạn scheduling.

## Sửa

- Vùng cleanup chỉ xử lý lỗi dọn tệp: lỗi duyệt danh sách, lỗi `unlink` được ghi log `ERROR` với ID job, tên tệp và exception.
- Không xóa ngoài `source-*.ifc` và `request.json`; không ẩn lỗi ở những giai đoạn khác của pipeline.
- Không làm đảo lại terminal state đã commit và không xem cleanup là bằng chứng science; các tệp bị lock được giữ để operator xử lý.
- `tests/test_job_cleanup_nonfatal.py` kiểm tra lock source/request và hủy job đã commit dù cleanup bị từ chối.

## Giới hạn

Chưa giải quyết secure purge, auto retry sau khi tệp hết lock, filesystem crash atomicity hay retention nguồn cho bản nghiên cứu; các mục này tiếp tục mở. Kiểm tra CI trên đúng HEAD trước merge. G05/G06 vẫn chưa được chứng nhận toàn diện; G09/G10 INCONCLUSIVE; production NOT_PRODUCTION_READY.
