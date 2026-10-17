# Pre-main Workbench stabilization

Base: `dev` / `adf3fdc3d19e558ee6b4b686de2ed0b7ca4827f0`.
Work branch: `codex/pre-main-stabilization`.

## Corrections

- Preserve existing canonical entity keys. Bind the source/key on scene inputs
  before indexing or creating native, Web-IFC and FDS meshes. Keep source-qualified
  keys through descriptor normalization, tree selection and viewport picking.
  Child edge helpers do not create duplicate selections.
- Compose per-object section, exclusion, category and Workbench visibility. Layer
  and root visibility remain inherited from parent groups. Updating one channel
  cannot re-enable an object hidden by another. IFC section planes retain their
  existing fragment-clipping behavior; FDS retains whole-primitive clipping.
- Restore opacity, transparency and depth writing when leaving Ghost mode, and
  preserve Ghost while changing the opacity slider.
- Close Inspector through the selection command/store, keeping tree, Inspector
  and viewport selection synchronized.
- Clear scenario contents, mapping binding and command history on source reset.
  Fire parameters are unset until explicitly supplied. HVAC drafts have no
  default flow/activation and remain INCONCLUSIVE. Invalid numeric flow values
  are rejected; the Inspector's operational HVAC control is disabled pending
  a reviewed parameter/provenance workflow. No scenario physics is serialized.
- Mapping colors use exact explicit strategies, with unknown/incomplete states
  orange and confirmed failures red. Review approval cannot establish a PASS in
  verification colors. A mapping strategy color is not an acceptance verdict.
- Mark all Workbench browser tests `browser`. The ordinary Python matrix excludes
  `solver` and `browser`; the browser job installs Playwright/Chromium and executes
  the browser marker as well as the existing conversion regression.

## Reproduction and local evidence

Before correction, `node scripts/test-workbench-stabilization.js` failed three
independent groups: canonical identity, unknown mapping colors and fire defaults.
After correction all three pass. It also covers duplicate GUIDs across sources,
STEP fallback, scenario reset and invalid HVAC values.

Local Windows / Python 3.12 results:

| Check | Outcome |
|---|---|
| Python core, `-m "not solver and not browser"` | 235 passed, 6 deselected |
| Browser marker, Edge headless | 4 passed, 237 deselected |
| Pinned FDS 6.11.1 solver marker | 2 passed, 239 deselected |
| Eight JavaScript regression suites | PASS |
| Generated worker bundles vs tracked bundles | No content difference |
| Existing browser conversion script | Quick HTTP/file with/without Web-IFC PASS; Verified HTTP PASS |
| Verified through `file://` | NOT_SUPPORTED, existing HTTP guidance retained |

The new browser regression imports `tests/browser/box.ifc`, clicks the semantic
tree and raycasts the actual wall, checks the exact key in both directions, then
exports FDS and tests section/hide/isolate/exclusions, category visibility, Ghost
restoration and source replacement. Both native and actual Web-IFC meshes are
covered. It is a small integration fixture, not real-building acceptance.

Logs/JUnit and browser results are local under `scripts/out/pre-main/`. Core tests
reported 30 existing library warnings (Starlette/trimesh). Initial sandbox runs
were interrupted because subprocess/browser startup did not complete there;
the completed checks above used permission to start local child processes.
An initial integration-test attempt used the conversion button while its workflow
tab was hidden; that test step was corrected and the browser group rerun.

Run the same gates through `.github/workflows/verified.yml` on the delivered commit.
Local Windows results do not establish the Linux/Python 3.11 matrix result.

## Release boundary

This change targets `dev`. Do not merge `dev` into `main` until the delivered
revision's required remote CI checks pass and the stabilization PR is reviewed.
Branch protection is a separate repository-owner setting, not changed here.
Research-basement approval, general GEOM effective geometry and simulation
acceptance retain their existing limitations.

## Pre-main edge visibility follow-up

PR #8 was merged at `dev@c45ec20c6713c19114fc71b3c6a7069a95c82487` after
approval of the tested head `6efe550`. A small follow-up binds IFC edge display
to its own visibility channel at native/Web-IFC creation and checkbox changes.
Workbench visibility updates cannot restore disabled edges. Existing opening
outlines remain visible by policy, subject to the owning object's visibility.

Before correction, the extended real-IFC test failed on both native and Web-IFC
meshes. After correction it checks edges OFF before loading, Hide/Show, Reset,
Isolate/Reset, and edges ON while the entity is hidden. The Node regression also
checks the intended opening-outline exception. Geometry, review and boundary
status strings are normalized consistently (case and surrounding whitespace),
with regression cases that previously selected a green mapping color.

This follow-up changes display state and tests only. Source identity improvements
for advanced Quick federation and the separate Scenario Engine remain future work;
neither is claimed as completed by stabilization.
