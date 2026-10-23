"""Boundary fixture test cases and geometry definitions."""

__all__ = ["fixture_cases", "fixture_text"]


def fixture_cases():
    box = [1, 2, 1, 2, 1, 2]
    cases = {
        "inside": [box],
        "corner": [[0, 1, 0, 1, 0, 1]],
        "offgrid": [[1.04, 2.06, 1, 2, 1, 2]],
        "thin": [[1.01, 1.09, 1, 2, 1, 2]],
        "passage": [[0.4, 1, 1, 2, 1, 2], [1.4, 2, 1, 2, 1, 2]],
        "closed_passage": [[0.4, 1.04, 1, 2, 1, 2], [1.06, 2, 1, 2, 1, 2]],
        "rejected": [box],
    }
    for axis, name in enumerate(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")):
        bounds = box.copy()
        bounds[axis // 2 * 2 : axis // 2 * 2 + 2] = [0, 1] if axis % 2 == 0 else [3, 4]
        cases[name] = [bounds]
    return cases


def fixture_text(name, boxes):
    text = f"&HEAD CHID='fixture_{name}' /\n&MESH IJK=20,20,20,XB=0,4,0,4,0,4 /\n&TIME T_END=0 /\n"
    for i, bounds in enumerate(boxes):
        surf = ", SURF_ID='missing_surface'" if name == "rejected" else ""
        text += f"&OBST ID='box{i}',XB={','.join(map(str, bounds))}{surf} /\n"
    return text + "&TAIL /\n"
