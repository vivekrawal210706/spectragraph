"""Unit tests for Union-Find (Disjoint Set Union) component detection."""

from __future__ import annotations

import pytest

from ds.bfs import bfs_connected_components, edges_to_adj_list
from ds.union_find import UnionFind, union_find_components
from math_engine.adjacency import build_adjacency_matrix
from math_engine.eigenvalues import compute_eigenvalues
from math_engine.laplacian import build_laplacian


# ---------------------------------------------------------------------------
# UnionFind class tests
# ---------------------------------------------------------------------------


def test_union_find_operations_and_redundant_unions():
    """Verify find, union, connected, component_count tracking, and redundant union False."""
    uf = UnionFind(5)
    assert uf.component_count == 5
    assert uf.connected(0, 1) is False
    assert uf.connected(2, 2) is True

    # First union succeeds and decrements component_count
    assert uf.union(0, 1) is True
    assert uf.component_count == 4
    assert uf.connected(0, 1) is True

    # Redundant self-union and already-connected union return False
    assert uf.union(0, 0) is False
    assert uf.union(0, 1) is False
    assert uf.union(1, 0) is False
    assert uf.component_count == 4

    # Merge another pair then link the two pairs
    assert uf.union(2, 3) is True
    assert uf.union(1, 3) is True
    assert uf.component_count == 2
    assert uf.connected(0, 2) is True
    assert uf.connected(0, 4) is False


def test_union_find_path_compression_and_get_components():
    """Path compression flattens parent pointers; get_components returns consistent structure."""
    uf = UnionFind(6)
    # Force a multi-level tree before path compression
    uf.union(0, 1)
    uf.union(2, 3)
    uf.union(0, 2)  # rank of root(0) becomes 2
    uf.union(4, 5)

    # Calling find on deeper nodes compresses paths directly to the root
    root_0123 = uf.find(3)
    assert uf.find(0) == root_0123
    assert uf.parent[3] == root_0123

    comps = uf.get_components()
    assert comps["component_count"] == 2
    assert comps["components"] == [[0, 1, 2, 3], [4, 5]]
    assert comps["component_map"] == {0: 0, 1: 0, 2: 0, 3: 0, 4: 1, 5: 1}


def test_union_find_edge_and_invalid_bounds():
    """Test n=0, n=1, negative n, and out-of-bounds node queries."""
    uf_empty = UnionFind(0)
    assert uf_empty.get_components() == {
        "component_count": 0,
        "components": [],
        "component_map": {},
    }

    uf_single = UnionFind(1)
    assert uf_single.find(0) == 0
    assert uf_single.get_components() == {
        "component_count": 1,
        "components": [[0]],
        "component_map": {0: 0},
    }

    with pytest.raises(ValueError):
        UnionFind(-1)

    uf = UnionFind(3)
    with pytest.raises(ValueError):
        uf.find(3)
    with pytest.raises(ValueError):
        uf.union(-1, 2)
    with pytest.raises(ValueError):
        uf.connected(0, 99)


# ---------------------------------------------------------------------------
# union_find_components tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n,edges",
    [
        (2, [(0, 1)]),  # K2
        (5, [(0, 1), (1, 2), (2, 3), (3, 4)]),  # path P5
        (5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]),  # cycle C5
        (4, [(i, j) for i in range(4) for j in range(i + 1, 4)]),  # complete K4
        (5, [(0, 1), (0, 2), (0, 3), (0, 4)]),  # star S5
    ],
)
def test_union_find_connected_graphs(n, edges):
    """Connected graphs (K2, path, cycle, complete, star) yield 1 component."""
    res = union_find_components(n, edges)
    assert res["component_count"] == 1
    assert res["components"] == [list(range(n))]


def test_union_find_disconnected_isolated_and_edge_cases():
    """Verify exact components for disconnected, isolated-node, empty, and 1-node graphs."""
    # Empty and single-node edge cases
    assert union_find_components(0, [])["component_count"] == 0
    assert union_find_components(1, []) == {
        "component_count": 1,
        "components": [[0]],
        "component_map": {0: 0},
    }

    # Disconnected 2 triangles + isolated node 6
    edges = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)]
    res = union_find_components(7, edges)
    assert res["component_count"] == 3
    assert res["components"] == [[0, 1, 2], [3, 4, 5], [6]]

    # Malformed edge raises ValueError
    with pytest.raises(ValueError):
        union_find_components(3, [(0, 1, 2)])  # type: ignore[list-item]


@pytest.mark.parametrize(
    "n,edges,expected_count",
    [
        (0, [], 0),  # empty graph
        (1, [], 1),  # single-node graph
        (2, [(0, 1)], 1),  # two-node connected
        (4, [(0, 1), (1, 2), (2, 3)], 1),  # path P4
        (5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], 1),  # cycle C5
        (4, [(i, j) for i in range(4) for j in range(i + 1, 4)], 1),  # complete K4
        (5, [(0, 1), (0, 2), (0, 3), (0, 4)], 1),  # star S5
        (6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)], 2),  # disconnected 2xK3
        (5, [(0, 1), (1, 2)], 3),  # path P3 + 2 isolated nodes
    ],
)
def test_union_find_matches_bfs_and_spectral(n, edges, expected_count):
    """Cross-check Union-Find against BFS and Spectral zero-eigenvalue counts on all graph types."""
    uf_res = union_find_components(n, edges)
    bfs_res = bfs_connected_components(n, edges_to_adj_list(n, edges))
    lap = build_laplacian(build_adjacency_matrix(n, edges))
    spectral_res = compute_eigenvalues(lap, method="auto")

    assert uf_res["component_count"] == expected_count
    assert uf_res["component_count"] == bfs_res["component_count"]
    assert uf_res["component_count"] == spectral_res["zero_eigenvalue_count"]
    assert uf_res["components"] == bfs_res["components"]
