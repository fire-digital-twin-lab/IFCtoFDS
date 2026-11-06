# IFCtoFDS — Integration Acceptance Report

**Ngày ghi nhận:** 07/11/2026. **Baseline:** `main@3f90132abae94a2efcd7ba4a73b12dbd786948c4`. **Verdict toàn hệ thống:** `NOT_PRODUCTION_READY`.

## 1. Truy vết thay đổi

| PR | Finding | Commit merge | Test bổ sung/đối chiếu | Kết quả CI thực tế |
|---|---|---|---|---|
| [#57](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/57) | IO-CLEANUP-01 | `5d3b1f4` | `tests/test_job_cleanup_nonfatal.py` | [PR Conversion #42064270096](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42064270096) SUCCESS; [PR Quality #42064270221](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42064270221) SUCCESS; main #42262907385/#42262907437 SUCCESS |
| [#58](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/58) | IO-CANCEL-DIAGNOSTIC-01 | `ff7f329` | `tests/test_job_cancel_diagnostic_io.py` | [PR Conversion #42263377779](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42263377779) SUCCESS; [PR Quality #42263377785](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42263377785) SUCCESS; main #42264208457/#42264208452 SUCCESS |
| [#59](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/59) | IO-SCHEDULER-DIAGNOSTIC-01 | `3f90132` | `tests/test_job_scheduler_diagnostic_io.py` | [PR Conversion #42264341863](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42264341863) SUCCESS; [PR Quality #42264341872](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42264341872) SUCCESS; merge main CI pending ở checkpoint |

## 2. Các điều kiện đã và chưa đạt

- Trước mỗi merge, branch protection xác nhận các required contexts tương ứng đủ 9/9 SUCCESS. Không bypass.
- Không có PR mở tại thời điểm truy vấn sau #59.
- Các test chỉ chứng minh contract và đường lỗi được tiêm; không thay thế multi-host, OS crash, disk failure hoặc so sánh khoa học độc lập.
- GitHub Actions dùng FDS solver theo CI fixture; PASS không cấp `SIMULATION_VERIFIED`.
- Repo có `AGPL-3.0-or-later`; bắt buộc rà soát nghĩa vụ cấp phép khi vận hành phiên bản đã sửa đổi qua mạng.
- Container không thể clone GitHub do DNS không truy cập; **local tests: NOT_RUN trong phiên**. Không dùng kết quả CI giả làm local test.

## 3. Kết luận kỹ thuật

`IO-CLEANUP-01`, `IO-CANCEL-DIAGNOSTIC-01` và `IO-SCHEDULER-DIAGNOSTIC-01`: đã merge, bằng chứng PR CI PASS cho phạm vi test. Không đóng toàn bộ `IO-PERSISTENCE` hay nâng G05/G06 lên PASS. Chờ CI main trên `3f90132` và tiếp tục fault injection.

G09/G10 `INCONCLUSIVE`; G11/G12/G13/G15 `NOT_RUN`. Không có staging/production, release candidate, completed backup/restore drill hay chuyên gia PCCC sign-off. Tổng thể `NOT_PRODUCTION_READY`.
