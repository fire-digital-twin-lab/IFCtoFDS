"""Binary64 solid operations; never quantize audit coordinates to float32."""

import numpy as np
import trimesh


def solid_boolean(meshes, operation):
    import manifold3d

    if not hasattr(manifold3d, "Mesh64"):
        raise RuntimeError("Binary64 Manifold backend unavailable; no float32 fallback")
    operands = []
    for mesh in meshes:
        if not mesh.is_volume:
            raise ValueError("Boolean operand is not a valid oriented volume")
        operand = manifold3d.Manifold(
            manifold3d.Mesh64(
                vert_properties=np.array(
                    mesh.vertices, dtype=np.float64, order="C", copy=True
                ),
                tri_verts=np.array(mesh.faces, dtype=np.uint64, order="C", copy=True),
            )
        )
        if operand.status() != manifold3d.Error.NoError:
            raise RuntimeError(f"Manifold rejected operand: {operand.status()}")
        operands.append(operand)
    operators = {
        "intersection": manifold3d.OpType.Intersect,
        "union": manifold3d.OpType.Add,
        "difference": manifold3d.OpType.Subtract,
    }
    result = manifold3d.Manifold.batch_boolean(operands, operators[operation])
    if result.status() != manifold3d.Error.NoError:
        raise RuntimeError(f"Manifold Boolean failed: {result.status()}")
    output = result.to_mesh64()
    return trimesh.Trimesh(
        vertices=output.vert_properties[:, :3], faces=output.tri_verts, process=False
    )
