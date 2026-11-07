# P1 — Atomic diagnostic publication để tránh nhận file JSON nửa chừng

**Ngày:** 07/11/2026. **Finding:** `IO-DIAGNOSTIC-PARTIAL-01`. **Phụ thuộc:** [PR #63](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/63), cần merge theo thứ tự. **Trạng thái:** `FIXED_PENDING_VERIFICATION`.

## Lỗi

`JobService._terminal_diagnostic()` dùng `Path.write_text` trực tiếp. Khi disk-full, permission change hoặc process crash giữa quá trình ghi, một file `diagnostics.json` chưa hoàn chỉnh có thể tồn tại. Lần retry `diag_path.is_file()` sẽ bỏ qua tạo lại và cho phép terminal commit dù diagnostic hỏng. Điều này tác động các đường timeout, memory, queue, validation và kiểm toán bằng chứng.

## Khắc phục

- Ghi JSON vào tên tạm riêng (`.diagnostics-<uuid>.tmp`) trong cùng thư mục, `flush` + `fsync` trước khi publish.
- `os.link(temp, diagnostics.json)` là thao tác tạo tên kết quả **atomically only-if-absent** trên filesystem hỗ trợ hard link, tránh ghi đè diagnostic do worker tạo trước hoặc cùng lúc.
- Không fallback sang `write_text` không nguyên tử khi filesystem từ chối hard link: fail closed và retry/report OSError.
- `finally` dọn tệp tạm, ghi log nếu cleanup lỗi; không đổi mapping IFC/FDS, trạng thái khoa học hay nội dung JSON đã quy định.

## Regression

`tests/test_job_atomic_terminal_diagnostic.py`: ghi thành công/cleanup; fsync lỗi sau viết tạm; atomic publish lỗi; worker diagnostic xuất hiện đồng thời và phải được giữ nguyên. Kết hợp PR #63 để bảo toàn reason khi retry.

## Hạn chế

- File đã tồn tại từ phiên bản trước có thể đã hỏng; cần audit hợp đồng cấu trúc trước khi chấp nhận evidence hiện hữu, xử lý trong finding riêng.
- `fsync` tệp không thay thế diễn tập mất nguồn/metadata directory fsync hay crash-consistency của SQLite.
- Hard link có thể không được hỗ trợ trên một số NFS/object-mount; đường đó fail closed, không tuyên bố tương thích đa filesystem.
- Chưa có chạy kiểm thử trên actual staged Windows filesystems hoặc hạ tầng production. G05 `IN_PROGRESS`; G09/G10 vẫn `INCONCLUSIVE`; `NOT_PRODUCTION_READY`.
