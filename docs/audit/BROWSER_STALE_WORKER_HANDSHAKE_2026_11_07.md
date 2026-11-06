# P2 — Stale-worker browser E2E có race với verified conversion

**Ngày:** 07/11/2026. **Finding:** `CI-BROWSER-HANDSHAKE-01`. **Trạng thái:** `FIXED_PENDING_VERIFICATION`.

## Bằng chứng và giả thuyết nguyên nhân

Tại [PR #60, Conversion correctness #42265579572, attempt 1](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42265579572), năm test `pytest -m browser` PASS, nhưng `scripts/test-conversion-browser.py` bị `Page.wait_for_function("window.oldRequest")` timeout 60 giây ở dòng 224. Chạy lại **riêng job browser trên cùng HEAD** (attempt 2) PASS. Đây là flakiness có bằng chứng; không kết luận runner lỗi hay ứng dụng PASS toàn diện.

Nhìn code: trước khi tiêm stale-worker, script chỉ chờ `count-obsts > 0` — điều kiện có thể đã đúng từ lần quick conversion trước đó. `exportVerified()` là async; trạng thái `exportBusy` có thể chưa clear khi script gọi click `#convert-ifc`. `exportIfc()` chủ động `return` nếu `exportBusy`, vì vậy không có lệnh `createExportWorker()` và `window.oldRequest` không bao giờ được ghi. Đây là **nguyên nhân khả dĩ từ đường điều khiển**, chưa chứng minh bằng stack dump của lần timeout trước.

## Khắc phục trong browser E2E

- Trước khi tiêm fake worker, chờ `#convert-ifc` enabled và `#convert-verified[aria-busy]` không còn `true`.
- Reset `window.oldRequest` và `window.oldMessage` trước mỗi lượt để không dùng sai request của lượt trước.
- Nếu chờ `oldRequest` lỗi, lưu `stale-worker-handshake.json` (trạng thái UI, handler) và screenshot trong artifact browser, không swallow lỗi, không retry ngầm.
- Giữ nguyên kết luận fail-closed stale-worker cũ; không sửa product logic hoặc khoa học.

## Nghiệm thu còn thiếu

Bắt buộc chạy full browser workflow trên HEAD PR và merge SHA; theo dõi flakiness nhiều lượt, không tuyên bố đã loại bỏ hoàn toàn chỉ từ một lần PASS. G04 chưa PASS nếu chưa có staging E2E thực, G09/G10 vẫn INCONCLUSIVE và hệ thống NOT_PRODUCTION_READY.
