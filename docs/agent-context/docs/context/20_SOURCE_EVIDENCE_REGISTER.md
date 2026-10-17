# 20 — Sổ đăng ký nguồn và độ tin cậy của bằng chứng

## Bằng chứng đã hiện diện tại thời điểm lập context

| Code | Nguồn | Mức tin cậy / cách sử dụng |
|---|---|---|
| SRC-01 | `IFCtoFDS-v0.1.0.zip`, SHA `3ea08378...9214bf` | Đã hiện diện và inspect; baseline snapshot release, KHÔNG là fork HEAD mới |
| SRC-02 | `IFCtoFDS_v0.1.0_Code_Audit.md` (15/10) | Ghi nhận findings/test run trên ZIP; cần regression lại |
| SRC-03 | `IFCtoFDS_v0.2.0_Implementation_Plan.md` | Kế hoạch triển khai, không chứng minh đã hoàn thành |
| SRC-04 | `MASTER_PROMPT_IFCtoFDS_IfcOpenShell_End_to_End.md` | Yêu cầu phát triển được soạn trước, có hiệu lực hướng dẫn |
| SRC-05 | GitHub `fire-digital-twin-lab/IFCtoFDS` | Kiểm tra 16/10: fork upstream, `main@7352195f...`, AGPL. Verify lại khi bắt đầu |
| SRC-06 | Repo upstream `ProfRino/IFCtoFDS`, README/LICENSE/CITATION | Xác định công cụ gốc Web browser + provenance, AGPL-3.0 |
| SRC-07 | `Bao_cao_tieu_chi_anh_xa_IFC_FDS_TNR13.docx` (bộ tiêu chí người dùng tạo trước) | Nguồn 11 nhóm C01–C11, independent audit; không phải kết quả pass công trình |
| SRC-08 | Trao đổi người dùng 03–16/10 về B1/B2, HVAC/PCCC, alias, không kịch bản | Nguồn requirement/decision; số liệu ca được xem như historical until revalidated |

## Danh sách chưa có / chưa có thể xác nhận trong gói

- Các file IFC công trình hai tầng hầm gốc, FDS công trình gần nhất, source PCCC/HVAC thực tế **không nằm trong ZIP release v0.1.0** và chưa được truy cập trong lần lập context này.
- Toàn bộ kịch bản và đặc tả riêng để sửa FDS cũ, nếu không còn file thì phải xin lại khi audit case cụ thể; không tự tái dựng chính xác từ tường thuật.
- Không có ground truth số lượng quạt sự cố, CO sensors, sprinkler hay công suất/tọa độ thực từ source IFC công trình trong gói này.
- Chưa có FDS solver log nghiệm thu thực tế cho project, benchmark ngang hàng giữa fork/BFDS/IfcOpenShell.

## Danh sách reference nên agent tự kiểm tra

- Upstream https://github.com/ProfRino/IFCtoFDS
- Fork https://github.com/fire-digital-twin-lab/IFCtoFDS
- IfcOpenShell https://github.com/IfcOpenShell/IfcOpenShell và https://docs.ifcopenshell.org/
- Voxelization Toolkit https://github.com/IfcOpenShell/voxelization_toolkit
- BFDS https://github.com/firetools/bfds
- NIST FDS https://github.com/firemodels/fds và https://pages.nist.gov/fds-smv/
- FD-Gen https://github.com/usnistgov/FD-Gen (ngoài scope hiện tại)

## Quy tắc provenance cho tài liệu này

Không trộn kết quả code audit với benchmark; không chuyển đánh giá đề xuất thành yêu cầu khoa học tuyệt đối nếu chưa có ADR; không chuyển ước tính B1/B2 thành thông số của một IFC khác; không dùng link/README của upstream làm bằng chứng đã kiểm chứng fork tại HEAD sau này.
