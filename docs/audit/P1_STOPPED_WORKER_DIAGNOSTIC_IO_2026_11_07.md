# P1 — Giữ nguyên lý do terminal sau khi kill worker và diagnostic I/O lỗi

**Ngày:** 07/11/2026. **Finding:** `IO-STOPPED-DIAGNOSTIC-01`. **Gate:** G05. **Trạng thái:** `FIXED_PENDING_VERIFICATION`.

## Root cause

`JobService._run_loop_until_io_failure` dừng worker trước khi `_terminal_diagnostic` ghi `diagnostics.json` ở hai đường `RESOURCE_EXHAUSTED` và `deadline`. Nếu ghi diagnostic gây `OSError`, supervisor wrapper (#59) retry, nhưng process đã bị kill, SQLite vẫn là RUNNING. Lượt tiếp theo có thể rơi sang `proc.poll() != None`, ghi FAILED / `Worker exited -9` thay cho `TIMED_OUT` hoặc `RESOURCE_EXHAUSTED`; thiếu hoặc sai diagnostic, gây sai lệch provenance.

## Bản sửa

- `_finish_stopped_worker()` ghi diagnostic trước, sau đó mới commit trạng thái terminal, rồi mới cleanup tệp nguồn.
- Nếu diagnostic I/O lỗi sau khi kill worker, lưu private `_pending_terminal[jid]` cùng `_pending_diagnostic[jid]`; tiếp tục thử ghi diagnostic trước SQLite trên lượt scheduler kế tiếp, không cho nhánh generic worker-exit ghi đè.
- Nếu SQLite lỗi sau khi diagnostic thành công, giữ terminal intent cũ và retry SQLite; không lặp ghi diagnostic hay cleanup.
- `cancel()` thành công xóa các pending intent vì người dùng đã quyết định trạng thái CANCELLED hợp lệ.
- Không persist intent chưa commit như trạng thái thật; restart sau power loss vẫn fail-closed, G05 chưa thể PASS.

## Regression

`tests/test_job_stopped_worker_diagnostic_io.py` gồm 4 kịch bản: deadline và RSS, mỗi kịch bản phục hồi diagnostic ngay hoặc sau đó có thêm lỗi SQLite. Assert SQLite vẫn RUNNING, file IFC còn nguyên trong cửa sổ lỗi, diagnostic và terminal reason khớp sau phục hồi, không bị `Worker exited -9`, chỉ kill worker một lần.

## Hạn chế

Chưa thực hiện power-loss drill, disk-full thực, cross-process recovery hay independent scientific verification. Tests/CI trên PR HEAD cần được xác minh trước merge; check PASS chỉ xác nhận các đường hồi quy, không cấp `SIMULATION_VERIFIED` hay production readiness.
