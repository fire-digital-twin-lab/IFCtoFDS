# IFCtoFDS — Kiểm định thay đổi Python base image và CVE (09/11/2026)

**Phạm vi:** chỉ thay đổi lớp OS/Python của runtime Docker image, không sửa domain logic/IFC/FDS.  
**Trạng thái:** đề xuất kiểm thử độc lập trên PR; chưa có staging nghiệm thu, chưa phê duyệt release.

## 1. Bằng chứng trước thay đổi

Trong R5a, workflow `Release image security evidence` đầu tiên đã quét image trên Debian **Bookworm 12.15** và lưu artifact [run #42652597149](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42652597149):

- SPDX SBOM: **1.220 packages**.
- Trivy: **2 CRITICAL + 40 HIGH findings** trong OS packages; 17 CVE ID không trùng lặp. Đây là **finding counts theo package**, không phải 42 lỗ hổng độc lập hoặc 42 khả năng khai thác.
- Hai CRITICAL trên `libsqlite3-0` (`CVE-2025-7458`, package 3.40.1-2+deb12u2) và `zlib1g` (`CVE-2023-45853`).
- Trivy không có `FixedVersion` trong 42 record. Điều đó không có nghĩa chắc chắn chưa có phiên bản đã sửa ở bản phân phối khác.

Theo [Debian CVE-2025-7458](https://security-tracker.debian.org/tracker/CVE-2025-7458), SQLite trên Bookworm vulnerable, Trixie đã fixed. Theo [Debian CVE-2023-45853](https://security-tracker.debian.org/tracker/CVE-2023-45853), Trixie đã fixed; tracker ghi chú thành phần MiniZip liên quan không được build trong một số gói Bookworm, vì vậy scanner severity không tự chứng minh exploitability của ứng dụng.

## 2. Thay đổi có kiểm soát

Từ:

`python:3.12.16-slim-bookworm` (tag version, không pin OCI digest)

sang:

`python:3.12.16-slim-trixie@sha256:962f801b08c870ac2a51b72bf02dae38c9a4162319e5e882ec244e198188d54e`

Digest là **OCI multi-platform index** được công bố cho tag này trên [Docker Hub](https://hub.docker.com/layers/library/python/3.12.16-slim-trixie/images/sha256-6d2b0577e6d1632f077331de8e4780535f54839d163ded7abb4b7dd37b5d37ac) ở thời điểm lập PR. Vì index đã pin, tag di chuyển về sau không tự thay đổi byte base image. Cần kiểm tra thực tế Docker build trên CI cả trên kiến trúc được triển khai.

Không thay Python minor version, UV binary digest, `uv.lock`, user UID/GID 10001, entrypoint, Volume, TLS, API contract hoặc FDS solver policy. Đây **không phải** sự kiện phê duyệt scientific claim.

## 2.1. Kết quả thực nghiệm Trivy trên base Trixie (CI)

**Run:** [Release image security evidence #42654966363](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42654966363), HEAD nhánh thử nghiệm `58d191e37ed1cabd2972634f4e8ce19119b2ebd5`. Artifact `image-security-evidence` gồm SPDX, Trivy JSON, `summary.json` và SHA-256 của các báo cáo. Dữ liệu từ chính scanner, **không phải ước tính**:

| Chỉ tiêu | Bookworm 12.15 (run #42652597149) | Trixie 13.7 (run #42654966363) |
|---|---:|---:|
| Packages SPDX SBOM | 1.220 | 1.202 |
| CRITICAL findings | 2 | **0** |
| HIGH findings | 40 | **51** |
| HIGH CVE IDs không trùng | 15 | 14 |
| Security release approval | NOT_GRANTED | **NOT_GRANTED** |

Mức CRITICAL của scanner đã giảm về 0 trên digest được pin, nhưng HIGH **tăng 11 findings**; không được gọi đây là image sạch lỗ hổng. Phần lớn HIGH liên quan nhiều binary packages cho cùng CVE ID. Ở Trixie, Trivy đánh dấu 4 HIGH findings là đã có phiên bản sửa: `CVE-2026-109518` (apt/libapt), `CVE-2026-76844` và `CVE-2026-85091` (zlib); 46 findings ở trạng thái `affected` chưa có `FixedVersion` và một finding `fix_deferred`. Các nhận định cần được đối chiếu với Debian Security Tracker và actual usage trước khi chấp thuận exception hoặc nâng image.

Hai lần quét khác thời điểm; vulnerability DB, OS package set và distribution thay đổi. So sánh không chứng minh tự động có giảm rủi ro tổng thể. `--enforce` với policy HIGH/CRITICAL vẫn sẽ FAIL. R5b chỉ chốt thay đổi base image sau khi regression đủ PASS; CVE triage/remediation là work package tiếp theo trước release.

## 3. Ma trận nghiệm thu

1. Docker build mới thành công, image vẫn chạy non-root UID/GID 10001 và read-only filesystem.
2. Production container regression: NGINX, secrets, key rotation, job IFC E2E, persistence, backup/restore named volume và all negative tests.
3. Source Quality, Conversion Linux/Windows matrix, browser, pinned FDS solver PASS. Linux FDS thực vẫn không được tự đóng gói trong image.
4. R5a trên image mới tạo SBOM/Trivy, so sánh với baseline theo cùng severity policy. Ghi rõ CVE ID, package, scanner DB timestamp; không chỉ so tổng finding counts.
5. **Không tự kết luận G07 PASS** nếu Trivy còn HIGH/CRITICAL, chưa có triage và approved exceptions. Không dùng kết quả SBOM/Trivy thay cho threat model/staging.
6. Chạy snapshot/restore compatibility trên staging: mở SQLite cũ, verify bản ghi, artifacts và rollback compatibility trước khi cutover.

## 4. Risks/rollback

- Debian 12 → 13 đổi thư viện hệ điều hành, glibc và dependency ABI; phải chạy conversion/mesh/geometry, runtime Docker và worker subprocess tests, không chỉ import smoke.
- Nếu lỗi CI, rollback PR (chưa deploy). Nếu lỗi staging sau cutover, cần backup và khả năng mở DB bằng image cũ đã kiểm tra; **không** tự rollback chỉ vì ImageID cũ chạy được.
- Rollback về Bookworm tái đưa CVE findings của baseline; yêu cầu risk acceptance riêng. Không xóa named volumes hoặc scientific evidence.

**Release verdict:** `NOT_PRODUCTION_READY`. **Scientific/application:** `INCONCLUSIVE`.
