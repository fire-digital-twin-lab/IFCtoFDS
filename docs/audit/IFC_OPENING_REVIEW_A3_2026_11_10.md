# A3 — Hàng đợi review opening IFC thực (10/11/2026)

**Phạm vi:** quan hệ `IfcRelVoidsElement` và `IfcRelFillsElement`, chưa xác minh geometry/door state/airflow.  
**Dữ liệu:** chứa IFC STEP ID/GlobalId **nhạy cảm**; chỉ lưu máy được ủy quyền, không gửi public Actions/artifact/GitHub.  
**Status:** `UNREVIEWED`, `NOT_EVALUATED`, science `INCONCLUSIVE`.

## Vì sao có bước A3

Source Dossier A1 xác nhận số quan hệ void/fill; song dữ liệu công trình vẫn phải qua human review trước khi gán OPEN/CLOSED. Ví dụ mô hình hầm hai tầng có nhiều opening không có filling, nhưng đây **không** phải bằng chứng tất cả đều là đường thông khói; chúng có thể là lỗ kỹ thuật, cửa chưa modeled, shaft, hoặc thông tầng. `IfcRelConnectsPathElements` không phải thuật toán airflow-connectivity.

## Lệnh thao tác (offline/local only)

`python -m ifc_to_fds opening-review "<private>.ifc" -o ".local-reference-cases/opening-review.json"`

Output `.json` dùng `O_EXCL`, không ghi đè và POSIX mode 0600; trên Windows phải bổ sung NTFS ACL. Không đưa output này vào PR, issue, logs hoặc public CI. Mỗi bản ghi có `opening`, `hosts`, `fill_elements` gồm GlobalId/STEP ID/IFC type để operator tìm chính xác trong Revit/BIM viewer. Mã lệnh không in các định danh này lên stdout.

## Review algorithm và giới hạn

1. Đếm mọi opening/void/filling relation bằng IfcOpenShell, không tạo BREP và không đặt cửa OPEN/CLOSED.
2. Liên kết các quan hệ bằng STEP ID của `IfcOpeningElement`; báo orphan/unknown opening, host/filling thiếu, duplicate relation.
3. Không có `IfcRelFillsElement` → `NO_FILLING_RELATION`, **không** phải `OPEN`. Có filling dạng `IfcDoor` → `PHYSICAL_OPEN_CLOSE_STATE_NOT_PROVEN`, **không** phải `CLOSED`.
4. Thiếu `IfcRelVoidsElement` hoặc representation → yêu cầu review; không tạo HOLE trong FDS.
5. Mỗi opening có `human_review_status=UNREVIEWED`, `physical_state=UNKNOWN`, `airflow_connectivity=NOT_EVALUATED`, `fds_effective_geometry=NOT_EVALUATED`; toàn file có `review_approval=NOT_GRANTED`.

## Điều kiện nghiệm thu

- Negative tests: duplicate relations, invalid host/filling, orphan opening, source SHA sai, không tự gắn OPEN/CLOSED.
- Unit test và integration test chạy với IFC `tests/baseline/fixtures/opening.ifc` trong CI; riêng IFC hầm thật chạy local có quyền truy cập.
- Các kết luận phải được đối chiếu với hình học BREP, bản vẽ kiến trúc/MEP và trạng thái cửa vận hành; `IfcRelFills` chỉ nói quan hệ phần tử.
- Kỹ sư phải xem lại 100% opening liên quan khoang cháy/dốc/giếng/cửa/biên CFD trước khi tạo `air-path graph`. Các phần tử không review giữ `INCONCLUSIVE`.
- A3 không tự thay đổi `FDS HOLE/VENT`, `GEOM/OBST`, accepted reference hoặc scientific ledger.
- 4 workflow CI trên **final PR HEAD** phải PASS; main push CI cần xác minh lại sau merge.

## Next: A4/A5

A4: topology các vùng/khoang dựa trên hình học và nguồn MEP/bản vẽ được duyệt, không suy từ IFC room name. A5: independent geometry oracle và effective FDS grid geometry so opening cutoff, không dùng cùng một library để tự kiểm định lẫn nhau.

**Rollback:** revert module/CLI/tests/docs A3. Không có migration, không đổi DB/solver hay file IFC. Không claim production-ready hoặc simulation-verified.
