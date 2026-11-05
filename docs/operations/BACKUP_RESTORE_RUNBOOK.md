# Backup / Restore Runbook — IFCtoFDS (Offline, Single Instance)

**Trạng thái:** quy trình kỹ thuật thử nghiệm; chưa được diễn tập trên staging hoặc production. **G12 = NOT_RUN** cho đến khi có bằng chứng runtime trên hạ tầng thực, checksum và phê duyệt phục hồi. Không dùng quy trình này để tạo live snapshot nhất quán khi worker đang chạy.

## Phạm vi

- Sao lưu SQLite `jobs.sqlite3` bằng SQLite backup API (bao gồm dữ liệu đã commit trong WAL).
- Sao lưu toàn bộ tệp **và thư mục rỗng** nằm trong các thư mục `job-*`, gồm artifact/evidence hiện hữu, không theo symbolic link. Manifest schema 2 bắt buộc có danh sách `directories` để khôi phục job ngay cả khi thư mục artifact không chứa tệp.
- Xuất `manifest.json` cuối cùng với SHA-256 và kích thước từng tệp.
- Khôi phục vào **thư mục đích chưa tồn tại**; kiểm tra toàn bộ checksum trước khi tạo đích, xác minh SQLite, cập nhật đường dẫn tuyệt đối `jobs.directory` sang thư mục mới.
- Không sửa, dọn hoặc ghi đè job store gốc.

## Điều kiện bắt buộc trước khi backup

1. Dừng API và các tiến trình worker bằng quy trình điều phối đã được nghiệm thu; hạn chế nhận job mới. Chỉ chạy sau khi các tiến trình thực sự đã thoát.
2. Xác nhận không còn trạng thái `QUEUED` / `RUNNING` trong SQLite. Công cụ cũng kiểm tra và sẽ từ chối khi tìm thấy. Việc kiểm tra này **không phải** distributed lock và không chứng minh hệ thống đã dừng.
3. Đảm bảo đủ disk space tại nơi backup; các artifact có thể rất lớn.
4. Kiểm tra quyền chỉ đọc/ghi phù hợp, mã hóa vùng lưu trữ và chính sách bảo mật dữ liệu công trình. Công cụ **không tự mã hóa hoặc ký số** backup.
5. Chọn thư mục backup chưa tồn tại, không nằm trong job store, không có symbolic link chuyển hướng.

## Backup

```bash
python -m ifc_to_fds.operations.offline_backup backup \
  --job-root /srv/ifctofds/jobs \
  --destination /srv/backups/ifctofds-2026-11-05
```

Đầu ra hợp lệ phải có `manifest.json` và `jobs.sqlite3`. Nếu công cụ dừng giữa chừng, backup có thể thiếu `manifest.json`, phải coi là **INCOMPLETE**, không đưa vào hệ thống phục hồi.

## Verify và restore vào thư mục cô lập

```bash
python -m ifc_to_fds.operations.offline_backup restore \
  --source /srv/backups/ifctofds-2026-11-05 \
  --destination /srv/ifctofds-restore-test/jobs
```

Đích phải chưa tồn tại. Công cụ không có `--force`, không xóa dữ liệu và từ chối checksum không khớp, thiếu tệp/thư mục (kể cả thư mục rỗng), thư mục không được manifest khai báo, symlink, đường dẫn traversal, SQLite integrity lỗi hoặc metadata thư mục không hợp lệ. Manifest v1 cũ không còn được chấp nhận để tránh bỏ sót các thư mục rỗng.

Sau khi restore: xác minh `jobs.sqlite3`, các bản ghi job đã kết thúc và artifact/evidence, chạy ứng dụng trong môi trường cô lập bằng cấu hình riêng, kiểm tra restore khi API/worker không dùng root production. Không đổi DNS hoặc root đang phục vụ lưu lượng nếu chưa phê duyệt chuyển đổi.

## Disaster recovery và hoạt động sau sự cố

1. Khoanh vùng lỗi, khóa đầu vào nhận job mới và đảm bảo nguồn gốc backup.
2. Kiểm tra backup đã được tạo từ bản release/hợp đồng schema tương thích; không tự động rollback schema.
3. Restore vào đích mới bằng lệnh trên, kiểm tra checksum và `PRAGMA integrity_check`.
4. Kiểm tra toàn bộ `jobs.directory` trỏ về đích mới, so sánh số job và artifact với manifest.
5. Cập nhật cấu hình `IFCFDS_JOB_ROOT` cho môi trường thử nghiệm, chạy API/worker theo runbook, kiểm tra smoke tests.
6. Phải có phê duyệt đổi root/triển khai production và kế hoạch rollback riêng. Không xóa dữ liệu cũ trước khi nghiệm thu.
7. Ghi biên bản, thời điểm, release SHA, file count, tổng dung lượng, hashes, logs và số liệu RPO/RTO thực đo.

## Những việc chưa hoàn thành

- Backup khi service đang chạy, snapshot consistency giữa SQLite và filesystem, filesystem atomicity.
- Single-scheduler process lock, replicated coordination, durable outbox, artifact object storage, cross-zone backup.
- Encryption, offsite replication, signing, retention rotation và phân quyền backup.
- RPO/RTO và tần suất backup chưa được chủ sở hữu xác định, không tự đặt giá trị PASS.
- Chưa chạy diễn tập khôi phục trên staging, chưa có thử nghiệm mất điện, disk-full giữa backup/restore hoặc so sánh scientific evidence sau restore.
- Manifest chỉ chứng minh **tính nhất quán byte theo SHA-256**, không chứng minh nguồn gốc được ký số hay độ đúng khoa học của kết quả mô phỏng.
