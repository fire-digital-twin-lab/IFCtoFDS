"""Small FDS cases whose expected solver/effective outcomes are explicit."""


def solver_cases():
    head = "&HEAD CHID='acceptance' /\n&TIME T_END=0 /\n"
    mesh = "&MESH ID='domain', IJK=20,10,10, XB=0,4,0,2,0,2 /\n"
    wall = "&OBST ID='wall', XB=1,3,0.2,1.8,0,2 /\n"
    tail = "&TAIL /\n"
    vertices = "1,0.4,0.4, 2,0.4,0.4, 2,1.4,0.4, 1,1.4,0.4, 1,0.4,1.4, 2,0.4,1.4, 2,1.4,1.4, 1,1.4,1.4"
    # Outward-oriented cube triangles, FDS vertex and surface indices are 1-based.
    faces = "1,3,2,1, 1,4,3,1, 5,6,7,1, 5,7,8,1, 1,2,6,1, 1,6,5,1, 2,3,7,1, 2,7,6,1, 3,4,8,1, 3,8,7,1, 4,1,5,1, 4,5,8,1"
    geom = f"&SURF ID='solid' /\n&GEOM ID='cube', SURF_ID='solid', VERTS={vertices}, FACES={faces} /\n"
    meshes = (
        "&MESH ID='left', IJK=10,10,10, XB=0,2,0,2,0,2 /\n"
        "&MESH ID='right', IJK=10,10,10, XB=2,4,0,2,0,2 /\n"
    )
    return {
        "obst": head + mesh + wall + tail,
        "geom": head + mesh + geom + tail,
        "hole": head
        + mesh
        + wall
        + "&HOLE ID='opening', XB=0.8,3.2,0.6,1.4,0,1.4 /\n"
        + tail,
        "vent": head
        + mesh
        + wall
        + "&VENT ID='outside', XB=0,0,0,2,0,2, SURF_ID='OPEN' /\n"
        + tail,
        "multi_mesh": head + meshes + wall + tail,
        "invalid_geom": head
        + mesh
        + geom.replace("FACES=1,3,2,1", "FACES=999,3,2,1")
        + tail,
    }
