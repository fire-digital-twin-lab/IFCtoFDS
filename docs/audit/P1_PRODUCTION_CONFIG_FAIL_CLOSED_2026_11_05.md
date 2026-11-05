# P1 — Fail-closed cho cấu hình triển khai staging và production

Ngày rà soát: 05/11/2026.

## Nguy cơ

Trước thay đổi này, `server.security_guard` chỉ xác thực `/api/*` nếu
`IFCFDS_API_KEY` có giá trị. Một môi trường internet cấu hình thiếu khóa
có thể vô tình phục vụ API không xác thực.

## Khắc phục

Hàm `validate_deployment_config()` được thực thi trước khi khởi tạo
`JobManager` và FastAPI:

- Mặc định `IFCFDS_ENV=local` để không thay đổi hành vi desktop hiện có.
- `IFCFDS_ENV=staging` hoặc `production` bắt buộc khóa API tối thiểu 32
  ký tự và `IFCFDS_ALLOWED_HOSTS` tường minh, không có wildcard.
- Giá trị môi trường không được hỗ trợ gây lỗi khi khởi động.
- Không ghi nội dung khóa vào exception/log.
- Test: `tests/test_production_deployment_config.py` gồm trường hợp âm tính,
  cấu hình hợp lệ và kiểm tra import server thực tế với khóa trống.

Ví dụ vận hành (chỉ là tên biến, **không lưu khóa vào repository**):

```sh
export IFCFDS_ENV=production
export IFCFDS_ALLOWED_HOSTS=ifctofds.example.org
export IFCFDS_API_KEY="$(secret-manager-get ifctofds/api-key)"
```

Lệnh `secret-manager-get` là placeholder biểu diễn trình quản lý bí mật,
không phải công cụ sẵn có. Cần truyền giá trị thực qua secret manager của
hạ tầng được phép.

## Giới hạn — Không đóng Security gate

- Đây chỉ là chặn cấu hình thiếu khóa, **không thay thế** authorization
  theo user/job/artifact, token lifecycle, session security hoặc xác thực
  phù hợp browser; một khóa chung không đủ cho mô hình multi-tenant.
- TLS/HSTS/CSP/rate limiting/reverse proxy/host validation thực tế cần
  E2E và runtime evidence riêng.
- Chưa xác nhận triển khai staging hoặc production. Chưa có threat model
  đầy đủ hoặc pentest, không cấp `SECURITY=PASS`.
- Đối với hệ thống mở cho người dùng, nên chuyển xác thực sang session/BFF
  hoặc identity provider phù hợp, không nhúng API key vào trình duyệt.

## Tiêu chí nghiệm thu PR

1. Python unit và subprocess startup negative tests PASS.
2. GitHub CI đúng HEAD PASS và không nới branch protection.
3. `local` không đổi hành vi; staging/production thiếu khóa không khởi động.
4. Các chức năng IFC/FDS và verdict khoa học không thay đổi.
