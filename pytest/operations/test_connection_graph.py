"""Tests for dependency graph utilities in connection_graph.py."""

from __future__ import annotations

import pytest

from pyssp_standard.standard.operations.connection_graph import (
    build_adjacency_list,
    compute_execution_order,
    find_strongly_connected_components,
    topological_sort,
)


class TestBuildAdjacencyList:
    def test_build_adjacency_list(self) -> None:
        connections = [("a", "b"), ("b", "c")]
        result = build_adjacency_list(connections)
        assert result == {"a": ["b"], "b": ["c"], "c": []}

    def test_empty_graph(self) -> None:
        assert build_adjacency_list([]) == {}

    def test_sink_only(self) -> None:
        connections = [("a", "b")]
        result = build_adjacency_list(connections)
        assert result == {"a": ["b"], "b": []}

    def test_multiple_edges_from_same_source(self) -> None:
        connections = [("a", "b"), ("a", "c")]
        result = build_adjacency_list(connections)
        assert result == {"a": ["b", "c"], "b": [], "c": []}


class TestFindSCC:
    def test_no_cycles(self) -> None:
        adj = {"a": ["b"], "b": ["c"], "c": []}
        assert find_strongly_connected_components(adj) == []

    def test_simple_cycle(self) -> None:
        adj = {"a": ["b"], "b": ["a"]}
        sccs = find_strongly_connected_components(adj)
        assert len(sccs) == 1
        assert sccs[0] == {"a", "b"}

    def test_self_loop(self) -> None:
        adj = {"a": ["a"]}
        sccs = find_strongly_connected_components(adj)
        assert len(sccs) == 1
        assert sccs[0] == {"a"}

    def test_two_disjoint_cycles(self) -> None:
        adj = {"a": ["b"], "b": ["a"], "c": ["d"], "d": ["c"], "e": []}
        sccs = find_strongly_connected_components(adj)
        assert len(sccs) == 2
        # Order is not guaranteed, so check set membership
        scc_sets = {frozenset(s) for s in sccs}
        assert frozenset({"a", "b"}) in scc_sets
        assert frozenset({"c", "d"}) in scc_sets

    def test_self_loop_excluded_in_trivial_scc(self) -> None:
        """A single node without self-loop should NOT produce an SCC."""
        adj = {"a": ["b"], "b": ["c"], "c": []}
        sccs = find_strongly_connected_components(adj)
        # No cycles means no SCCs (self-loop is only on 'a' if 'a' -> 'a')
        all_scc_nodes = set().union(*sccs) if sccs else set()
        for node in adj:
            assert node not in all_scc_nodes


class TestTopologicalSort:
    def test_dag(self) -> None:
        adj = {"a": ["b"], "b": ["c"], "c": []}
        result = topological_sort(adj)
        assert result == ["a", "b", "c"]

    def test_cycle_raises(self) -> None:
        adj = {"a": ["b"], "b": ["a"]}
        with pytest.raises(ValueError, match="cycle"):
            topological_sort(adj)

    def test_self_loop_raises(self) -> None:
        adj = {"a": ["a"]}
        with pytest.raises(ValueError, match="cycle"):
            topological_sort(adj)

    def test_disconnected_dag(self) -> None:
        adj = {"a": [], "b": ["c"], "c": []}
        result = topological_sort(adj)
        # a has no deps and b has no deps, order among independent nodes
        assert set(result) == {"a", "b", "c"}
        # b must come before c
        assert result.index("b") < result.index("c")

    def test_single_node(self) -> None:
        adj = {"a": []}
        assert topological_sort(adj) == ["a"]


class TestComputeExecutionOrder:
    def test_acyclic(self) -> None:
        order, loops = compute_execution_order([("a", "b"), ("b", "c")])
        assert loops == []
        assert order == ["a", "b", "c"]

    def test_with_cycles(self) -> None:
        # a -> b -> a is an algebraic loop; c -> d is acyclic
        order, loops = compute_execution_order(
            [("a", "b"), ("b", "a"), ("c", "d")]
        )
        assert len(loops) == 1
        assert loops[0] == {"a", "b"}
        assert order == ["c", "d"]

    def test_empty_graph(self) -> None:
        order, loops = compute_execution_order([])
        assert order == []
        assert loops == []

    def test_self_loop_in_loops_not_in_order(self) -> None:
        order, loops = compute_execution_order([("a", "a"), ("a", "b")])
        assert len(loops) == 1
        assert loops[0] == {"a"}
        assert order == ["b"]

    def test_multiple_cycles(self) -> None:
        order, loops = compute_execution_order(
            [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")]
        )
        assert len(loops) == 2
        assert order == []