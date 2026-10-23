import pytest

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.mapping.exporter import compute_mesh_grid


@pytest.mark.parametrize("thin_axis", range(3))
def test_generated_3d_mesh_has_no_one_or_two_cell_direction(thin_axis):
    lengths = [2.0, 2.0, 2.0]
    lengths[thin_axis] = 0.1
    bounds = BoundingBox(
        xmin=0, xmax=lengths[0], ymin=0, ymax=lengths[1], zmin=0, zmax=lengths[2]
    )
    ijk, xb = compute_mesh_grid(bounds, cell_size=0.2)
    assert min(ijk) >= 3
    assert xb == bounds.to_xb(), "Grid refinement must not move the declared domain"
