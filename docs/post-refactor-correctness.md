# Post-refactor correctness delivery

Base: `refactor/modular-verified-core` at `36db24e`.
Work branch: `codex/post-refactor-correctness`.

## Contract corrections

- Public regression IFCs have LF checkout attributes. Each parity case checks the
  exact input SHA-256 before conversion. Production IFC hashing still uses the
  original bytes. No private IFC was normalized or added to Git.
- CSV parity hashes parsed rows, including every field. CSV output uses LF and is
  written as UTF-8 bytes: Windows text-mode writing previously turned CRLF into
  CRCRLF, adding empty rows. Artifact checksums continue to hash the saved bytes.
- The six snapshots were regenerated from fixed input bytes. Comparing against the
  original snapshots after substituting source SHA-256 tokens showed identical
  verdicts, gates, primitive bounds/counts, classifications, scope, roles and
  dispositions. Changed hashes and source-qualified keys are intentional fixture
  identity changes. No tolerance or geometry assertion was removed.
- Serialization reads strategy, bounds, domain and cell size from MappingPlan.
  It validates complete entity coverage, authorization, source scope, solid/box
  evidence and the supported boundary intersection. Conflicting cell sizes are
  errors. An absent plan domain stays absent; it does not expand around geometry.
- Legacy `serialize_fds(model, cell_size=...)` constructs a plan and returns the
  same `(text, manifest)` tuple. The serializer leaves the input plan untouched;
  emitted IDs are returned through the manifest and mirrored to model elements
  for compatibility. Source meshes are retained. Artifact schemas remain 0.5.0.
- Follow-up review: a source-policy OBST/GEOM cannot become NONE, SEMANTIC_ONLY,
  EXCLUDED_SCOPE or EXCLUDED_APPROVED merely by editing the plan. Changing a
  disposition requires applying the explicit reviewed decision through source
  policy before constructing a new plan. Existing reference-only, out-of-scope,
  pending-boundary, semantic and approved exclusions remain valid. Non-emitting
  dispositions cannot be relabelled by the serializer. Rejections identify the
  entity and leave both inputs unchanged. Independent audit remains required.
- AcceptanceEvaluator copies checker outcomes and finalizes verdicts before
  returning. FAIL takes precedence over incomplete gates. The report is mutable
  but detached from checker evidence. Production audit retains the full existing
  engine; the two extracted checkers do not replace the remaining checks.
- Adapter and compatibility reference inspection now share content validation.
  Both read approval.json, check its bundle binding and verify schemas, geometry
  payloads, inventory/manifest and reference projections. Existing 0.4/0.5 bundles
  remain readable; inspection never creates or inherits approval.

## Stack overflow and diagnostics

The reproducible failure is in `holeForOpeningExtrusion`: passing all opening
heights to `Math.min.apply` exceeds V8's argument limit. The independent stress
case has 150,000 profile points. The reviewed base throws RangeError; the fix
checks the same bottom/top coordinates incrementally and retains every point.
No stack-size setting, geometry simplification or opening guard was changed.

Workers retain name, message, stack, stage, request ID and entity STEP ID when
known. Verified frontend errors also retain the job ID. The Checks panel offers
a diagnostic JSON download without IFC text, FDS text, mesh or full inventory.
Viewer failures are labelled as display failures and keep the FDS download.
Changing the source prevents delayed worker results from replacing the new view.
Verified polls use per-run identities; cancel/replacement stops the server job
and late responses cannot overwrite the next job's artifacts or progress.
The HTTP and inline bundles are generated from the same sources.

## Reproduction and checks

```text
python -m pytest -q -m "not solver"
node scripts/test-large-opening.js
node scripts/test-worker-bundle-parity.js
node scripts/test-background-export-worker.js
python scripts/test-conversion-browser.py
python -m pytest -q -m solver
```

Playwright 1.58.0 and Chromium (Edge locally on Windows) are test-only tooling.
The browser suite selects a public IFC fixture and covers Quick HTTP/file modes,
actual Web-IFC preview enabled/disabled, Verified over HTTP, retained downloads
after injected viewer errors, diagnostic downloads and late messages after source
replacement. Verified from file URLs returns the existing instruction to open
the local HTTP app; this is an explicit unsupported case, not a successful run.
Browser evidence is uploaded by a dedicated Linux CI job. Existing Python
Windows/Linux 3.11/3.12, JavaScript and pinned FDS jobs remain required checks.

The large-opening test can replay the reviewed implementation locally with
`node scripts/test-large-opening.js --baseline` (requires commit 36db24e).
It is expected to fail; the ordinary command must pass. Local evidence and run
logs are under `scripts/out/post-refactor/` and the browser output directories.
All failed/timeout attempts are retained separately from successful runs.

Local verification after the CSV and coherent-mutant corrections: 155 Python
tests passed (two solver tests deselected); both real FDS 6.11.1 solver tests
passed separately. Seven JavaScript suites include the new large-opening stress
case. Browser cases passed with actual preview enabled/disabled over HTTP/file,
and Verified over HTTP; the two file-URL Verified cases are NOT_SUPPORTED as
described above. CI repeats the checks on the delivered commit; local Windows
results alone are not a Linux pass claim.

## Real-model limits

The external ALL_FDS_2027.ifc source has SHA-256
`a54ba512754efe1f82b87d7fb1853361889ad00d59be5a7a14ecac075e2cc7af`.
Native Quick parsing rebuilt 2,122 supported browser elements. Both native and
browser Quick export stopped at the existing incomplete-opening guard for slab
STEP 6490. The initial full Web-IFC preview attempt timed out after 315 seconds;
low available system RAM was observed and the owned test browser was stopped.

These attempts do not establish the cause of the user's original screenshot and
do not prove full conversion of this building. The large-profile stack failure
is separately reproduced and fixed. The incomplete-opening blocker remains
explicit; no elements were silently removed to obtain a successful export.
No new B1/B2 approval, historical parity or SIMULATION_VERIFIED claim is made.
