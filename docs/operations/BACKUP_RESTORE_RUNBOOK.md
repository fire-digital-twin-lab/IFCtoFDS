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

## Backup/restore đúng Compose named volume (Linux Docker Engine)

**Không dùng** đường dẫn host giả định `/srv/ifctofds/jobs`. Compose hiện gắn named volume mặc định `ifctofds_jobs` vào `/var/lib/ifctofds/jobs` **bên trong container**. Tên volume có thể chỉ định bằng `IFCFDS_JOB_VOLUME_NAME` sau khi có phê duyệt đổi root; không đặt biến này trỏ tới volume production khác khi đang thử nghiệm.

Chỉ chạy trong bảo trì có kiểm soát; không thực thi lệnh `down --volumes` hoặc `docker volume rm` với volume thực. Công cụ `scripts/production-volume-maintenance.sh` kiểm tra nhãn project/volume, ngăn backup nếu còn container đang dùng volume, và không pull image bất ngờ.

Chuẩn bị thư mục host chỉ UID 10001 đọc/ghi (ví dụ mới, chưa có dữ liệu nhạy cảm); dùng nguồn ảnh build đã nghiệm thu:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /srv/ifctofds/backups
export IFCFDS_JOB_VOLUME_NAME=ifctofds_jobs
export IFCFDS_RELEASE_IMAGE=ifctofds:release-sha
docker image inspect "$IFCFDS_RELEASE_IMAGE" >/dev/null
```

Trước khi backup, dừng **sạch** API/worker/proxy qua quy trình bảo trì đã duyệt. `docker compose stop` không thay thế việc xác minh job đã hoàn thành; công cụ backup còn từ chối SQLite có job `QUEUED`/`RUNNING`. Chỉ sau khi kiểm tra trạng thái và chấp thuận downtime:

```bash
docker compose -f compose.production.yml stop proxy app
bash scripts/production-volume-maintenance.sh backup \
  "$IFCFDS_RELEASE_IMAGE" /srv/ifctofds/backups backup_20261109_01
```

Đầu ra hợp lệ phải có `manifest.json`, `jobs.sqlite3`, các artifact và `status=OFFLINE_SNAPSHOT_ONLY`. Nếu backup thiếu `manifest.json`, coi là **INCOMPLETE** và không dùng phục hồi. Backup phải được sao chép ra vùng lưu trữ ngoài host, mã hóa và phân quyền theo chính sách operator đã ký duyệt; công cụ không tự làm những bước đó.

## Verify và restore vào named volume mới, cô lập

Phục hồi phải dùng **volume mới chưa tồn tại**, có tiền tố riêng, không được chỉ định `ifctofds_jobs` làm đích:

```bash
bash scripts/production-volume-maintenance.sh restore \
  "$IFCFDS_RELEASE_IMAGE" /srv/ifctofds/backups backup_20261109_01 \
  ifctofds_jobs_restore_20261109_01
```

Script tạo volume mới, mount vào đúng `/var/lib/ifctofds/jobs`, chạy restore với `--allow-empty-existing` (chỉ cho phép mount root **đang rỗng**), kiểm tra đầy đủ SHA-256/SQLite integrity và marker `.restore-verified.json` được ghi sau cùng. Restore từ manifest v1, hỏng hash, symlink/traversal hoặc dữ liệu active bị từ chối; giữ nguyên source và không ghi đè volume đã tồn tại.

Nếu restore dừng giữa chừng, volume mới có thể còn dữ liệu **INCOMPLETE** và không có marker; **không** gắn volume đó vào app. Không tự xóa volume lỗi trước khi lưu evidence điều tra. Marker/checksum chứng minh tính toàn vẹn theo contract, không phải chứng cứ số đã ký hoặc CFD validation.

Sau restore, kiểm tra lại metadata `jobs.directory` trỏ về `/var/lib/ifctofds/jobs/job-*`, so sánh job count, artifact SHA-256 và manifest. Chỉ nghiệm thu G12 sau khi khởi chạy trong staging cô lập, test đọc/download được evidence, drill failure/restart và ghi RPO/RTO.

### Chuyển volume trên staging (sau phê duyệt riêng)

Compose chấp nhận `IFCFDS_JOB_VOLUME_NAME` để chọn tên volume; môi trường đang hoạt động **không** tự đổi giá trị. Không chuyển tên volume production chỉ dựa vào PASS của CI. Trên staging cô lập, xác minh volume mới trước, sau đó cấu hình lại Compose bằng tên volume phục hồi có chủ đích và khởi động có kiểm soát. Giữ volume gốc không bị xóa để rollback. Không dùng `docker compose down --volumes` trong runbook staging/production.

Đích mới trong Python API mặc định vẫn phải **chưa tồn tại**; `--allow-empty-existing` là cờ opt-in hẹp để khôi phục trực tiếp vào root của Docker named volume mới, và vẫn từ chối mọi đích có tệp, thư mục hoặc symlink.

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
