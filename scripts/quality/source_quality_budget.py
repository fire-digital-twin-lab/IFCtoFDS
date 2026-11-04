"""R10-06: deterministic source debt inventory and non-regression budget.

The report deliberately distinguishes measured technical debt from verified
scientific correctness. Initial --report obtains the baseline; --baseline
fails if any metric grows beyond the approved snapshot. This does not
auto-waive new source files or error swallowing.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "ifc_to_fds"
METRICS = (
    "imports_in_functions",
    "broad_except",
    "bare_except",
    "silent_except",
)


class DebtVisitor(ast.NodeVisitor):
    """Count syntactic debt precisely, including imports nested in closures."""

    def __init__(self) -> None:
        self.function_depth = 0
        self.counts = {key: 0 for key in METRICS}

    def _visit_function(self, node: ast.AST) -> None:
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        if self.function_depth:
            self.counts["imports_in_functions"] += 1

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.function_depth:
            self.counts["imports_in_functions"] += 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.counts["bare_except"] += 1
        elif isinstance(node.type, ast.Name) and node.type.id in {
            "Exception", "BaseException"
        }:
            self.counts["broad_except"] += 1
        if node.body and all(
            isinstance(stmt, (ast.Pass, ast.Expr))
            and (
                isinstance(stmt, ast.Pass)
                or (
                    isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                )
            )
            for stmt in node.body
        ):
            self.counts["silent_except"] += 1
        self.generic_visit(node)


def inventory(root: Path = SOURCE) -> dict:
    """Return a reproducible, per-file technical-debt inventory."""
    files = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = DebtVisitor()
        visitor.visit(tree)
        rel = path.relative_to(root).as_posix()
        files[rel] = visitor.counts
    totals = {key: sum(values[key] for values in files.values()) for key in METRICS}
    return {"schema_version": 1, "files_scanned": len(files), "totals": totals, "files": files}


def compare_to_baseline(current: dict, baseline: dict) -> list[str]:
    """Reject budget growth; existing debt remains visible, not hidden."""
    if baseline.get("schema_version") != 1:
        raise ValueError("Unknown source debt baseline schema")
    errors = []
    old_totals = baseline.get("totals", {})
    for key in METRICS:
        allowed = old_totals.get(key)
        if not isinstance(allowed, int) or allowed < 0:
            raise ValueError(f"Missing valid baseline: {key}")
        if current["totals"][key] > allowed:
            errors.append(f"{key}: {current['totals'][key]} > baseline {allowed}")
    return errors



def compare_git_base(current: dict, root: Path, base: str) -> list[str]:
    """Fail newly introduced source debt, including increases in old files.

    Only Python paths whose HEAD content differs from the base are inspected.
    Each changed file has its own budget, so clean new files cannot pay for
    regressions elsewhere and old debt cannot mask new local error swallowing.
    """
    repo_root = root.parent
    command = [
        "git", "diff", "--name-only", "--diff-filter=ACMR",
        base, "HEAD", "--", root.name + "/",
    ]
    changed = subprocess.run(
        command, cwd=repo_root, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    errors = []
    for rel in sorted(changed):
        if not rel.endswith(".py"):
            continue
        source_path = repo_root / rel
        if not source_path.is_file():
            continue
        current_key = source_path.relative_to(root).as_posix()
        new_counts = current["files"][current_key]
        old_blob = subprocess.run(
            ["git", "show", f"{base}:{rel}"],
            cwd=repo_root, capture_output=True, check=False, text=True
        )
        if old_blob.returncode:
            old_counts = {metric: 0 for metric in METRICS}
        else:
            old_visitor = DebtVisitor()
            old_visitor.visit(ast.parse(old_blob.stdout, filename=f"{base}:{rel}"))
            old_counts = old_visitor.counts
        for metric in METRICS:
            if new_counts[metric] > old_counts[metric]:
                errors.append(
                    f"{rel}: {metric} increased "
                    f"{old_counts[metric]} -> {new_counts[metric]}"
                )
    return errors

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=SOURCE)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--git-base", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    current = inventory(args.root)
    rendered = json.dumps(current, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(
        "SOURCE_QUALITY_METRICS "
        + json.dumps(
            {"files_scanned": current["files_scanned"], **current["totals"]},
            sort_keys=True,
        ),
        flush=True,
    )
    if args.git_base:
        errors = compare_git_base(current, args.root, args.git_base)
        if errors:
            for error in errors:
                print("SOURCE_QUALITY_NEW_DEBT " + error, flush=True)
            return 1
        print("SOURCE_QUALITY_NO_NEW_DEBT", flush=True)
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        errors = compare_to_baseline(current, baseline)
        if errors:
            for error in errors:
                print("SOURCE_QUALITY_REGRESSION " + error, flush=True)
            return 1
        print("SOURCE_QUALITY_BUDGET_OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
