"""Unit tests for BFS connected components and adjacency list conversion."""

from __future__ import annotations

import pytest

from ds.bfs import bfs_connected_components, edges_to_adj_list
from math_engine.adjacency import build_adjacency_matrix
from math_engine.eigenvalues import compute_eigenvalues
from math_engine.laplacian import build_laplacian


# ---------------------------------------------------------------------------
# edges_to_adj_list tests
# ---------------------------------------------------------------------------


def test_edges_to_adj_list_normal_and_deduplication():
    """Verify undirected sorted adjacency lists, deduplication, and self-loop removal."""
    adj = edges_to_adj_list(
        4,
        [
            (2, 0),
            (0, 1),
            (0, 2),  # duplicate reversed edge
            (1, 1),  # self-loop ignored
        ],
    )
    assert adj == {
        0: [1, 2],
        1: [0],
        2: [0],
        3: [],  # isolated node still present
    }


def test_edges_to_adj_list_edge_and_error_cases():
    """Test n=0, n=1, negative n, out-of-bounds, and malformed edges."""
    assert edges_to_adj_list(0, []) == {}
    assert edges_to_adj_list(1, [(0, 0)]) == {0: []}

    with pytest.raises(ValueError):
        edges_to_adj_list(-1, [])

    with pytest.raises(ValueError):
        edges_to_adj_list(3, [(0, 3)])

    with pytest.raises(ValueError):
        edges_to_adj_list(3, [(0,)])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# bfs_connected_components tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,edges",
    [
        (2, [(0, 1)]),  # two-node connected (K2)
        (5, [(0, 1), (1, 2), (2, 3), (3, 4)]),  # path P5
        (5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]),  # cycle C5
        (4, [(i, j) for i in range(4) for j in range(i + 1, 4)]),  # complete K4
        (5, [(0, 1), (0, 2), (0, 3), (0, 4)]),  # star S5
    ],
)
def test_bfs_connected_graphs_single_component(n, edges):
    """Connected path, cycle, complete, star, and K2 graphs yield 1 component."""
    adj_list = edges_to_adj_list(n, edges)
    res = bfs_connected_components(n, adj_list)
    assert res["component_count"] == 1
    assert res["components"] == [list(range(n))]
    assert res["component_map"] == {i: 0 for i in range(n)}


def test_bfs_disconnected_and_isolated_nodes():
    """Verify exact component partitioning on disconnected and isolated-node graphs."""
    # Two disjoint triangles: K3 + K3
    edges_2k3 = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)]
    res_2k3 = bfs_connected_components(6, edges_to_adj_list(6, edges_2k3))
    assert res_2k3["component_count"] == 2
    assert res_2k3["components"] == [[0, 1, 2], [3, 4, 5]]
    assert res_2k3["component_map"] == {0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1}

    # Path P3 (0-1-2) with isolated nodes 3 and 4
    edges_iso = [(0, 1), (1, 2)]
    res_iso = bfs_connected_components(5, edges_to_adj_list(5, edges_iso))
    assert res_iso["component_count"] == 3
    assert res_iso["components"] == [[0, 1, 2], [3], [4]]
    assert res_iso["component_map"] == {0: 0, 1: 0, 2: 0, 3: 1, 4: 2}

    # All isolated nodes (edgeless graph on 4 nodes)
    res_edgeless = bfs_connected_components(4, edges_to_adj_list(4, []))
    assert res_edgeless["component_count"] == 4
    assert res_edgeless["components"] == [[0], [1], [2], [3]]


def test_bfs_edge_cases_empty_single_and_invalid():
    """Empty graph yields 0 components, single node yields 1 component, negative n fails."""
    res_empty = bfs_connected_components(0, {})
    assert res_empty == {"component_count": 0, "components": [], "component_map": {}}

    res_single = bfs_connected_components(1, {0: []})
    assert res_single == {"component_count": 1, "components": [[0]], "component_map": {0: 0}}

    with pytest.raises(ValueError):
        bfs_connected_components(-2, {})


@pytest.mark.parametrize(
    "n,edges,expected_count",
    [
        (0, [], 0),  # empty
        (1, [], 1),  # single-node
        (2, [(0, 1)], 1),  # two-node connected
        (4, [(0, 1), (1, 2), (2, 3)], 1),  # path P4
        (4, [(0, 1), (1, 2), (2, 3), (3, 0)], 1),  # cycle C4
        (4, [(i, j) for i in range(4) for j in range(i + 1, 4)], 1),  # complete K4
        (5, [(0, 1), (0, 2), (0, 3), (0, 4)], 1),  # star S5
        (6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)], 2),  # disconnected 2xK3
        (5, [(0, 1), (1, 2)], 3),  # graph with isolated nodes 3, 4
    ],
)
def test_bfs_matches_spectral_component_count(n, edges, expected_count):
    """Cross-check BFS component count against expected count and spectral zero-eigenvalue count."""
    bfs_res = bfs_connected_components(n, edges_to_adj_list(n, edges))
    lap = build_laplacian(build_adjacency_matrix(n, edges))
    spectral_res = compute_eigenvalues(lap, method="auto")

    assert bfs_res["component_count"] == expected_count
    assert spectral_res["zero_eigenvalue_count"] == expected_count
    assert bfs_res["component_count"] == spectral_res["zero_eigenvalue_count"]
