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
4. Tạo API key ngẫu nhiên tối thiểu 32 ký tự trong file-backed Compose secret đúng policy Linux host: regular file `root:10001`, mode `0640`, thư mục cha không cho group/others ghi. Không dùng `0600 root:root` vì ứng dụng chạy UID/GID `10001` sẽ không đọc được; không dùng `0644` vì mọi user trong container có thể đọc. Không commit secret hoặc đưa nội dung khóa lên argv/Compose environment.
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

Compose mount `IFCFDS_API_KEY_FILE` thành `/run/secrets/api_key`; CLI đọc secret file trước khi import server. Docker Compose secret có nguồn từ file là **bind mount**; khai báo `uid/gid/mode` tại Compose **không tự remap** owner/mode của host trên cơ chế này. Runtime hiện chỉ được nghiệm thu với Linux Docker Engine rootful không cấu hình remap UID/GID; nếu dùng rootless/userns phải đánh giá lại UID mapping và thử quyền đọc trong container thực tế.

### Tạo và kiểm tra API key trên Linux host

Operator cần `sudo` và quyền quản trị Docker. Ví dụ sử dụng thư mục do root kiểm soát:

```bash
sudo install -d -o root -g root -m 0755 /srv/ifctofds/secrets
openssl rand -hex 32 | sudo tee /srv/ifctofds/secrets/api-key >/dev/null
sudo chown root:10001 /srv/ifctofds/secrets/api-key
sudo chmod 0640 /srv/ifctofds/secrets/api-key
sudo python scripts/production-secret-preflight.py \
  --file /srv/ifctofds/secrets/api-key
```

Preflight chỉ kiểm tra metadata owner/group/mode và đường dẫn; **không đọc hoặc in nội dung khóa**. Ứng dụng phải kiểm tra chính nội dung và độ dài khi khởi động. Phải chứng minh Docker secret được UID/GID `10001` đọc và user khác bị từ chối; CI có positive/negative mount tests, còn staging phải chạy lại với host thực. Một host có user/group khác dùng GID `10001` cần đánh giá rủi ro chia sẻ group trước khi dùng policy này.

Khi `--api-key-file` đã được chỉ định, file thiếu, không đọc được hoặc rỗng phải làm startup thất bại. CLI không được âm thầm fallback sang `IFCFDS_API_KEY` từ môi trường. Không đưa key lên command line, debug logs, `.env` hoặc image layer.

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
sudo python scripts/production-smoke.py \
  --base-url "https://$IFCFDS_PUBLIC_HOST" \
  --api-key-file "$IFCFDS_API_KEY_FILE"
```

Smoke đọc API key từ file, không nhận secret qua command line; không tự theo redirect, đặc biệt redirect rời HTTPS. Endpoint Workbench trả HTML, không phải JSON. Ví dụ dùng `sudo` vì file host `root:10001/0640` không cho user vận hành thông thường đọc nội dung; hạn chế lệnh `sudo` vào nguồn đã kiểm soát, không dùng `chmod 0644` để làm smoke chạy được.

### Xoay vòng API key

1. Chọn cửa sổ bảo trì hoặc phương án chuyển đổi được phê duyệt, vì hệ thống dùng **một shared key** và không có hỗ trợ zero-downtime key overlap.
2. Sinh key mới bằng nguồn ngẫu nhiên an toàn, ghi đè file host với owner `root:10001` mode `0640`, chạy `production-secret-preflight.py`. Không ghi key ra terminal hoặc logs.
3. Tái tạo ứng dụng để đọc key mới; thay file trên host không tự đổi key đã nạp trong process:
   ```bash
   docker compose -f compose.production.yml up -d --force-recreate --no-build
   ```
4. Chạy smoke với key mới, xác nhận key cũ nhận HTTP `401`. Thu hồi bản sao key cũ đã được cấp, lưu biên bản rotation và thời gian gián đoạn. Nếu startup lỗi, không mở anonymous API hoặc nới file permissions; rollback có kiểm soát theo runbook.


Smoke chỉ kiểm tra:
- TLS endpoint có thể truy cập bằng client verification mặc định;
- `/api/health` trả service healthy;
- `/api/scheduler-health` trả scheduler healthy khi có API key;
- Workbench root trả HTTP 200.

Smoke PASS không phải scientific acceptance.

## Nghiệm thu conversion E2E qua HTTPS (phạm vi CI)

Workflow `Production container contract` chạy `scripts/production-conversion-e2e.py` trên đúng Compose image + NGINX TLS. Phép thử gửi IFC nhỏ thật (`tests/baseline/fixtures/tiny.ifc`) qua `POST /api/jobs` với API key; kiểm tra HTTP 401 khi thiếu khóa và HTTP 403 với Origin sai; chờ terminal state `COMPLETED`, đối chiếu `MAPPING_VERIFIED` và `simulation_status=INCONCLUSIVE`, xác minh `manifest`, `fds`, `geometry` theo SHA-256.

CI sau đó tái tạo `app` và `proxy` **không xóa jobs volume**, truy vấn lại job và so sánh hash artifact trước/sau restart. `--evidence` là file test tạm chứa ID job, kết luận mapping và SHA-256; không được lưu API key vào evidence.

Chỉ ghi nhận là software E2E contract của bản build tại CI runner. Không dùng kết quả này để phát hành `SIMULATION_VERIFIED`, không thay thế load/soak/staging smoke, không chứng minh durability dưới power loss. Nếu chạy trên staging, dùng IFC test được duyệt và bản key không được tiết lộ; không chạy fixture/negative tests trên production dữ liệu thực khi chưa phê duyệt.

## Backup / restore

Job store nằm trên Docker named volume `ifctofds_jobs` (mặc định cho project `ifctofds`) gắn vào **container path** `/var/lib/ifctofds/jobs`; không đồng nghĩa với đường dẫn host `/srv/ifctofds/jobs`. Tên volume có thể thay đổi một cách tường minh bằng `IFCFDS_JOB_VOLUME_NAME` chỉ sau khi xác minh volume mới và có phê duyệt cutover.

Trước backup phải dừng API/worker và dùng `scripts/production-volume-maintenance.sh` theo `docs/operations/BACKUP_RESTORE_RUNBOOK.md`. Công cụ từ chối backup đang có container sử dụng volume và job đang chạy; restore chỉ dùng volume **mới chưa tồn tại**, marker `.restore-verified.json` được ghi sau cùng. Tuyệt đối không dùng `docker compose down --volumes` trên môi trường staging/production thực; mọi thao tác chuyển volume/rollback cần biên bản và approval.

Kiểm thử backup/restore Docker trong CI chỉ xác minh hợp đồng phần mềm; **G12 = NOT_RUN** đến khi diễn tập thực trên staging, so sánh checksum, release SHA, RPO/RTO thực đo và phê duyệt.

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
