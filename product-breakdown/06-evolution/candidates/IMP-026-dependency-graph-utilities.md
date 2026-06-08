# IMP-026: Add dependency graph utilities for FMU connection analysis

> **Status:** Proposed
> **Priority:** Medium
> **Layer:** Operations (primary)

## Theme

New operations layer for FMU connectivity graphs: SCC detection, topological sort, execution order computation, using pure Python adjacency-list representation.

## Evidence

### No graph code exists

Confirmed by inspecting `pyssp_standard/standard/operations/` — it contains only `model_description_to_ssd.py` and `__init__.py`. No graph algorithm code exists anywhere in the codebase.

`pyssp_standard/standard/operations/__init__.py`:
```python
"""Operations that compose standard-domain models that cross standards."""
```

### Connection data exists in SSP module

`Ssd1Connector`, connection handling, and parameter bindings exist in `ssd_model.py` / `ssd_codec.py`, but these are data structures for XML representation, not graph analysis.

### ALIGN-001 assessment

Section F12 identified:

> **Gap Assessment:** Full gap. This is a new feature requiring:
> 1. A graph representation of FMU connections (can build from existing `Ssd1System` connector/connection data)
> 2. Tarjan's or Kosaraju's algorithm for SCC detection (algebraic loops)
> 3. Topological sort for execution order
> 4. Tests with known loop/non-loop configurations

**Recommendation:** Proceed as a new candidate. Scope is well-defined:
- `pyssp_standard/standard/operations/connection_graph.py` (cross-standard, since connections apply to both SSP1 and SSP2)
- Pure functions over connection lists
- No external graph library needed

## Current Pain Or Risk

1. **No way to detect algebraic loops** — SSP connection diagrams may contain cyclic dependencies (algebraic loops). The codebase has no tool to detect or report these.
2. **No execution order computation** — Given a set of FMU connections, there is no way to compute a valid execution order (topological sort).
3. **No graph abstraction** — Callers who need to analyze FMU connectivity must build their own graph from scratch.
4. **Testability gap** — Tools like cs-fmu-packager that need to analyze connection topologies have no shared infrastructure.

## Proposed Improvement

### New module: `pyssp_standard/standard/operations/connection_graph.py`

Pure functions over connection lists using an adjacency-list representation:

```python
def build_adjacency_list(
    connections: list[tuple[str, str]]
) -> dict[str, list[str]]:
    """Build adjacency list from a list of (source, target) pairs."""
    ...

def find_strongly_connected_components(
    adjacency: dict[str, list[str]]
) -> list[set[str]]:
    """Return SCCs using Tarjan's algorithm.

    Each SCC is a set of node names. Single-node SCCs with no
    self-loop are not included (they are trivially acyclic).
    """
    ...

def topological_sort(
    adjacency: dict[str, list[str]]
) -> list[str]:
    """Return a topological ordering of nodes.

    Raises ValueError if the graph contains cycles.
    """
    ...

def compute_execution_order(
    connections: list[tuple[str, str]]
) -> tuple[list[str], list[set[str]]]:
    """Return (execution_order, algebraic_loops).

    Convenience wrapper: builds adjacency, finds SCCs, applies
    topological sort to the condensation DAG.
    """
    ...
```

### Function-oriented, not class-oriented

The module uses standalone functions operating on basic Python types (`dict[str, list[str]]`, `list[tuple[str, str]]`). No class wrappers.

### No external graph library

Tarjan's SCC algorithm can be implemented in ~50 lines. Topological sort (Kahn's algorithm or DFS-based) in ~30 lines. Pure Python is sufficient for the expected scale (<10K connections).

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Graph representation | Adjacency list (`dict[str, list[str]]`) | Simple, standard, no object overhead |
| SCC algorithm | Tarjan's (DFS-based) | O(V+E), single pass, no separate transpose needed |
| Connection format | `list[tuple[str, str]]` — (source, target) pairs | Matches how SSP connections are naturally represented |
| Module placement | `standard/operations/connection_graph.py` | Cross-standard operations layer; SSP connections AND FMU-internal deps could use it |
| Cycle handling | `topological_sort` raises `ValueError`; `compute_execution_order` returns SCCs separately | Caller chooses strict (fail on cycle) or lenient (report cycles) |

