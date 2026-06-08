"""Dependency graph utilities for connection-based computation ordering.

Provides functions to build adjacency lists, detect cycles via Tarjan's
algorithm, topologically sort acyclic graphs, and compute execution order
with algebraic-loop detection.
"""

from __future__ import annotations


def build_adjacency_list(
    connections: list[tuple[str, str]],
) -> dict[str, list[str]]:
    """Build a directed adjacency list from a list of (source, target) pairs.

    All nodes that appear in the connections are present as keys; sinks
    that never appear as a source get an empty list.
    """
    adjacency: dict[str, list[str]] = {}
    for source, target in connections:
        adjacency.setdefault(source, []).append(target)
        # Ensure target appears as a key even if it has no outgoing edges
        adjacency.setdefault(target, [])
    return adjacency


def find_strongly_connected_components(
    adjacency: dict[str, list[str]],
) -> list[set[str]]:
    """Find non-trivial strongly connected components (Tarjan's algorithm).

    Uses an iterative stack-based implementation to avoid Python recursion
    limits on large graphs.

    Trivial single-node SCCs that have *no* self-loop are excluded.
    Nodes with an explicit self-loop are included as ``{node}``.
    """
    index_counter = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()

    sccs: list[set[str]] = []

    for start_node in adjacency:
        if start_node in indices:
            continue

        # Explicit DFS stack: each entry is (node, children_iterator)
        dfs_stack: list[tuple[str, object]] = []

        # Initialise the start node
        indices[start_node] = index_counter
        lowlinks[start_node] = index_counter
        index_counter += 1
        stack.append(start_node)
        on_stack.add(start_node)
        dfs_stack.append((start_node, iter(adjacency.get(start_node, []))))

        while dfs_stack:
            v, children = dfs_stack[-1]

            # Try to consume the next child
            try:
                w = next(children)  # type: ignore[arg-type]
            except StopIteration:
                # All children processed — pop and finalise
                dfs_stack.pop()
                if dfs_stack:
                    parent_v, _ = dfs_stack[-1]
                    lowlinks[parent_v] = min(
                        lowlinks[parent_v], lowlinks[v]
                    )

                # Check if v is the root of an SCC
                if lowlinks[v] == indices[v]:
                    scc: set[str] = set()
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        scc.add(w)
                        if w == v:
                            break
                    # Exclude trivial single nodes without a self-loop
                    if len(scc) > 1 or v in adjacency.get(v, []):
                        sccs.append(scc)
                continue

            # Process child *w*
            if w not in indices:
                # First visit to w
                indices[w] = index_counter
                lowlinks[w] = index_counter
                index_counter += 1
                stack.append(w)
                on_stack.add(w)
                dfs_stack.append((w, iter(adjacency.get(w, []))))
            elif w in on_stack:
                # w is a back-edge target
                lowlinks[v] = min(lowlinks[v], indices[w])

    return sccs


def topological_sort(adjacency: dict[str, list[str]]) -> list[str]:
    """Return a topological ordering of the graph (Kahn's algorithm).

    Raises ``ValueError`` if the graph contains a cycle.
    """
    in_degree: dict[str, int] = {node: 0 for node in adjacency}
    for source in adjacency:
        for target in adjacency[source]:
            in_degree[target] = in_degree.get(target, 0) + 1

    queue: list[str] = [
        node for node, degree in in_degree.items() if degree == 0
    ]
    # Use a pointer-based queue for O(1) pops
    idx = 0
    order: list[str] = []

    while idx < len(queue):
        node = queue[idx]
        idx += 1
        order.append(node)
        for neighbour in adjacency.get(node, []):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(adjacency):
        raise ValueError("Graph contains a cycle")

    return order


def compute_execution_order(
    connections: list[tuple[str, str]],
) -> tuple[list[str], list[set[str]]]:
    """Compute execution order and algebraic loops from connection pairs.

    Returns
    -------
    execution_order : list[str]
        Nodes that are not part of any algebraic loop, in topological order.
    algebraic_loops : list[set[str]]
        Strongly connected components (algebraic loops). Only non-trivial
        SCCs and self-loops are included.
    """
    adjacency = build_adjacency_list(connections)
    sccs = find_strongly_connected_components(adjacency)

    # Collect all nodes that belong to any SCC
    in_scc: set[str] = set()
    for scc in sccs:
        in_scc.update(scc)

    # Build condensation DAG from non-SCC nodes
    dag: dict[str, list[str]] = {}
    for node in adjacency:
        if node not in in_scc:
            dag[node] = [
                t for t in adjacency[node] if t not in in_scc
            ]

    execution_order: list[str] = []
    if dag:
        execution_order = topological_sort(dag)

    return execution_order, sccs