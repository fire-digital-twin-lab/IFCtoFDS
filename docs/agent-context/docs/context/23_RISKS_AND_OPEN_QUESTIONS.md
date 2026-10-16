# 23 — Risk register và quyết định chưa đóng

| ID | Rủi ro / điểm còn mở | Tác động | Phương án giảm thiểu / trạng thái |
|---|---|---|---|
| R-01 | IFC công trình B1/B2 không có trong gói hiện tại | Không nghiệm thu thực địa | Yêu cầu source bytes + SHA và FDS mới nhất; dùng fixtures trước |
| R-02 | Mô hình nhiều IFC không cùng origin/units | FDS lệch hàng mét, sai kết cấu/MEP | Federation gate, transforms explicit, block ambiguous |
| R-03 | IfcOpenShell không tạo được geometry một số exotic representations | Missing elements | Inventory preserving + unsupported reason, alternate kernel/human review |
| R-04 | Ống gió là hollow volume nhưng exporter tạo solid blocker | Chặn lưu thông khí | Tách semantic/internal airway/shell, FDS policy + topology audit |
| R-05 | Mesh FDS thô làm mất opening | Sai hiệu quả hình học | Effective geometry check + mesh sensitivity |
| R-06 | IFC không có port/MEP systems | Không có ground truth connectivity | UNKNOWN instead of inferred; human review |
| R-07 | Khi clone fork có upstream changes / dirty worktree | Merge conflicts/ghi đè | Commit SHA+worktree mới, no destructive commands |
| R-08 | AGPL fork + LGPL dep + GPL code khác | Vi phạm license | Giữ notices, kiểm tra per dependency, không copy BFDS runtime |
| R-09 | Huge IFC -> RAM/CPU/timeouts | Worker crash/đợi quá lâu | Streaming geometry, limits, caching, profiling |
| R-10 | Parser và validator dùng chung mesh | False positives | Re-open source and parse FDS, diverse geometry tests |
| R-11 | Tên FDS ID thay tên IFC làm khó phân loại | Không truy vết | Source tags/GlobalId/system in manifest và viewer inspector |
| R-12 | Inline worker bundle lỗi thời | UI chạy khác code đã sửa | Regenerate + parity test in CI |
| R-13 | Thiếu official FDS solver/Smokeview | Chưa xác thực effective geometry | Static audit + `NOT_RUN`, install solver phase riêng |
| R-14 | IFC chứa thông tin công trình nhạy cảm | Data leak khi push public | Local-first, redact logs, gitignore fixtures private |
| R-15 | Kiểu IFC/PSets đặt tên không nhất quán | Misclassification HVAC vs FP | Multi-signal classification with `UNKNOWN`/review |
| R-16 | Khi combine voxel/GEOM tệp FDS quá lớn | Solver chậm, khả năng mở rộng thấp | Fidelity-performance frontier, sample model benchmarking |

## Câu hỏi thực sự cần người dùng/chuyên gia quyết định ở bước sau

- Khi có source thực: những phần tử/hệ thống nào bắt buộc **phải có geometry FDS** chứ không chỉ semantic? (policy theo mục tiêu mô phỏng)
- Tolerance được phê duyệt theo mesh/kích thước/ý nghĩa cấu kiện cụ thể là bao nhiêu?
- Hệ quy chiếu và control points cho multi-IFC có đầy đủ không?
- Những lỗ mở/cửa có trạng thái mở/đóng mặc định nào cần được sử dụng ở testcase?
- Danh mục system/type nào coi là bắt buộc để chặn nghiệm thu cho công trình?
- Run CLI offline trên Windows/Linux nào là môi trường ưu tiên; cấu hình FDS/Smokeview có sẵn hay chưa?

Các câu hỏi này **không cản trở** giai đoạn Phase 0/1 trên fixtures; chỉ cản trở nghiệm thu trường hợp công trình thực tế hay quyết định vật lý thiếu dữ liệu.
