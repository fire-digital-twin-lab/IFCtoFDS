# P1 — Required checks bị hủy chéo giữa push và pull_request

**Bằng chứng thực tế ngày 05/11/2026:**
- PR #39 HEAD `ba1c4e04`: pull_request workflows
  [41973924515](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41973924515)
  và [41973924533](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41973924533)
  đều PASS, nhưng merge vẫn bị chặn bởi "9 of 9 required status checks are cancelled".
- Lượt `push` tương ứng
  [41973918319](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41973918319)
  cùng SHA bị hủy; các check trùng tên có kết luận cancelled.
- Cả `.github/workflows/verified.yml` và `quality.yml` dùng
  `cancel-in-progress: true` và nhóm concurrency không phân biệt
  `github.event_name`.

**Nguyên nhân gốc:** cùng nhóm cho push và pull_request của cùng một
workflow/nhánh. Một lượt chạy hợp lệ sau có thể hủy required checks của
lượt trước, dù SHA không đổi. Vấn đề thuộc CI orchestration chứ không
phải bằng chứng bài kiểm thử Python/FDS thất bại.

**Sửa:** đưa `github.event_name` vào concurrency group của cả hai
workflow. Vẫn chỉ giữ lượt mới nhất trong cùng loại sự kiện và nhánh,
nhưng push và PR không triệt tiêu nhau.

**Regression:** `tests/test_ci_concurrency_contract.py` kiểm tra cả hai
workflow phân biệt event và giữ cơ chế cùng-event cancellation.

**Nghiệm thu:** `FIXED_PENDING_VERIFICATION` đến khi CI chạy trên HEAD
PR và hai loại event cùng có required checks không bị hủy chéo. Không
nới lỏng branch protection hay dùng continue-on-error. Không tác động
đến kết luận khoa học IFC/FDS.

**Giới hạn:** CI vẫn phải hạn chế trùng công việc và chi phí runner; việc
chọn chính sách `push` cho nhánh nào là một tối ưu hạ tầng riêng.
