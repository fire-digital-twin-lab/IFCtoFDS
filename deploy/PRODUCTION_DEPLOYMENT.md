# IFCtoFDS — Production deployment contract

**Phạm vi hiện tại:** triển khai Workbench + Verified Mapping/API theo mô hình single-instance. Tài liệu này không cấp `SIMULATION_VERIFIED`, không thay thế CFD V&V và không biến solver smoke test thành bằng chứng an toàn cháy.

## Kiến trúc runtime

```text
Internet
  |
  v
NGINX 1.30.6 :443 (TLS, HSTS, rate limit)
  |
  v
IFCtoFDS app :8000 (không publish trực tiếp)
  |
  +-- SQLite + artifacts: named volume /var/lib/ifctofds/jobs
  +-- single scheduler owner enforced by job-root lock
```

Container ứng dụng chạy UID/GID 10001, root filesystem read-only, chỉ job volume và `/tmp` được ghi. Python dependencies được cài từ `uv.lock`; binary uv được pin bằng OCI SHA-256 để giảm drift của build. `IFCFDS_ENV=production` buộc API key và Host allowlist; thiếu cấu hình thì app phải dừng thay vì mở anonymous API.

## Điều kiện trước khi triển khai

1. Docker Engine + Compose plugin đã được cập nhật và quản trị bằng quy trình của hạ tầng.
2. DNS của `IFCFDS_PUBLIC_HOST` trỏ tới máy chủ.
3. Có chứng chỉ TLS hợp lệ trong thư mục chỉ đọc:
   - `fullchain.pem`: owner `root:root`, mode `0644`;
   - `privkey.pem`: owner `root:root`, mode `0600`.
   Proxy đã drop `DAC_OVERRIDE`, vì vậy operator phải cấu hình ownership/mode đúng thay vì cấp thêm capability chỉ để đọc private key.
4. Tạo API key ngẫu nhiên tối thiểu 32 ký tự trong file chỉ operator đọc được; không commit vào Git và không truyền secret qua Compose environment.
5. Có dung lượng persistent volume đủ cho IFC, SQLite và artifacts.
6. Chọn release SHA đã qua CI. Không deploy trực tiếp nhánh feature.
7. Với profile yêu cầu FDS solver evidence: image hiện tại **không đóng gói FDS Linux**. Chỉ bật solver khi operator đã cung cấp executable FDS 6.11.1 tương thích và xác minh version/checksum theo contract dự án. Nếu chưa có, giữ simulation verification fail-closed.

## Biến môi trường

Ví dụ shell; thay giá trị thật bằng secret manager hoặc cơ chế triển khai được phê duyệt:

```bash
export IFCFDS_PUBLIC_HOST=ifctofds.example.org
export IFCFDS_API_KEY_FILE=/srv/ifctofds/secrets/api-key
export IFCFDS_TLS_CERT_DIR=/srv/ifctofds/tls
export IFCFDS_IMAGE_TAG=release-sha
```

Compose mount `IFCFDS_API_KEY_FILE` thành `/run/secrets/api_key`; CLI đọc secret file trước khi import server. Không lưu secret trực tiếp trong `.env`, command line, image layer hoặc repository.

## Kiểm tra cấu hình trước khi chạy

```bash
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml build --pull
```

## Khởi động

```bash
docker compose -f compose.production.yml up -d
docker compose -f compose.production.yml ps
```

App không publish cổng 8000 ra host. Host allowlist của app gồm public hostname cộng `127.0.0.1/localhost` để Docker healthcheck nội bộ hoạt động; NGINX luôn chuyển Host của lưu lượng ngoài thành public hostname. Chỉ reverse proxy mở 80/443; cổng 80 chuyển hướng vĩnh viễn sang HTTPS.

## Smoke nghiệm thu

```bash
python scripts/production-smoke.py \
  --base-url "https://$IFCFDS_PUBLIC_HOST" \
  --api-key-file "$IFCFDS_API_KEY_FILE"
```

Smoke đọc API key từ file, không nhận secret qua command line; không tự theo redirect, đặc biệt redirect rời HTTPS. Endpoint Workbench trả HTML, không phải JSON.

Smoke chỉ kiểm tra:
- TLS endpoint có thể truy cập bằng client verification mặc định;
- `/api/health` trả service healthy;
- `/api/scheduler-health` trả scheduler healthy khi có API key;
- Workbench root trả HTTP 200.

Smoke PASS không phải scientific acceptance.

## Backup / restore

Job store nằm trên named volume. Trước backup phải dừng API/worker và dùng quy trình trong `docs/operations/BACKUP_RESTORE_RUNBOOK.md`. Chưa được gọi G12 PASS cho đến khi diễn tập restore trên staging với checksum, release SHA, RPO/RTO thực đo và biên bản.

## Rollback

1. Không xóa volume job hiện tại.
2. Ghi release SHA đang chạy và backup offline trước thay đổi có rủi ro dữ liệu.
3. Chỉ rollback application image khi schema/job-store contract tương thích.
4. Chạy smoke trên phiên bản rollback trước khi mở lại lưu lượng.
5. Nếu cần restore dữ liệu, restore vào root mới trước; không overwrite root đang phục vụ.

## Giới hạn production còn mở

- Shared API key không phải multi-tenant identity/authorization.
- Chưa có staging runtime evidence, production smoke/soak, DR drill và rollback rehearsal.
- Chưa có containerized Linux FDS 6.11.1 evidence chain.
- Chưa có application-relevant approved B1/B2 reference; P4c2b vẫn bị readiness gate chặn.
- Các claim khoa học trong `docs/science/SCIENTIFIC_CLAIMS.md` vẫn fail-closed theo evidence ledger.

Vì vậy deployment stack này là **production deployment mechanism**, không phải release approval. `NOT_PRODUCTION_READY` chỉ được gỡ khi các gate còn thiếu có evidence trên release SHA thực tế.
