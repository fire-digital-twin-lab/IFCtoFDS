# P1 — Ghi trạng thái worker terminal trước khi dọn đầu vào

Ngày: 05/11/2026. Phạm vi chỉ là nhánh `proc.poll() is not None`
trong `JobService._loop`, không thay đổi thuật toán IFC, FDS hay nghiệm thu khoa học.

## Nguyên nhân gốc

Nhánh hoàn tất worker thay đổi dictionary cache bằng `running.update()`,
sau đó gọi `_cleanup(running)` xoá `source-*.ifc`, cuối cùng
`repository.set()` ghi SQLite theo best-effort. Khi SQLite lỗi,
metadata bền vững vẫn RUNNING, nhưng cache có thể COMPLETED/FAILED và
file đầu vào đã bị xóa.

## Thay đổi và kiểm thử

- Tạo bản sao `terminal = dict(running)` để không publish trạng thái
  trong RAM trước commit.
- Gọi `JobRepository.set_durable()` với UPDATE + commit trước cleanup;
  `JobPersistenceError` được ghi log và giữ worker terminal để scheduler
  thử lại ở vòng kế tiếp.
- Khi commit thành công, dọn source và request theo chính sách hiện có.
- `tests/test_job_terminal_durability.py` giả lập disk-full, kiểm tra
  RAM/SQLite/source giữ nguyên, sau đó phục hồi DB và chạy lại một vòng
  scheduler để xác nhận trạng thái FAILED và cleanup.

## Điều kiện nghiệm thu và giới hạn

**FIXED_PENDING_VERIFICATION** đến khi CI trên HEAD của PR PASS.
Không kết luận đã xử lý queue-timeout, resource-exhaustion, process
spawn failure, startup-recovery, multi-instance writers, hoặc crash
trong khoảng giữa SQLite commit và filesystem cleanup.
Không cấp `MAPPING_VERIFIED` hay `SIMULATION_VERIFIED` từ job status.


## Bổ sung nghiệm thu GitHub — 05/11/2026

- PR #40 đã merge vào `main` tại `d04771db4f9f584b98a1bab1d9d03a028cd769ab`.
- Nhánh PR #39 đã đồng bộ bằng merge commit `39caa95749467b11eaff4060bc403c58cdb6f6db`.
- Hai workflow `pull_request` trên commit đồng bộ PASS: [Conversion #41980077859](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41980077859) và [Quality #41980077747](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41980077747).
- Một `push` run khác từ lúc tạo nhánh phụ thuộc #41 dùng chính SHA này bị hủy do các commit tiếp theo trên nhánh mới. GitHub có thể gộp required check contexts của các run cùng SHA, nên vẫn phải kiểm tra trạng thái merge trên **HEAD cuối**. Không nới lỏng required checks.
- Công việc này chỉ bảo đảm nhánh worker đã kết thúc; các đường queue/startup/missing worker có PR #41 riêng, và các đường execution-timeout, resource-exhaustion, spawn vẫn mở.

**Ghi chú:** cập nhật tài liệu này tạo HEAD mới nhằm lưu lại provenance và đối chiếu CI. Trạng thái PR chỉ được nâng lên VERIFIED khi GitHub Actions trên HEAD mới đạt và nhánh được merge bình thường.
