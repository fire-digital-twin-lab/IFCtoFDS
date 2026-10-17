# 02 — Phạm vi, ngoại lệ và ranh giới

## Trong phạm vi giai đoạn đang triển khai

- IFC2x3/IFC4 và IFC4x3 *theo khả năng thư viện đã xác minh*, không tuyên bố hỗ trợ schema chưa test.
- Một hoặc nhiều IFC cùng dự án, tọa độ/đơn vị/federation.
- Geometry kết cấu/kiến trúc ảnh hưởng miền khí: walls, slabs, beams, columns, ceilings, foundations/ramps, stairs, shafts, openings, doors/windows theo trạng thái hình học được chọn.
- MEP structure: ducts, duct fittings, damper, fans, terminals; pipes FP, fittings, valves, sprinkler, pumps, detectors nếu hiện có trong IFC; IFC classes có thể khác theo phiên bản schema.
- Export strategy `OBST`, `OBST+HOLE`, `GEOM`, approved approximation/voxel, `SEMANTIC_ONLY` hoặc `EXCLUDED_APPROVED`.
- Bảo toàn IFC GlobalId/STEP/type/name/tag/system/storey, provenance, geometry tolerance, manifold/mesh quality.
- Kiểm toán sai số hình học + open-space connectivity + source→output coverage; báo cáo có thể tái lập.
- CLI thực sự chạy + giao diện Web về sau; giữ chế độ legacy.

## Ngoài phạm vi (chưa được tự phát triển)

- HRR/thermal runaway nguồn cháy xe máy điện, combustion/smoke chemistry, vật liệu cháy, phun sprinkler, điều khiển quạt, thông số lưu lượng/áp suất giả định.
- Dự đoán AI/ML, dữ liệu huấn luyện, surrogate FDS, Digital Twin real-time, FD-Gen kịch bản, mô phỏng thoát nạn và tối ưu cảm biến.
- Không mô phỏng hệ thống thủy lực PCCC chỉ từ hình dạng ống; không khẳng định detector thật có behavior `DEVC` FDS khi chưa có dữ liệu/loại cảm biến tương thích.
- Không coi “mô hình visually similar” hoặc tệp FDS parse được là nghiệm thu khoa học.

## Mô hình “có/không có” dữ liệu nguồn

- **IFC có:** bắt buộc ghi nhận/kiểm tra phần tử và thông tin có thật, kể cả nếu chỉ semantic.
- **IFC không có:** báo `MISSING_SOURCE_DATA` hoặc `INCONCLUSIVE` tùy yêu cầu; không tự thêm thiết bị/ống.
- **IFC có hình học thiếu hoặc lỗi:** `NO_GEOMETRY`/`UNSUPPORTED`/`DEVIATED` với evidence, không tự đặt hình học đúng vì dự kiến có.
- **Có phần tử ngoài scope:** `EXCLUDED_APPROVED` nếu policy hợp lệ; không tính là lỗi missing.
- **Trong vùng giao cắt biên:** `KEEP_WHOLE`, `GEOMETRIC_CLIP_VERIFIED` hoặc `BLOCK_UNSUPPORTED` theo cấu hình; không clip theo bounding box một cách âm thầm.

## Đường phân cách nghiệp vụ

Phải tách ít nhất: `SOURCE_INVENTORY`, `SOURCE_GEOMETRY`, `SOURCE_SEMANTICS`, `FDS_REPRESENTATION`, `SIMULATION_PHYSICS`. Metadata có thể hiện diện mà không có primitive FDS; ngược lại, một FDS primitive có thể là trợ giúp tính toán và cần `source: synthetic/derived` có lý do thay vì gắn GUID giả.

## Điều kiện bổ sung ngoài giai đoạn

Khi người dùng yêu cầu chạy mô phỏng cháy sau này, lập hạng mục riêng để xác thực các điều kiện biên, quạt, HRR, gas species, devices và mesh sensitivity; không ngầm đưa vào công cụ chuyển đổi này.