## Expected Benefit

- **Algebraic loop detection** — `find_strongly_connected_components(connections)` finds cyclic dependencies
- **Execution order computation** — `compute_execution_order(connections)` returns a valid partial order
- **No dependency** — Pure Python, no `networkx` or similar
- **Reusable** — Can be used for SSP connection-level graphs and potentially FMU-internal dependency graphs

## Risk And Blast Radius

| Risk | Severity | Mitigation |
|------|----------|------------|
| Large graphs (>10K nodes) | Low | Pure Python adjacency list is fine for expected scale; explicit out-of-scope for >10K optimization |
| Recursion depth | Medium | Tarjan's uses recursion; Python default recursion limit (1000) could be hit for deep graphs. Use iterative stack or `sys.setrecursionlimit` |
| Misleading SCC output | Low | Single-node SCCs without self-loops are excluded by convention; documented in function docstring |

## Suggested Priority

**Medium** — Important capability for FMU connectivity analysis but no immediate blocker. Ecosystem value increases as more connection-based tools are built.

## Task Contract Seed

### Phase 1 — Core graph functions

1. Create `pyssp_standard/standard/operations/connection_graph.py`:
   - `build_adjacency_list(connections) -> dict[str, list[str]]`
   - `find_strongly_connected_components(adjacency) -> list[set[str]]` (Tarjan's algorithm)
   - `topological_sort(adjacency) -> list[str]` (Kahn's algorithm for DAGs)
   - `compute_execution_order(connections) -> tuple[list[str], list[set[str]]]`

### Phase 2 — Tests

2. Create `pytest/operations/test_connection_graph.py`:

   | Test | Purpose |
   |------|---------|
   | `test_build_adjacency_list` | Simple (a→b, b→c) → `{a: [b], b: [c], c: []}` |
   | `test_find_scc_no_cycles` | No cycles → empty SCC list |
   | `test_find_scc_simple_cycle` | a→b→a → [{a, b}] |
   | `test_find_scc_self_loop` | a→a → [{a}] |
   | `test_find_scc_two_cycles` | Disjoint cycles → both detected |
   | `test_topological_sort_dag` | a→b→c → [a, b, c] |
   | `test_topological_sort_cycle_raises` | a→b→a → ValueError |
   | `test_compute_execution_order_acyclic` | No SCCs → ordered list, empty SCCs |
   | `test_compute_execution_order_with_cycles` | SCCs reported separately from ordered nodes |
   | `test_empty_graph` | No connections → empty order, empty SCCs |

### Phase 3 — Integration

3. Verify graph functions work with actual SSP connection data (parse `Ssd1System` connections → extract (source, target) pairs → feed to graph functions).

## Out Of Scope

- **FMU-internal dependency graphs** — `modelStructure` dependencies within an FMU. The graph operates on SSP-level component connections, not FMU-internal variable dependencies.
- **Visualization** — No graphviz, matplotlib, or any visualization output.
- **Performance optimization for >10K connections** — Pure Python adjacency list is sufficient for typical SSP scale.
- **SSP2 connection model** — Add when SSP2 codec is implemented; the graph functions are connection-format agnostic.

## Traceability

- **Intent:** ALIGN-001 F12 — Dependency graph utilities for FMU connectivity analysis.
- **Product:** `pyssp_standard/standard/operations/connection_graph.py` with 4 pure functions.
- **Architecture:** Operations layer (cross-standard).
- **Implementation:** New module, no changes to existing code.
- **Verification:** Tests with known loop/non-loop connection sets.

## Notes

- The graph functions operate on string node names (component identifiers), not on model objects. This keeps the module dependency-free and testable.
- Tarjan's algorithm uses a lowlink approach. Ensure the implementation handles the recursion depth concern by using an iterative stack variant if needed.
- The `compute_execution_order` wrapper returns SCCs separately so callers can decide whether to fail or proceed with warnings on cycle detection.