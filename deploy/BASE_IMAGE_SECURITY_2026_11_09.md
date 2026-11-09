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
