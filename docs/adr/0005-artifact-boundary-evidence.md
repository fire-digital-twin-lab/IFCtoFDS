# ADR 0005 — saved geometry artifacts and evidence-bound OBST intersections

Status: implemented software policy; research approval remains pending.

Separate API summaries from large saved artifacts. Use lossless binary mesh payloads with an entity index and lazy independent audit. Keep placement provenance distinct from already transformed world vertices. Preserve the 0.4 reader without inheriting approval on format migration.

Keep the computational domain fixed and source geometry complete. The sole new boundary representation is the positive intersection of an independently proved structural axis-aligned box and an explicitly declared single domain. It remains pending until the exact serialized bytes pass source/representation and pinned solver/effective checks, including a version-bound analytic fixture certificate. This supersedes blanket blocking only for the supported OBST subset; it does not enable arbitrary clipping or MEP obstacles.

Generic mapping status cannot imply B1/B2 research acceptance. Recognize registered sources without automatically selecting profile, domain or reference. Create a new DRAFT research baseline and require human approval of its full bundle. Do not assert historical parity.
