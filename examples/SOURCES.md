# Building IFC Sources

The browser workbench bundles complete building models in `examples/`.

## KIT Buildings

`AC20-FZK-Haus.ifc` and `AC20-Institute-Var-2.ifc` are IFC4 building examples
from Karlsruhe Institute of Technology (KIT), distributed by STEP Tools:

- https://steptools.com/docs/stpfiles/ifc/AC20-FZK-Haus.ifc
- https://steptools.com/docs/stpfiles/ifc/AC20-Institute-Var-2.ifc
- https://steptools.com/docs/stpfiles/ifc/index.html

## Duplex Building

`IfcOpenShell-Duplex.ifc` is the complete duplex model used by the IfcOpenShell
voxelization toolkit tutorial:

- https://github.com/IfcOpenShell/voxelization_toolkit
- https://github.com/IfcOpenShell/voxelization_toolkit/blob/e9ce7e0c5569da67c9953bcd4e6496b5ce1c3699/tests/fixtures/duplex.ifc

## Authored MEP/PCCC geometry fixture

`mep-fire-geometry.ifc` is a synthetic IFC4 regression fixture authored for this
repository using IfcOpenShell. It includes actual swept solids and explicit
systems/ports; it is not surveyed building data or a functional fire model.
See [fixture scope and generation](mep-fire-geometry.md).
