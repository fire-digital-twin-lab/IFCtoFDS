# IFCtoFDS — R5c: Khắc phục ba CVE có bản vá Debian (09/11/2026)

**Trạng thái:** CODE REVIEW / CI PENDING. Không phải thông báo CVE đã được xử lý thành công trên release.  
**Source:** `fire-digital-twin-lab/IFCtoFDS`; baseline `main@83340f0ecfd620affe4fe84dcd6e658d4ef3f419`.  
**Intended use:** production software Workbench / Verified Mapping API; **scientific/application INCONCLUSIVE**, release **NOT_PRODUCTION_READY**.

## 1. Bằng chứng trước sửa

Artifact `image-security-evidence` tại [run #42654966363](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42654966363), trên Debian Trixie 13.7, Trivy 0.70.0: **1.202 SPDX packages, 0 CRITICAL, 51 HIGH findings** từ 14 CVE IDs. Các finding là theo binary packages, không tương đương 51 CVE độc lập.

Bốn finding thuộc ba CVE có `FixedVersion` trong report:

| CVE | Binary packages bị ảnh hưởng | Installed | FixedVersion do Trivy ghi |
|---|---|---|---|
| CVE-2026-109518 | `apt`, `libapt-pkg7.0` | `3.0.3` | `3.0.4` |
| CVE-2026-76844 | `zlib1g` | `1:1.3.dfsg+really1.3.1-1+b1` | `1:1.3.dfsg+really1.3.1-1+deb13u1` |
| CVE-2026-85091 | `zlib1g` | `1:1.3.dfsg+really1.3.1-1+b1` | `1:1.3.dfsg+really1.3.1-1+deb13u1` |

Đối chiếu: [Debian libapt-pkg7.0 trixie 3.0.4](https://packages.debian.org/trixie/libapt-pkg7.0), [Debian security tracker zlib](https://security-tracker.debian.org/tracker/source-package/zlib), [DSA-6613-1](https://security-tracker.debian.org/tracker/DSA-6613-1).

**Các HIGH còn lại trong report:** 47 findings / 11 CVE IDs, gồm `util-linux` family (36 findings), `ncurses` (4), `libsqlite3-0` (3), `libsystemd0/libudev1` (2), `libacl1` (1), `perl-base` (1). Trivy không ghi `FixedVersion` trong 47 record này. Các tên package và count là baseline; cần quét lại khi build thay đổi.

## 2. Thay đổi kỹ thuật có phạm vi hẹp

- `Dockerfile`: trên base Trixie đã pin OCI digest, chỉ cài các phiên bản **chính xác** `apt=3.0.4`, `libapt-pkg7.0=3.0.4`, `zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1`. Nếu Debian mirror/security repo không còn cung cấp bản đó, build **FAIL**; không lùi về version cũ. Giữ GPG/APT signature checks mặc định và xóa package index sau cài.
- `.github/workflows/container.yml`: đọc `dpkg-query` từ **runtime image** để chứng minh packages đang cài đúng version, bên cạnh job IFC E2E, TLS, key rotation và offline backup/restore.
- `scripts/validate-release-security-evidence.py`: hỗ trợ repeatable `--deny-cve`, fail ngay nếu scan còn chứa CVE đã vá, kể cả trong chế độ inventory `EVIDENCE_ONLY`.
- `.github/workflows/release-security.yml`: bắt buộc chặn cả ba CVE trong normal CI và manual strict preflight; scan vẫn thống kê toàn bộ HIGH/CRITICAL.
- Tests positive, negative, invalid ID, no-overwrite evidence, static enforcement.

## 3. Định nghĩa nghiệm thu / NO-GO

1. Source Quality, Conversion Correctness, Production Container, Release Image Security đều PASS trên **HEAD cuối của PR**.
2. Container CI xác nhận exact OS package versions. Trivy JSON mới không còn `CVE-2026-109518`, `CVE-2026-76844`, `CVE-2026-85091` trong kết quả HIGH/CRITICAL. So sánh CVE ID và package, không chỉ giảm tổng count.
3. Trivy `ImageID` phải đối chiếu image build; SBOM và scan artifacts có checksum và source SHA. Không sửa scan JSON/golden để qua test.
4. Không thay đổi Python dependency lock, IFC mapping/FDS semantics, scientific reference/solver. Kết luận khoa học **không được nâng**.
5. Không đánh dấu G07/production PASS: còn các HIGH khác; policy `--enforce` toàn bộ HIGH/CRITICAL vẫn phải FAIL nếu chưa giải quyết hoặc được phê duyệt qua quy trình riêng.
6. Sau CI, staging phải kiểm chứng SQLite/worker/conversion/backup/rollback với dữ liệu tương ứng và image digest, không dùng kết quả runner thay thế.

## 4. Rủi ro và rollback

- Package versions pin chính xác cải thiện kiểm soát nhưng không bảo đảm byte-level reproducibility của toàn bộ image; apt metadata/timestamp và những layer khác phải được chứng thực trong release workflow.
- Security repo/Debian mirror có thể thay đổi và làm build fail-closed. Không chuyển sang `apt-get upgrade` toàn bộ hoặc `--allow-unauthenticated` chỉ để qua CI.
- Nếu phát sinh regression, revert PR. Rollback đưa CVE đã xác định quay lại phải được operator đánh giá và phê duyệt; không triển khai rollback mù.
- Không xóa named volume, sửa backup manifest hay golden evidence.

**Các công việc kế tiếp:** cập nhật 47 HIGH còn lại theo patch availability/exploitability và bản vá Debian tiếp theo; build once → push image theo OCI registry digest sau strict security approval; required branch checks và protected environment; staging/DR/rollback drills; scientific P4c2b bên track độc lập.
