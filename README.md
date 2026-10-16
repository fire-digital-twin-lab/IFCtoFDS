# IFCtoFDS

[![Listed on FDS Third-Party Tools](https://img.shields.io/badge/Listed%20on-FDS%20Third--Party%20Tools-1f5b96?logo=github&logoColor=white)](https://github.com/firemodels/fds/wiki/Third-Party-Tools)
[![Latest release](https://img.shields.io/github/v/release/ProfRino/IFCtoFDS?label=latest&color=blue)](https://github.com/ProfRino/IFCtoFDS/releases/latest)
[![License: AGPL-3.0](https://img.shields.io/github/license/ProfRino/IFCtoFDS?label=License&color=yellow)](LICENSE)

IFCtoFDS turns an **IFC** building model — the format every modern BIM tool
exports — into a **Fire Dynamics Simulator (FDS)** geometry input file with a separate acceptance report,
so fire-safety engineers can move from architectural geometry to a simulation
mesh without rebuilding the model by hand.

The workbench has two modes:

- **Quick Conversion** runs in the browser for preview and preliminary conversion.
- **Verified Conversion** uses a local Python/IfcOpenShell service, explicit export scope,
  multiple IFC sources, provenance manifests and independent audit gates.

Mapping audit returns `MAPPING_VERIFIED`, `REJECTED` or `INCONCLUSIVE`, with a
separate simulation result. Research acceptance additionally requires an approved
golden reference. Scoped domains stay fixed, boundary elements require evidence,
and MEP defaults to reference geometry outside FDS. Simulation verification and
GEOM cut-cell evidence remain incomplete. See
[Current mapping guide and limitations](docs/golden-mapping-parity.md).
For the 0.5 compact API, binary geometry package and narrow solver-backed OBST boundary policy, see [artifact and boundary guide](docs/artifact-boundary-v05.md).

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m ifc_to_fds serve
```

Open `http://127.0.0.1:8000`. Verified Conversion uses this backend's same-origin page.

![Demo](demo/demo.gif)

> **Disclaimer:** No responsibility is taken for the use or output of this tool.
> All results must be independently verified by a qualified fire safety engineer
> before use in any design or regulatory context.

---

## Project team

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/ProfRino">
        <img src="https://github.com/ProfRino.png?size=100" width="100" alt="Prof Rino Lovreglio"><br>
        <strong>Prof Rino Lovreglio</strong>
      </a><br>
      Project lead and developer
    </td>
    <td align="center">
      <a href="https://github.com/resilienceengineer">
        <img src="https://github.com/resilienceengineer.png?size=100" width="100" alt="resilienceengineer"><br>
        <strong>resilienceengineer</strong>
      </a><br>
      Project collaborator
    </td>
  </tr>
</table>

## Features

Quick mode uses `index.html` and static JavaScript modules. Verified mode additionally requires the local Python service described above.

* **Native IFC parser.** Handles `IfcExtrudedAreaSolid`, `IfcFacetedBrep`,
  `IfcTriangulatedFaceSet`, `IfcFaceBasedSurfaceModel`, planar
  `IfcBooleanClippingResult` cuts, and `IfcRelVoidsElement` openings. Non-convex
  outlines (L / U / T floor plates) are re-triangulated with earcut.
* **Two opening strategies.** **HOLE** emits one continuous `&OBST` per
  axis-aligned wall/slab plus rectangular `&HOLE` cutouts — cleaner FDS file,
  exact opening rectangles. **Voxelization** stair-steps small `&OBST`s around
  each opening; use it for arched or curved openings that `&HOLE` cannot
  represent.
* **Optional closed window/door fills** in window-blue and door-brown
  `SURF`s. With the HOLE strategy, closures are deferred to the end of the
  namelist so wall `&HOLE`s cannot carve the glass.
* **Auto-extruded flat slabs.** Floors whose IFC representation the parser
  couldn't extrude (some Revit-exported slabs and tapered insulation roofs) are
  auto-inflated to a default thickness so their L / U outline is preserved
  rather than collapsing to a zero-volume polygon.
* **Three view modes** (Overlay / FDS / IFC) with independent opacity sliders,
  per-layer toggles (OBST / HOLE / VENT / GEOM / IFC structure / fills / other),
  and a six-slider clip box that hides FDS primitives outside the kept volume.
* **First-person walk mode.** Click any floor or stair surface to place
  yourself, then WASD + mouselook to walk through the building. Door closures
  and `&HOLE` volumes are passable so you can step through doorways.
* **Keyboard navigation.** Number keys `1`–`6` and `0` snap to canonical views.
  Arrow keys orbit; Shift+arrows dolly or strafe.
* **Background conversion** runs in a Web Worker so the interface stays
  responsive while a 5 000-product IFC is being processed. A live progress
  banner shows the current element.
* **Saved provenance.** Every emitted `&OBST` / `&GEOM` / `&HOLE` carries an
  `! IFC_SOURCE` comment with IFC type, GlobalId, STEP id, and source name so
  the link to the source model survives a save-and-reload round trip.

## Download / Try it live

> **👉 [Run it now in your browser — profrino.github.io/IFCtoFDS](https://profrino.github.io/IFCtoFDS/)**
>
> No installation, no local server, no account. Just click *Open IFC* and load
> an `.ifc` model. The hosted upstream demo provides Quick Conversion.
> Verified Conversion uses the local Python service described above.

For a versioned snapshot, download the [latest release zip](https://github.com/ProfRino/IFCtoFDS/releases/latest)
— a clean zip with no git history (recommended). All releases with
per-version download counts are listed on the
[Releases page](https://github.com/ProfRino/IFCtoFDS/releases). Unzip and
double-click `index.html`.

## Quick Start

### A. Hosted version (recommended)

Open **https://profrino.github.io/IFCtoFDS/** in any modern browser. Click
*Open IFC*, pick an `.ifc` file (or drag-drop one onto the page), choose an
**Opening approach** in the right-hand panel, then click **Convert to FDS**.
Use the save icon to download the generated `.fds`.

### B. Download a release ZIP and double-click

Grab the latest release as a single zip:

* **Latest release:** [IFCtoFDS-v0.1.0.zip](https://github.com/ProfRino/IFCtoFDS/releases/download/v0.1.0/IFCtoFDS-v0.1.0.zip)
* **Bleeding-edge `main`:** `git clone https://github.com/ProfRino/IFCtoFDS.git`

Unzip anywhere, then double-click `index.html`. The workbench runs straight
from `file://` — no local server needed. Use the *Open IFC* button to load a
model.

### C. Local web server

### C. Local web server with Verified IfcOpenShell backend (Recommended)

Serving the folder with the verified Python backend provides authoritative OpenCASCADE BRep booleans, MEP graph extraction, and 3-tier independent validation:

```powershell
pip install -e .
python -m ifc_to_fds serve --port 8000
```

Then open `http://127.0.0.1:8000/index.html`. The web interface will automatically detect the backend and enable **Verified Conversion (Audit)**.

### D. Verified CLI batch conversion and auditing

Run authoritative conversions directly from the command line:

```powershell
# 1. Complete element inventory check
ifc_to_fds inventory examples/AC20-FZK-Haus.ifc

# 2. Authoritative conversion with 3-tier validation audit
ifc_to_fds convert examples/AC20-FZK-Haus.ifc -o out/fzk.fds --cell-size 0.2

# 3. Storey-scoped conversion
ifc_to_fds convert examples/AC20-FZK-Haus.ifc -o out/erdg.fds --storey Erdgeschoss
```

Outputs produced:
- `.fds` simulation namelist with inlined `! IFC_SOURCE(...)` provenance
- `_manifest.json` and `_manifest.csv` bidirectional mapping records
- `_acceptance_report.md` and `_acceptance_report.json` with `VERIFIED` / `REJECTED` verdict

### E. Convert from Node.js (Legacy client-side engine)

The JavaScript client-side conversion pipeline also runs under Node for quick testing:

```powershell
node scripts/test-ifc-conversion.js
```

---

## Verified Architecture & Dual-Mode Engine

The repository implements a **dual-mode conversion pipeline**:

1. **Browser Client Workbench (`js/`)**:
   - Ultra-fast zero-install preview and interactive inspection.
   - Built-in opening carving and inverse coordinate transformations (`invertTransform()`).
   - Three view modes, walk-mode camera, and interactive clipping planes.
2. **Authoritative Python Engine (`ifc_to_fds/`)**:
   - **Canonical Intermediate Model**: Decoupled Pydantic v2 schemas (`CanonicalElement`, `CanonicalModel`).
   - **Watertight OpenCASCADE BRep Geometry**: Full boolean subtractions for door/window openings via `IfcOpenShell`.
   - **MEP & Fire Protection Graph**: Systems classification (`VENTILATION`, `SMOKE_EXTRACT`, `FIRE_SUPPRESSION`) and port topology.
   - **Spatial Scoping**: Storey and 3D bounding box filtering with vertical connectivity preservation.
   - **Independent 3-Tier Validation Engine**:
     - *Tier 1*: IFC source to Canonical inventory completeness & unit scale audit.
     - *Tier 2*: Canonical to FDS syntax and primitive traceability audit via independent regex parsing.
     - *Tier 3*: Effective geometry and opening retention audit with 3D IoU verification.
   - **Strict Acceptance Gating**: Automatic `VERIFIED` vs `REJECTED` verdict based on zero unmitigated P0/P1 defects.

---

## Bundled examples

The `examples/` folder ships with three open BIM models so the workbench can be
exercised end-to-end without any external download. See
[`examples/SOURCES.md`](examples/SOURCES.md) for original URLs and attribution.

| File | Source | License |
|---|---|---|
| [`AC20-FZK-Haus.ifc`](examples/AC20-FZK-Haus.ifc) | Karlsruhe Institute of Technology (KIT), distributed by [STEP Tools](https://steptools.com/docs/stpfiles/ifc/) | Freely available IFC test model |
| [`AC20-Institute-Var-2.ifc`](examples/AC20-Institute-Var-2.ifc) | Karlsruhe Institute of Technology (KIT), distributed by [STEP Tools](https://steptools.com/docs/stpfiles/ifc/) | Freely available IFC test model |
| [`IfcOpenShell-Duplex.ifc`](examples/IfcOpenShell-Duplex.ifc) | [IfcOpenShell voxelization toolkit](https://github.com/IfcOpenShell/voxelization_toolkit) | LGPL-3.0 |

## Repository layout

```text
index.html              Entry page, wires the browser workbench together
guide.html              Single-column docs page (linked from the ? icon)
css/                    app.css + guide.css
docs/                   Audit baseline, verified architecture, and risk register
ifc_to_fds/             Authoritative Python geometry & validation framework
  core/                 Canonical model, unit normalization, element inventory
  geometry/             IfcOpenShell OpenCASCADE engine, mesh manifoldness
  mep/                  MEP classifier and distribution systems graph
  mapping/              Spatial scoping, mapping policies, manifests, FDS serializer
  validation/           Metrics (IoU), strict acceptance gates, 3-tier validation audit
  cli.py                Command-line interface (convert, inventory, serve)
  server.py             FastAPI local service and web workbench mount
js/
  core/                 namespace + diagnostics
  ifc/                  IFC parser + meta builder + display loader
  fds/                  Namelist parser, geometry adapter, FDS exporter
  workers/              Background conversion worker + inline bundle
  viewer/               Three.js scene viewer
  vendor/               earcut.min.js
  compare/              Conversion sanity checks
  app-controller.js     UI wiring, conversion orchestration
tests/                  Automated test suite (pytest)
examples/               Three open IFC test models
scripts/                Node & Python test harness + bundle generators
demo/                   Demo video + sibling reference viewer
```

## Dependencies

CDN-loaded at runtime, no build pipeline:

* **[three.js](https://threejs.org/)** r128 — WebGL renderer, `OrbitControls`,
  `PointerLockControls`
* **[Mapbox earcut](https://github.com/mapbox/earcut)** — non-convex polygon
  triangulation (vendored at `js/vendor/earcut.min.js`, ISC licence at
  `js/vendor/EARCUT-LICENSE.txt`)
* **[Lucide](https://lucide.dev/)** icons

## License

**GNU Affero General Public License v3.0** — see [`LICENSE`](LICENSE).

In plain terms: you can use, study, and modify this software freely. **If you
integrate it into another product or run it as a network-accessible service,
you must release your entire derivative or service codebase under the same
AGPL-3.0 licence.** This is a deliberate choice to keep the tool open for the
research community while preventing closed commercial integration. Commercial
use is not forbidden, but it can only happen under AGPL terms.

## Citation

If you reference this work, please cite:

> Lovreglio, R. *IFCtoFDS*. Massey University.
> https://github.com/ProfRino/IFCtoFDS
