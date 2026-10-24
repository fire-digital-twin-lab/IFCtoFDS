# Spec: EV Fire Scenario Batch (full simulation)

Ngày: 2026-10-26. Trạng thái: chờ duyệt.

## 1. Mục tiêu

Sinh hàng loạt kịch bản cháy xe điện (xe máy + ô tô) từ mô hình IFC đã verified,
chạy mô phỏng FDS đầy đủ (lưới $D^*/\Delta x$, HVAC/CTRL liên động, solver thật),
tổng hợp verdict từng case qua UI. Mọi preset thiếu thực nghiệm được tham số hóa
với nhiều lựa chọn phổ biến + confidence, không hardcode một giá trị "đúng".

## 2. Ràng buộc

- A3 (`js/workbench/state/scenario-store.js`): scenario không mutate MappingBundle,
  chỉ tham chiếu `bundle_sha256`.
- Fail-closed: yêu cầu `MAPPING_VERIFIED` + review tay trước seal; scenario fail
  mesh gate → INCONCLUSIVE, không chạy solver.
- Mọi bản ghi thư viện có `citations[]` + `confidence` (low/medium/high); preset
  `unknown-origin` bắt buộc confidence low + cảnh báo trong báo cáo.
- Báo cáo ghi rõ: tiền xử lý hình học + kịch bản giả định, cần kỹ sư PCCC thẩm
  định độc lập.

## 3. Kiến trúc (Approach A, đã duyệt)

### 3.1 EV physics library
- `ifc_to_fds/fire/ev_library.py`: load/validate bản ghi JSON, versioned.
- `reference-cases/ev-library/*.json`: một file mỗi (vehicle_class, chemistry).
- Schema: `{vehicle_class, chemistry, pack_kwh_range, peak_hrr_mw_range,
  t_alpha_s, growth, yields {CO, soot, HF}, citations[], confidence, notes}`.
- Preset khởi tạo: e-bike/moped 0.5-3 kWh (LFP/NMC/unknown); ô tô 40-100 kWh
  (NMC/LFP, peak 2-7 MW/xe). Dải giá trị thay vì điểm, phản ánh uncertainty.

### 3.2 Scenario emitter
- `ifc_to_fds/fire/scenario_emitter.py`: MappingPlan + vị trí đỗ từ IFC
  (space/storey chứa xe) → `&REAC/&RAMP/&BURN` trên `&SURF` xe cháy,
  `&DEVC/&CTRL` (sprinkler/detector), trạng thái cửa/HVAC theo profile
  `fire-scenario`. Lan truyền cụm xe máy (0.3-0.5 m) là mode mặc định cho
  bãi xe máy.
- Output gắn `bundle_sha256` + `ev_library_version`; seal chỉ sau review tay.

### 3.3 Mesh & solver gates
- Tính $D^*$ từ HRR từng scenario; gate $4 \le D^*/\Delta x \le 16$.
- Cài FDS 6.11.1 (scripts/install-fds.py đã có); bật solver/effective/mesh gates.
- Remediation hình học trước: Duplex.ifc đang REJECTED (self-intersecting solid,
  unsupported geometry) phải về VERIFIED trước khi batch.

### 3.4 UI matrix + batch queue
- Panel mới trong `js/workbench`: ma trận (số xe, khoảng cách, SoC,
  % NMC/LFP/unknown, cửa/thông gió) → sinh N scenario JSON → queue N jobs qua
  JobService hiện có → tổng hợp verdict + báo cáo gộp qua checkpoint API.
- Không mutate MappingBundle; mỗi scenario lưu preset đã chọn + confidence.

## 4. Thứ tự thực hiện

1. Remediation hình học: xử lý self-intersecting/unsupported geometry trong
   pipeline (không sửa file IFC mẫu) để Duplex.ifc đạt VERIFIED; nếu hình học
   mẫu sai thật thì document rõ và chọn mẫu khác làm golden cho batch.
2. EV library + schema + 2 preset đầu (e-bike LFP, ô tô NMC).
3. Scenario emitter + profile `fire-scenario`.
4. Mesh/solver gates + cài FDS.
5. UI matrix + batch queue + báo cáo gộp.

## 5. Tiêu chí nghiệm thu

- Full suite xanh (pytest + JS harnesses) sau mỗi phase.
- Mỗi preset có citation hoặc `confidence: low` + cảnh báo显式 trong báo cáo.
- Scenario fail mesh không chạy solver (test khóa).
- Báo cáo gộp ghi rõ giả định + yêu cầu thẩm định độc lập.
