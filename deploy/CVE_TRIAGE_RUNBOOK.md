# IFCtoFDS — Quy trình triage CVE cho release artifact

**Trạng thái:** Proposed / review evidence. **Không** đồng nghĩa phê duyệt chấp nhận rủi ro.  
**Intended use:** Workbench + IFC conversion API; scientific/application tiếp tục **INCONCLUSIVE**.

## 1. Nguồn dữ liệu và lý do

Sau R5c, [báo cáo Trivy trên PR #90](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/90) dự kiến còn **47 HIGH findings thuộc 11 CVE IDs**, mặc dù bản sửa apt/zlib đã loại ba CVE có `FixedVersion` khỏi scan. Giá trị phải được cập nhật theo từng image/Trivy DB ở mọi build; không hardcode làm ngưỡng chấp nhận.

Trivy `Vulnerabilities` có thể chứa nhiều binary packages cho một CVE, nên **finding count ≠ unique CVE count ≠ số lỗi khai thác được**. Một CVE không có `FixedVersion` trong report **không** tự động là không thể sửa, không có rủi ro hoặc đủ điều kiện exception.

## 2. Công cụ tạo sổ triage

`scripts/triage-release-vulnerabilities.py` đọc **đúng** `vulnerabilities.json` do Trivy trong workflow tạo, đối chiếu `ArtifactName`, `SchemaVersion`, `ImageID`, source SHA và tính SHA-256 trên bytes nguồn.

Công cụ xuất `release-evidence/cve-triage.json` gồm:

- `finding_counts` HIGH/CRITICAL, `unique_cve_count`, `patch_candidate_cve_count`;
- mỗi CVE gắn tất cả package phiên bản ảnh hưởng, `FixedVersion` do scanner ghi, target, status và severity;
- `patch_availability` là suy luận có/không có `FixedVersion` **trong bản scan**, không phải kết luận tồn tại patch trên Debian;
- `triage_status=UNREVIEWED`, `human_review=REQUIRED`, `security_release_verdict=NO_GO`, `release_approval=NOT_GRANTED`, `scientific_verdict=NOT_EVALUATED`.

Không tự chuyển `UNREVIEWED` sang APPROVED. JSON này là **đầu vào để reviewer đánh giá**; không phải quyết định risk acceptance đã ký. Không được chỉnh tệp scanner/triage trong CI để loại CVE hoặc làm xanh release.

## 3. Quy trình phê duyệt ngoài công cụ

Với từng CVE reviewer cần: đối chiếu Debian Security Tracker và upstream advisory tại ngày review, phiên bản chạy trong **image digest cụ thể**, đường exploit khả dĩ trong container, exposure (untrusted IFC, upload, parsing, subprocess, network, file IO), điều kiện tiên quyết, mức ảnh hưởng, trạng thái patch và phương án giảm thiểu.

Nếu đề xuất exception: owner/reviewer độc lập, mã CVE + package/installed image digest, justification, scope, evidence links, mitigation, expiry date, kế hoạch đóng, phê duyệt rõ ràng. Không có exception vô hạn hoặc waiver tự động; cần Security/SRE phê duyệt theo chính sách dự án trước khi cấu hình gate.

Để production release phải có strict high/critical gate PASS hoặc policy exception được xác minh, image immutable digest, CI/attestation, staging, DR, rollback, alert drill và release sign-off. **Chưa có** những bằng chứng này; production vẫn **NOT_PRODUCTION_READY**.

## 4. Negative tests và tính tái lập

- Thiếu `Results`, artifact khác image, `ImageID` sai, `PkgName` hoặc `InstalledVersion` rỗng, severity ngoài HIGH/CRITICAL → FAIL.
- Source SHA sai, CVE identifier ngoài contract, output tồn tại → FAIL; không ghi đè chứng cứ.
- Sắp xếp deterministic CVE/packages; SHA-256 của raw Trivy JSON cho phép đối chiếu nguồn.
- Scanner JSON hợp lệ có 0 finding **vẫn** `release_approval=NOT_GRANTED`: không được dùng việc không phát hiện CVE làm bảo chứng toàn hệ thống.
- Chạy qua GitHub Actions trên image build cùng SHA; đính kèm `cve-triage.json` vào artifact `image-security-evidence`.

## 5. Rollback

Revert script/test/workflow/docs nếu workflow kiểm định chứng cứ có regression. Không cập nhật container image hoặc SQLite data từ công cụ này. Không giảm severity filter, không xóa findings để giữ CI xanh.
