# IFCtoFDS — Integration Acceptance Report R21

**Date / Ngày:** 2026-11-07  
**Baseline:** `main@3640d99d49017b93dd8ebf47417c0279aad82648`  
**System verdict:** `NOT_PRODUCTION_READY`  
**Evidence type:** GitHub repository / PR diff / CI check runs / static scientific governance; **NOT** staging, production, or independent CFD evidence.

## 1. Những thay đổi đã tích hợp

| PR | Merge SHA | Finding | Test/evidence | CI |
|---|---|---|---|---|
| [#61](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/61) | `a2428569` | `OPS-DOWNLOAD-01` | `test_job_artifact_download_lease.py`: purge 409, response cancel, multi-lease, retention | [main Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42330708717) / [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42330708649) SUCCESS |
| [#62](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/62) | `2404e3a2` | `CI-BROWSER-HANDSHAKE-01` | Browser stale-worker wait for verified idle, failure state dump | [main Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42291965464) / [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42291965457) SUCCESS |
| [#63](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/63) | `9faabc64` | `IO-STOPPED-DIAGNOSTIC-01` | `test_job_stopped_worker_diagnostic_io.py`: RAM/deadline x diagnostic+SQLite outage | [main Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331377851) / [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331377866) SUCCESS |
| [#64](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/64) | `3640d99d` | `IO-DIAGNOSTIC-PARTIAL-01` | `test_job_atomic_terminal_diagnostic.py`: fsync, link, concurrent worker | PR [Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331440045), [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331440065) SUCCESS; main runs PENDING tại checkpoint |

## 2. Đánh giá về fault injection

Các thay đổi đặt ra và kiểm tra bất biến:

1. Không xóa artifact đang trả response hoặc đang trong thời gian xác minh evidence theo download lease; purge báo 409.
2. Không mất lý do `TIMED_OUT` hoặc `RESOURCE_EXHAUSTED` đã xác định sau khi kill worker nhưng diagnostic/SQLite gặp lỗi I/O liên tiếp.
3. Không công bố file `diagnostics.json` chưa hoàn chỉnh ở đường scheduler internal; không ghi đè diagnostic xuất bản bởi worker.
4. Không công bố trạng thái terminal trước khi SQLite commit.

**Giới hạn:** Bằng chứng test/công cụ CI không thay thế physical power loss, directory fsync, worker external writes, NFS incompatibility, Byzantine files, multi-host concurrency, degraded storage, scheduled retention soak, hay staged restore drill.

## 3. Scientific acceptance — fail closed

- `reference-cases/basement-b1-b2/approval.json`: `status=DRAFT`, `reviewer=null`, `evidence=[]`. Không có independent reviewer sign-off.
- Solver chạy thành công qua GitHub CI chỉ chứng minh hợp đồng/fixture phù hợp; không chứng minh độ đúng CFD cho thiết kế cháy công trình thực.
- `SIMULATION_VERIFIED` **không được cấp**; những báo cáo hình học/ánh xạ phải tách bạch khỏi nghiệm thu vật lý.
- Những finding còn mở gồm energy-budget scope C-3b, HF NOT_MODELED, door control, mesh sensitivity, opening grid alignment và independent HVAC/solver parity.

## 4. Gates và exit criteria

Trạng thái đầy đủ của 16 gate nằm tại [PRODUCTION_ACCEPTANCE_MASTER_TRACKER.md](PRODUCTION_ACCEPTANCE_MASTER_TRACKER.md). Tổng thể **NOT_PRODUCTION_READY**. Không có Release hoặc staging/production deployment evidence. G05 `IN_PROGRESS`; G06 `INCONCLUSIVE`; G09/G10 `INCONCLUSIVE`; G11/G12/G13/G15 `NOT_RUN`.

## 5. English executive summary

PRs #61–#64 are merged and protected by mandatory multi-OS CI. They harden download-vs-purge races, stale-worker browser tests, stopped-worker terminal error preservation, and atomic terminal diagnostic publication. Passing CI verifies scoped regressions **only**. Independent fire-science validation, real IFC reference approval, staging, backup/restore, rollback, and production smoke testing remain outstanding. **No scientific verification or production approval is implied.**
