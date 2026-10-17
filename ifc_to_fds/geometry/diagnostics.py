"""Reproducible host/opening inspection; never substitutes an uncut host."""

from time import perf_counter
import ifcopenshell
import ifcopenshell.geom

from ifc_to_fds.core.inventory import compute_file_sha256
from ifc_to_fds.core.placement import extract_placement
from ifc_to_fds.core.units import get_length_unit_scale
from ifc_to_fds.domain.bim import TriangleMesh
from .engine import create_geom_settings
from .mesh import as_trimesh, inspect_mesh_quality, valid_solid
from ifc_to_fds.validation.metrics import opening_residual


def inspect_host_openings(source_path, host_step):
    started = perf_counter()
    source = ifcopenshell.open(str(source_path))
    host = source.by_id(host_step)
    _, scale = get_length_unit_scale(source)
    errors = []
    source_hash = compute_file_sha256(source_path)

    def identity(product):
        return dict(entity_key=f"{source_hash}:{product.id()}", step_id=product.id(),
                    global_id=product.GlobalId, ifc_type=product.is_a())

    def read(product, subtract=True):
        settings = create_geom_settings()
        settings.set("disable-opening-subtractions", not subtract)
        try:
            shape = ifcopenshell.geom.create_shape(settings, product)
            g = shape.geometry  # retain shape until both arrays are copied
            mesh = TriangleMesh(
                vertices=[list(g.verts[i:i+3]) for i in range(0, len(g.verts), 3)],
                faces=[list(g.faces[i:i+3]) for i in range(0, len(g.faces), 3)],
            )
            if not valid_solid(mesh):
                errors.append(dict(**identity(product), stage="IFC_GEOMETRY", name="UnsupportedSolid",
                                   message=str(inspect_mesh_quality(mesh)), subtract=subtract))
            return mesh
        except Exception as exc:
            errors.append(dict(**identity(product), stage="IFC_GEOMETRY",
                               name=type(exc).__name__, message=str(exc), subtract=subtract))
            return None

    def describe(product):
        items = []
        for rep in getattr(getattr(product, "Representation", None), "Representations", ()):
            for item in rep.Items:
                profile = getattr(item, "SweptArea", None)
                items.append(dict(step_id=item.id(), type=item.is_a(), source=str(item),
                                  profile=str(profile),
                                  profile_type=profile.is_a() if profile else None,
                                  inner_curves=len(getattr(profile, "InnerCurves", ())),
                                  curve_sources=[str(x) for x in source.traverse(profile)] if profile else []))
        return dict(**identity(product), name=product.Name,
                    placement=extract_placement(product, scale), representation_items=items)

    def metrics(mesh):
        if mesh is None:
            return dict(status="UNSUPPORTED")
        tm = as_trimesh(mesh)
        return dict(vertices=len(mesh.vertices), faces=len(mesh.faces),
                    quality=inspect_mesh_quality(mesh), bounds=tm.bounds.tolist(), volume_m3=float(tm.volume))

    def residual(mesh, opening):
        try:
            return dict(status="MEASURED", value=opening_residual([mesh], opening))
        except Exception as exc:
            return dict(status="INCONCLUSIVE", reason=str(exc))

    cut, uncut = read(host), read(host, False)
    openings = []
    for relation in getattr(host, "HasOpenings", ()):
        opening = relation.RelatedOpeningElement
        mesh = read(opening)
        openings.append(dict(**describe(opening), void_relation_step_id=relation.id(),
                             fillings=[r.RelatedBuildingElement.id() for r in opening.HasFillings],
                             mesh=metrics(mesh), source_residual=residual(cut, mesh),
                             material_overlap_before_relational_subtraction=residual(uncut, mesh)))
    return dict(source_sha256=source_hash, engine=ifcopenshell.version, unit_scale=scale,
                host=describe(host), with_relational_openings=metrics(cut),
                without_relational_openings=metrics(uncut), openings=openings, errors=errors,
                elapsed_s=perf_counter()-started,
                decision="DIAGNOSTIC_ONLY; no uncut substitution or source repair authorized")
