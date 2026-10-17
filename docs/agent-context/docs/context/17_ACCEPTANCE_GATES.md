# 17 — Acceptance Gates và Definition of Done

## Phân loại mức độ lỗi

| Severity | Mô tả | Ví dụ |
|---|---|---|
| P0 | Chặn khả năng chứng minh correctness cho phạm vi bắt buộc / gây sai nghiêm trọng | Bỏ sót im lặng cấu kiện nguồn; bít trục hút khói; sai hệ tọa độ toàn mô hình |
| P1 | Sai hình học/MEP quan trọng hoặc thiếu validation thành phần bắt buộc | Mất opening, mất HVAC/PCCC system membership, unsupported mapping không báo |
| P2 | Sai ít ảnh hưởng, thiếu đo/UX/doc làm giảm tái lập | Summary khác số primitives, thiếu metadata bổ sung, stale docs |
| P3 | Cải tiến chất lượng/trải nghiệm không chặn nghiệm thu | CSS/UX polish, optional charts |

Severity phụ thuộc chức năng và phạm vi, phải có rationale; không tự hạ mức để release.

## Acceptance Gates theo phase

| Gate | Điều kiện đạt | Bằng chứng |
|---|---|---|
| G0 — Baseline | Clean worktree/branch, scripts tests thực hiện, dependency/inventory/license chốt | baseline.md, checksums, test logs |
| G1 — Geometry | openings/transforms/units/scope không silent fail; golden fixtures đúng | source-vs-export geometry reports |
| G2 — MEP | toàn bộ object thuộc source scope được accounted; explicit graph bảo toàn | systems.json, MEP coverage report |
| G3 — FDS Mapping | FDS serialized reparse, policy clear, output refs consistent, no illegal fallback | `.fds`, manifest, round-trip tests |
| G4 — Independent Audit | mutation tests phát hiện lỗi; objective acceptance reasons | findings, acceptance report |
| G5 — Web Integration | verified UI thực gọi Python job, quick legacy vẫn chạy, download artifacts | E2E logs/screenshots |
| G6 — Real project acceptance | có source IFC B1/B2 đã xác thực + FDS outcome + engineer review nếu cần | evidence package by case/run |

## Release criteria

- `P0=0` và `P1=0` *chưa giải quyết* **trong phạm vi tuyên bố**.
- Source inventory accounted = 100% theo tập được định nghĩa (bao gồm trạng thái excluded/no geometry/semantic only).
- Required geometry mapping/preservation nằm trong tolerance đã phê duyệt; không có blocked critical openings.
- Hệ HVAC/PCCC có report theo system/type: phân biệt completeness/geometry/connectivity/function readiness.
- Traceability loss = 0 cho generated FDS primitives có nguồn IFC; synthetic primitives có derivation.
- Không có unsupported/inconclusive thuộc tập bắt buộc bị lờ đi; có thể release bản partial với nhãn `NOT_VERIFIED_FOR_SCOPE`, không được gắn ACCEPTED.
- Các tests có run logs; mọi NOT_RUN/BLOCKED được khai báo.

## Nghiệm thu solver

Giai đoạn này không cần thiết lập mô hình cháy vật lý; vì thế solver verification ở ca geometry-only áp dụng nếu đầu vào hợp lệ và executable hiện có. Nếu chưa chạy được, báo `FDS_SOLVER_NOT_RUN` và giữ gate liên quan ở BLOCKED, nhưng những gate static geometry riêng vẫn đánh giá được. Không tự yêu cầu tạo HRR/thiết bị giả chỉ để tạo ra log mô phỏng.

## Definition of Done cho mỗi PR

- Tests trước/sau và chứng cứ đã tái hiện lỗi.
- Code + test + docs + schema migrations khi cần.
- API changes có backward compatibility hoặc migration.
- Không phá Quick mode, parity inline worker được kiểm chứng khi có liên quan.
- Update risk register, acceptance matrix, version/changelog.
- Auditor độc lập (agent khác/ người) đối chiếu code và artifact thật; report rõ status.
- Không tự merge PR.
