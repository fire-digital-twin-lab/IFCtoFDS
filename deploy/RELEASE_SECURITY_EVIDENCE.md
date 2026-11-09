# IFCtoFDS — Hồ sơ bảo mật image và điều kiện release (R5a)

**Tình trạng:** PRE-RELEASE EVIDENCE ONLY, **không phải** release approval.  
**Intended use:** Workbench + IFC conversion/Verified Mapping API; không cấp `SIMULATION_VERIFIED`.

## 1. Workflow trên GitHub

`.github/workflows/release-security.yml` tạo bộ bằng chứng từ **cùng một image** `ifctofds:security` trong runner:

1. Build Dockerfile từ repository SHA của event (có `--pull`; base tag hiện chưa pin toàn bộ bằng digest).
2. Sinh SPDX-2.3 JSON SBOM bằng Syft/Anchore action đã pin commit.
3. Quét HIGH/CRITICAL bằng Trivy, lưu vulnerability JSON thay vì chỉ log, **không lọc unfixed**.
4. Kiểm tra hai định dạng, ImageID nếu Trivy cung cấp, nguồn SHA, checksum SHA-256 của hai artifacts và ghi `summary.json`.
5. Upload `image-security-evidence` để kiểm tra nguồn gốc và phân loại CVE.

Các action SBOM/Trivy/checkout/upload được pin **full commit SHA** thay vì mutable major tag. Tuy nhiên Trivy tải vulnerability DB theo thời điểm quét, nên kết quả quét có thể khác khi chạy lại cùng image; báo cáo phải kèm thời điểm workflow và nguồn dữ liệu CVE.

Định nghĩa `summary.json`:

- `source_sha` và `local_image_id` là bằng chứng của **build trong runner**, không phải immutable registry digest.
- `sbom_sha256`, `scan_sha256` chỉ bảo vệ byte của artifacts trong phiên nghiệm thu; không phải ký số nguồn cung ứng.
- `scanner_image_id_verified` phải được đọc khi kết quả scan cung cấp ImageID; nếu không có, report nêu `false` và phát hành phải bổ sung xác minh.
- `security_policy=EVIDENCE_ONLY`, `security_gate=NOT_ENFORCED`, `release_approval=NOT_GRANTED`, `registry_digest=null`; không được diễn giải thành release đã sạch CVE hay được ký duyệt.

## 2. Hai chế độ và ngưỡng chặn

**PR/main:** workflow chạy `EVIDENCE_ONLY` để đánh giá baseline vulnerabilities mà không tự bỏ qua lỗi. Nếu SBOM không hợp lệ, thiếu package, scan lỗi hoặc provenance mâu thuẫn, CI **FAIL**. Tìm thấy HIGH/CRITICAL được thống kê nhưng **chưa tự chặn**: giai đoạn này không đủ để cấp release.

**Manual enforcement:** chọn workflow **Release image security evidence → Run workflow → enforce=true**. Script `scripts/validate-release-security-evidence.py --enforce` chặn khi có ít nhất một HIGH hoặc CRITICAL từ scanner; không có cơ chế waiver tự động. Nếu có finding cần đánh giá, phải sửa dependency/image hoặc xử lý exception bằng quy trình review độc lập với expiry/owner/evidence, không tự giảm threshold.

Không cho production deploy khi policy enforce chưa đạt, artifact thiếu, hoặc scanner không xác nhận nguồn build. Thêm vulnerability snapshot theo ngày, SBOM package index và reviewer để hỗ trợ đánh giá rủi ro thực.

## 3. Các gate chưa hoàn thành sau R5a

- **R5b:** build once, publish image đã qua scan vào GHCR bằng commit SHA và promotion **bằng OCI registry digest**; không rebuild ở staging hoặc production.
- Ký/attest build provenance theo GitHub artifact attestations và xác thực offline/online ở đích triển khai.
- Pin/checksum Python+NGINX base images (hiện có version tag) và kiểm soát lịch cập nhật pin.
- Chốt ngưỡng HIGH/CRITICAL có policy được duyệt, không dùng chế độ EVIDENCE_ONLY làm required security release gate.
- GitHub admin cấu hình `main` branch protection/ruleset: giữ tất cả required contexts hiện có, bổ sung `container`, `python-quality` và `image-security` sau khi quyết định policy. Chỉ sửa workflow YAML **không** tự áp branch protection. Quyền connector hiện không cấp endpoint thay đổi protection.
- Protected environment release approval, registry permission, GHCR policy, rollback pinned digest và staging/DR/monitoring drills chưa nghiệm thu.

## 4. Điều kiện chấp nhận PR R5a

- Python test kiểm tra đúng SPDX/CVE schema, hash, image mismatch, blocked HIGH/CRITICAL ở chế độ `--enforce` và fail closed khi thiếu artifact.
- Workflow SBOM/Trivy tạo artifacts tải được trên GitHub; probe chính phải xác thực `summary.json` của cùng image.
- Source Quality, Conversion, Container vẫn PASS; workflow image-security cũng PASS trong phạm vi **inventory**.
- Không thay đổi IFC, FDS, solver, scientific claim, golden reference hoặc dữ liệu công trình. G07/G11–G15 và scientific application vẫn **INCONCLUSIVE/NOT_READY** cho đến khi có bằng chứng độc lập.

## 5. Rollback

Revert workflow/script/test/tài liệu R5a nếu có regression. Không thay đổi image deployment, không tạo GHCR package, không yêu cầu secret mới, không xóa artifacts hoặc dữ liệu nghiệp vụ. Kết luận release giữ `NOT_PRODUCTION_READY`.
