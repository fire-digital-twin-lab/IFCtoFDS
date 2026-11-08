# Monitoring runbook — IFCtoFDS single-instance

**Trạng thái:** operational monitoring contract. Đây không phải scientific evidence và chưa đủ để nâng G14 thành PASS nếu chưa có alert/runtime drill trên staging.

## Endpoints

- `/api/health`: liveness công khai, chỉ xác nhận HTTP process đang phục vụ.
- `/api/scheduler-health`: có API key; trả 503 nếu scheduler không thể dispatch pending jobs.
- `/api/operational-status`: có API key; trả telemetry path-free và 503 khi runtime bị degraded.

`/api/operational-status` gồm:

- `scheduler_healthy`, `accepting_jobs`, `service_closed`, `uptime_s`;
- job counts theo state, pending/terminal và queue capacity;
- process RSS bytes;
- disk total/free bytes và kết quả storage probe.

Endpoint không trả job directory, IFC filename, API key, source path hoặc scientific verdict.

## Probe

Ví dụ:

```bash
curl --fail --silent \
  -H "X-API-Key: $IFCFDS_API_KEY" \
  "https://$IFCFDS_PUBLIC_HOST/api/operational-status"
```

External monitor phải coi HTTP 503 là degraded. Không tự đặt ngưỡng disk/RSS khoa học trong code; alert thresholds là chính sách vận hành và phải được chọn theo capacity staging/production thực tế.

## Alert tối thiểu cần cấu hình ở staging

1. `/api/health` không reachable.
2. `/api/operational-status` trả 503 hoặc `scheduler_healthy=false`.
3. `accepting_jobs=false` kéo dài ngoài khoảng tải được chủ sở hữu chấp thuận.
4. Disk free/RSS vượt ngưỡng capacity đã đo trên staging.
5. NGINX 5xx tăng bất thường.

## Điều kiện để nâng G14

Cần bằng chứng runtime trên release SHA: monitor thu được endpoint qua TLS, alert thực sự kích hoạt khi kill supervisor/app hoặc gây resource pressure có kiểm soát, log sự kiện được giữ lại, và runbook recovery được thực hiện. CI unit/container smoke chỉ xác minh contract phần mềm; không chứng minh alerting production hoạt động.
