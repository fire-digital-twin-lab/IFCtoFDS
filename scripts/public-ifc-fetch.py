"""Download a fixed selection of public IFC test files, outside the repository, and record where each came from.

    python -I scripts/public-ifc-fetch.py --root <dir> [--groups bsi,whale,ifcos,tuwien,community] [--max-mb 80]

Nothing downloaded is ever executed or imported. Each source gets its own sub-directory under --root and every file must
start with a STEP header, otherwise it is discarded (some hosts answer with an HTML page or a Git LFS pointer). The url,
size, sha256 and licence note of each file go to <root>/manifest.json. Run it with `python -I` from a directory that does
not contain downloaded data. The files are public test data and must not be committed; keep them out of the repository.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request

UA = "public-ifc-fetch/1.0"
GITHUB_API = "https://api.github.com/repos/{repo}"


def is_inside(path, base):
    """True when path is base or below it; paths on different drives are never inside."""
    path, base = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(base))
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:  # different drives on Windows
        return False


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as response:
        return json.load(response)


def ifc_tree(repo):
    """{path: size} of every .ifc file of a public GitHub repository."""
    tree = get_json(GITHUB_API.format(repo=repo) + "/git/trees/HEAD?recursive=1")["tree"]
    return {t["path"]: t.get("size", 0) for t in tree if t["path"].lower().endswith(".ifc")}


def quote(path):
    return urllib.parse.quote(path, safe="/()")


def raw(repo, path):
    return f"https://raw.githubusercontent.com/{repo}/HEAD/{quote(path)}"


def selection(groups):
    """(group, file name, url, licence note) for every file to download."""
    items = []
    if "bsi" in groups:  # buildingSMART: three schemas x building disciplines, a few infrastructure files, ISO reference view
        repo = "buildingSMART/Sample-Test-Files"
        for path in sorted(ifc_tree(repo)):
            base = os.path.basename(path)
            if base.startswith("Building-") or "ReferenceView" in path or base in ("Infra-Road.ifc", "Infra-Bridge.ifc", "Infra-Rail.ifc", "Infra-Plumbing.ifc"):
                schema = re.search(r"\((IFC [^)]*)\)", path).group(1).replace(" ", "").replace(".", "")
                items.append(("bsi", f"{schema}__{'ISO-' if 'ReferenceView' in path else ''}{base}", raw(repo, path), "buildingSMART Sample-Test-Files (no licence asserted)"))
    if "whale" in groups:  # bim-whale samples, MIT
        for path in ("SimpleWall/IFC/SimpleWall.ifc", "ManySimpleWalls/IFC/ManySimpleWalls.ifc", "TallBuilding/IFC/TallBuilding.ifc",
                     "LargeBuilding/IFC/LargeBuilding.ifc", "BasicHouse/IFC/BasicHouse.ifc", "AdvancedProject/IFC/AdvancedProject.ifc"):
            items.append(("whale", os.path.basename(path), raw("andrewisen/bim-whale-ifc-samples", path), "MIT"))
    if "ifcos" in groups:  # IfcOpenShell/files: reproductions of native crashes, hangs and wrong geometry, plus a few real files
        repo = "IfcOpenShell/files"
        sizes = ifc_tree(repo)
        chosen = [p for p, s in sizes.items() if 400_000 <= s <= 14_000_000]
        small = sorted(p for p, s in sizes.items() if s < 400_000 and re.search(r"segfault|abort|missingSubtraction|wrong-geometry|infinite", p))
        chosen += random.Random(7).sample(small, min(14, len(small)))
        chosen += [p for p in sizes if p.startswith("acad2010") or p.startswith("encoding") or p == "nested_mapped_item.ifc"]
        for path in sorted(set(chosen)):
            items.append(("ifcos", path, raw(repo, path), "IfcOpenShell/files (no licence file)"))
    if "tuwien" in groups:  # fictional escape-route test building with an underground garage, CC BY 4.0
        items.append(("tuwien", "Custom-Escape-Route-Test-Model-ZDB.ifc",
                      "https://researchdata.tuwien.ac.at/records/ra5g9-tbb65/files/Custom-Escape-Route-Test-Model-ZDB.ifc?download=1", "CC BY 4.0"))
    if "community" in groups:  # stored with Git LFS: the real bytes come from media.githubusercontent.com
        repo = "buildingsmart-community/Community-Sample-Test-Files"
        branch = get_json(GITHUB_API.format(repo=repo))["default_branch"]
        for path in ("IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment/Duplex_A_20110907.ifc", "IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment/Duplex_MEP_20110907.ifc",
                     "IFC 2.3.0.1 (IFC 2x3)/Medical-Dental Clinic/Clinic_Architectural.ifc", "IFC 2.3.0.1 (IFC 2x3)/Medical-Dental Clinic/Clinic_HVAC.ifc",
                     "IFC 2.3.0.1 (IFC 2x3)/Esplanades/1807_EP_AR_v18.ifc", "IFC 2.3.0.1 (IFC 2x3)/Molio/Molio_with_URIs.ifc",
                     "IFC 4.0.2.1 (IFC 4)/Example project location/example project location.ifc",
                     "IFC 4.3.2.0 (IFC 4.3)/Chesapeake Bay Bridge-Tunnel IFC Model/chesapeake_bay_bridge_tunnel_4x3.ifc",
                     "IFC 2.3.0.1 (IFC 2x3)/Schependomlaan/As Planned models/IFC Schependomlaan incl planningsdata.ifc"):
            items.append(("community", os.path.basename(path), f"https://media.githubusercontent.com/media/{repo}/{branch}/{quote(path)}", "buildingsmart-community (no licence file)"))
    return items


def download(url, destination, max_bytes):
    part = destination + ".part"
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    total = 0
    with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as out:
        while chunk := response.read(1 << 20):
            total += len(chunk)
            if total > max_bytes:
                out.close()
                os.remove(part)
                raise ValueError(f"larger than {max_bytes >> 20} MB")
            out.write(chunk)
    with open(part, "rb") as handle:
        if b"ISO-10303-21" not in handle.read(400):
            os.remove(part)
            raise ValueError(f"not a STEP file ({total} bytes: an HTML page or a Git LFS pointer)")
    os.replace(part, destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="directory that receives one sub-directory per source (outside the repository)")
    parser.add_argument("--groups", default="bsi,whale,ifcos,tuwien,community")
    parser.add_argument("--max-mb", type=int, default=80, help="skip files larger than this")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if is_inside(root, repo_root):
        sys.exit("--root must be outside the repository: real and public IFC data are not committed")
    os.makedirs(root, exist_ok=True)
    manifest_path = os.path.join(root, "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8")) if os.path.exists(manifest_path) else {}
    done = failed = 0
    for group, name, url, licence in selection(set(args.groups.split(","))):
        key = f"{group}/{name}"
        destination = os.path.join(root, group, name)
        if key in manifest and os.path.exists(destination):
            continue
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        try:
            download(url, destination, args.max_mb << 20)
        except (OSError, ValueError) as exc:  # urllib errors are OSError subclasses
            print(f"FAIL  {key}: {str(exc)[:110]}", flush=True)
            failed += 1
            continue
        with open(destination, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        manifest[key] = dict(url=url, bytes=os.path.getsize(destination), sha256=digest, licence=licence)
        done += 1
        print(f"ok    {key}  {manifest[key]['bytes'] / 1048576:.2f} MB", flush=True)
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=1, ensure_ascii=False)
    print(f"DONE downloaded {done}, failed {failed}, manifest entries {len(manifest)}")


if __name__ == "__main__":
    main()
