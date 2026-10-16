# 08 — Validation Architecture: Independent Gate Checkers

## 1. Modular Validation Pipeline
Rather than executing all validation in a monolithic multi-hundred-line procedure, the validation suite decomposes into single-responsibility checkers:

```text
ValidationContext
       │
       ├──> SourceCoverageChecker        (verifies IFC sources and entity accounting)
       ├──> ScopeChecker                 (verifies spatial inclusion / exclusion boundaries)
       ├──> GeometryChecker              (audits topology, degenerate faces, bounds)
       ├──> OpeningChecker               (measures void subtraction and residual passages)
       ├──> MEPChecker                   (audits system connectivity and port alignment)
       ├──> ProvenanceChecker            (verifies bidirectional IFC-FDS entity keys)
       ├──> BoundaryChecker              (audits cross-boundary elements and solver proofs)
       ├──> FdsSyntaxChecker             (validates FDS namelist grammar and face indices)
       ├──> SolverChecker                (verifies FDS execution when solver is present)
       └──> GoldenParityChecker          (evaluates parity against approved reference cases)
       │
       ▼
GateResult[]
       │
       ▼
AcceptanceEvaluator ──> Immutable AcceptanceReport
```

## 2. Checker Contract
Every checker implements the same protocol:
```python
class GateChecker(Protocol):
    def run(self, context: ValidationContext) -> GateResult:
        ...
```

## 3. Immutability
Checkers **never mutate** the `AcceptanceReport` or append thousands of characters into `gate.reason`. Details belong in `findings`, `metrics`, and `evidence`. Once evaluated, `AcceptanceReport` is immutable.
