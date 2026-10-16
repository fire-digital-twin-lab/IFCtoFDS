# 08 — Hợp đồng dữ liệu Canonical BIM Model

## Mục tiêu

Định nghĩa representation nhất quán giữa Python IFC Core → Mapping Engine → JS FDS exporter/Web Viewer → independent auditor. Có `schemaVersion`; validate bằng JSON Schema hoặc Pydantic; không dựa vào cấu trúc `displayMesh` và `exportMesh` không tương đương của legacy.

## Entity classes đề xuất

| Lớp | Fields bắt buộc tối thiểu | Invariants |
|---|---|---|
| `SourceFile` | `sourceFileId`, `originalFilename`, `sha256`, `schema`, `unitAssignments`, `transformToProjectMeters`, `provenance` | `sourceFileId` duy nhất trong run; SHA256 từ bytes nguồn |
| `SourceElement` | `elementKey`, `globalId?`, `stepId`, `ifcType`, `name?`, `tag?`, `storeyIds`, `systemIds`, `representationStatus`, `geometryId?` | Không bỏ records khi unsupported/no geometry |
| `CanonicalGeometry` | `geometryId`, `format`, `coordinates`, `transform`, `bbox`, `validity`, `openings`, `fidelity` | Units METERS, CRS có metadata, checksum geometry |
| `IfcRelationship` | `relationId`, `ifcRelationType`, `sourceKeys`, `targetKeys`, `evidence` | Không coi proximity là explicit |
| `MEPSystem` | `systemKey`, `sourceRef`, `systemType`, `members` | Chỉ thành viên từ source hoặc gắn manual evidence |
| `MEPPort` | `portKey`, `ownerElementKey`, `placement?`, `connectionRefs`, `direction?` | Port thiếu là UNKNOWN, không auto-create explicit |
| `ScopeDecision` | `elementKey`, `scopeId`, `status`, `reason`, `intersectionInfo` | Ảnh hưởng xuất thực, không chỉ viewer |
| `MappingDecision` | `decisionId`, `elementKey`, `role`, `strategy`, `tolerances`, `reasonCodes` | Policy/approver và version rõ |
| `FdsPrimitive` | `primitiveId`, `namelistType`, `sourceKeys`, `decisionId`, `geometryRef?`, `serializedRecordRef` | ID duy nhất trong FDS run; hỗ trợ source→many targets |
| `ValidationFinding` | `findingId`, `requirementIds`, `severity`, `status`, `sourceRefs`, `fdsRefs`, `measured`, `threshold`, `evidenceRefs` | Measured vs threshold có đơn vị |
| `RunMetadata` | `runId`, `sourceHashes`, `toolCommit`, `pythonVersion`, `ifcopenshellVersion`, `fdsVersion?`, `policyVersion`, `tolerances`, `artifactsHashes` | Mọi đầu ra có run fingerprint |

## Định danh không bền vững và không nhầm lẫn

- Identity khóa ổn định ưu tiên `(sourceFileId, globalId)`, trong đó `sourceFileId` xuất phát từ provenance (sha + optional logical source); nếu trùng GlobalId giữa hai file, không tự đồng nhất.
- STEP ID chỉ có nghĩa trong một IFC instance và có thể thay đổi khi export lại; dùng phụ trợ cho debug.
- Khi GlobalId thiếu/trùng/lỗi: dùng `(sourceFileId, stepId)` tạm thời, kèm flag `UNSTABLE_ID`; không suy ra identity giữa các lần import.
- `FDS_ID` được sinh độc lập với Name nguồn, nhưng liên kết bằng mapping manifest; tên tệp IFC gốc giữ nguyên trong metadata.

## Ví dụ semantic element (minh họa, KHÔNG phải dữ liệu nguồn thật)

```json
{
  "schemaVersion": "1.0.0",
  "elementKey": "source-01::2AGuidExample",
  "sourceFileId": "source-01",
  "globalId": "2AGuidExample",
  "stepId": 1234,
  "ifcType": "IfcDuctSegment",
  "name": "Duct-B1-001",
  "tag": null,
  "storeyIds": ["B1-guid"],
  "systemIds": ["Vent-B1-guid"],
  "geometryId": "mesh:sha256:...",
  "representationStatus": "GEOMETRY_EXTRACTED",
  "mappingDecisionId": "map-1234",
  "mappingStatus": "PENDING_VALIDATION"
}
```

**Lưu ý:** string ID và tên trong ví dụ chỉ là minh họa cấu trúc; không được agent dùng làm giá trị kết quả thực nghiệm.

## Geometry payload lớn

Không serialize một file JSON chứa hàng triệu số float/tris vào một request browser. Thiết kế:

- Metadata index JSON (IDs, type, bbox, transforms, hashes).
- Geometry sidecar dạng binary/mesh chunked có content hash và index.
- Sử dụng tọa độ đôi (double) trong tính toán chuẩn; chỉ chuyển float32 cho viewer nếu đánh giá sai số chấp nhận được.
- Hash phải nêu canonicalization (units, face ordering, transform và precision), không tự xem hash giống nhau khi chưa chứng minh tương đương hình học.

## Trạng thái phân cấp

- **Nguồn:** `PRESENT`, `NO_GEOMETRY`, `MALFORMED`, `MISSING_SOURCE_DATA` (áp dụng cho expected business object bị thiếu).
- **Quyết định:** `EXPORT_GEOMETRY`, `SEMANTIC_ONLY`, `EXCLUDED_APPROVED`, `UNSUPPORTED`, `REVIEW_REQUIRED`.
- **Kiểm toán:** `MATCHED`, `DEVIATED`, `MISSING`, `INCONCLUSIVE`, `UNSUPPORTED`, `EXCLUDED_APPROVED`, `SEMANTIC_ONLY`.
- **Run:** `ACCEPTED`, `REJECTED`, `BLOCKED`, `PARTIAL`, `NOT_RUN`. Không gộp các lớp trạng thái lẫn nhau.

## Versioning

Schema dùng semantic version; validation báo lỗi với schema không hỗ trợ, migrations tách riêng; JSON API/FDS manifests đi kèm version rõ. Thêm field tùy chọn không được phá importer/validator version cũ.
