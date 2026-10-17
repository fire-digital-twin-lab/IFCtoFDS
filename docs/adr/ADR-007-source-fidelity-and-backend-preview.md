# Source fidelity, declared system semantics, and bounded backend preview

Date: 2026-10-17. Status: implemented; building-scale acceptance remains conditional on audit evidence.

The requested change is to preserve HVAC/fire-protection geometry, prevent valid
wall hosts disappearing when separate opening evidence is unavailable, and
support IFC sources that exhaust the browser import path. Existing source hashes,
scope, independent audits and explicit operational configuration remain required.

## Geometry and semantics

The existing `mapping` profile retains its reviewed MEP policy. A new explicit
`geometry-fidelity` profile emits valid MEP solids as passive OBST/GEOM geometry.
MEP operational status remains `NOT_CONFIGURED`; no HVAC flow network, sprinkler
particles, fan curves or fire scenario is generated. MEP proxies are included
as draft geometry while retaining `REVIEW_REQUIRED`; this still blocks accepted
mapping. Generic objects without MEP evidence remain reference geometry unless
reviewed. These shapes can change free space, so this profile does not
establish an operational simulation model.

`IfcSystem` evidence now retains IFC class, ObjectType, PredefinedType,
Description, property sets and classification references. Classification accepts
canonical enums and an exact declared ObjectType vocabulary, including supported
Vietnamese system descriptions. Unicode normalization includes Vietnamese đ.
Names such as `SPR 50` are never enough. Unknown descriptions and conflicting
declarations remain unresolved; a declared ventilation system is not promoted to
smoke extraction by its name.

`system_decisions` uses source-qualified system keys and the existing reviewed
decision schema. A reviewed passive promotion supplies the seven relevance
factors once per system. Entity decisions take precedence. Conflicting system
actions require an entity decision. Unknown system IDs are rejected.

A valid kernel-generated host solid is retained as GEOM when the separate opening
mesh is missing or invalid. Kernel-applied openings are neither filled nor
recomputed from guessed bounds. Opening verification stays INCONCLUSIVE with the
host key, opening STEP ID and extraction diagnostic. Invalid host solids remain
unsupported.

## Explicit domain intersections

`SOURCE_SOLID_DOMAIN_INTERSECTION` intersects the actual source solid with the
explicit domain using binary64 solid operations. It emits GEOM, keeps the source
mesh immutable, and independently compares the serialized output with the source
intersection. Air-passage comparisons use domain-intersected reference solids so
intentional removal outside the domain is not misreported as a blocked opening.
The geometry-fidelity profile selects this policy when an explicit domain is set
and no other boundary policy is supplied. Failed/empty intersections remain
withheld with diagnostics. The existing narrowly certified OBST policy remains
available independently.

This GEOM policy stays `PENDING_VALIDATION`: the OBST solver certificate cannot
certify GEOM boundary behavior. Mapping acceptance therefore remains INCONCLUSIVE
until corresponding effective-geometry evidence is implemented and supplied.

The new required `structural_completeness` gate accounts for in-scope walls,
curtain walls, slabs, beams, columns and roofs. Missing required primitives fail;
withheld/unresolved structures are inconclusive. Approved dispositions are
explicit. This gate proves accounting, not the airtightness of the source
building. Existing opening passage and solid comparison checks remain required.

## Import and memory

Sources over 8 MiB use `/api/preview-jobs` on the local Python backend.
Small-source legacy/file:// behavior remains available. Large sources
opened through file:// receive an actionable backend requirement.

The File is uploaded directly without a browser-wide ArrayBuffer/STEP string.
An isolated, cancellable worker consumes the IfcOpenShell iterator and writes
checksummed per-product binary payloads. Metadata accounts for all inventory
entities; unavailable physical shapes are counted explicitly. The browser fetches
two batches at a time (at most 16 meshes / 16 MiB each), verifies each mesh hash, retains canonical source identity, and
builds edge outlines on selection. This preview is `PREVIEW_ONLY`, verification
`NOT_RUN`. It is not an accepted conversion artifact. Large previews export through
Verified Mapping, which currently reuploads the original File.

Native `verts` and `faces` buffers must each be read once per mesh. Accessing their
IfcOpenShell property getter inside every slice repeatedly copies the entire
buffer and makes extraction quadratic. Both converter and preview now use the
single-read helper. Consumed converter iterator entries are removed. The
converter model and plan are released before the independent source audit starts;
the serializer also avoids joining the complete FDS twice.

Within each solid comparison, independently reconstructed exactly equal vertex
and oriented-face arrays share a single self-intersection proof. That proof is
still required. Changed coordinates/faces receive separate proofs. This reduces
duplicate work without caching exporter assertions or weakening tolerances.

IFC and FDS GEOM display buffers use coordinates relative to each product's
origin. The Object3D placement retains the original world coordinates in double
precision. This avoids collapsing thin walls when georeferenced coordinates are
in the millions of metres and the GPU uses Float32 vertices. Source/FDS geometry,
selection bounds and clipping coordinates are unchanged. Browser tests include a
3 cm object at generic northing 2.4 million metres.

The viewer still ultimately retains all displayed GPU geometry. Upload caps
remain configurable (default 200 MiB per source / 500 MiB total); these caps are
not a proven capacity guarantee. Fully virtualized geometry, streamed FDS audit,
whole-building air connectivity and solver-effective GEOM boundary certification
remain separate work.

## Reproduction

Select **Geometry Fidelity (Include HVAC / Fire Protection)** in the visible Verified Mapping profile,
or supply `{"profile":"geometry-fidelity"}` through the CLI configuration. To
measure a real preview without changing its source:

```powershell
python scripts/benchmark-backend-preview.py --source path/to/model.ifc --output scripts/out/model-preview
```

Tests cover malformed opening retention and uncertainty, invalid host rejection,
MEP geometry without operational directives, declared system labels/conflicts,
reviewed system decisions, exact domain intersections with a real cut opening,
single native-buffer reads, and a browser upload with whole-file reads forbidden.
The six frozen parity snapshots are retained; their harness additionally requires
the new structural completeness gate to PASS.
