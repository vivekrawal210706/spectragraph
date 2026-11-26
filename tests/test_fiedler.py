"""Unit tests for Fiedler value, Fiedler vector, and spectral bisection."""

from __future__ import annotations

import math
import numpy as np
import pytest

from math_engine.adjacency import build_adjacency_matrix
from math_engine.eigenvalues import compute_eigenvalues
from math_engine.fiedler import compute_fiedler
from math_engine.laplacian import build_laplacian


def _run_fiedler(n: int, edges: list[tuple[int, int]], method: str = "auto") -> dict:
    adj = build_adjacency_matrix(n, edges)
    lap = build_laplacian(adj)
    eig = compute_eigenvalues(lap, method=method)
    return compute_fiedler(eig["eigenvalues"], eig["eigenvectors"])


def test_fiedler_two_community_graph_clean_separation():
    """10-node two-community graph with bridge edges cleanly partitions {0..4} and {5..9}."""
    group_a = [
        (0, 1), (0, 2), (0, 4),
        (1, 2), (1, 3),
        (2, 3), (2, 4),
        (3, 4),
    ]
    group_b = [
        (5, 6), (5, 7), (5, 9),
        (6, 7), (6, 8),
        (7, 8), (7, 9),
        (8, 9),
    ]
    bridges = [(2, 7), (4, 5)]
    res = _run_fiedler(10, group_a + group_b + bridges)

    assert res["is_connected"] is True
    assert res["can_partition"] is True
    assert res["lambda_2"] is not None
    assert res["lambda_2"] > 0.0
    assert res["partition"] is not None

    g1 = frozenset(res["partition"]["group_1"])
    g2 = frozenset(res["partition"]["group_2"])
    assert g1 | g2 == frozenset(range(10))
    assert g1 & g2 == frozenset()
    assert {g1, g2} == {frozenset(range(0, 5)), frozenset(range(5, 10))}

    # Fiedler vector is unit-norm and orthogonal to the constant all-ones vector
    fvec = res["fiedler_vector"]
    assert fvec is not None
    assert np.sum(fvec) == pytest.approx(0.0, abs=1e-7)
    assert np.linalg.norm(fvec) == pytest.approx(1.0, abs=1e-7)


def test_fiedler_path_p4_exact_value_and_partition():
    """Path P4 has lambda_2 = 2 - sqrt(2) and splits cleanly into [0, 1] and [2, 3]."""
    res = _run_fiedler(4, [(0, 1), (1, 2), (2, 3)])

    assert res["is_connected"] is True
    assert res["can_partition"] is True
    assert res["lambda_2"] == pytest.approx(2.0 - math.sqrt(2.0), abs=1e-8)

    g1 = sorted(res["partition"]["group_1"])
    g2 = sorted(res["partition"]["group_2"])
    assert sorted([g1, g2]) == [[0, 1], [2, 3]]


def test_fiedler_complete_k4_and_symmetric_repeated_eigenvalues():
    """Complete graph K4 (repeated lambda_2=4) and Star S4 still produce valid non-empty partitions."""
    # Complete graph K4: eigenvalues [0, 4, 4, 4]
    k4_edges = [(i, j) for i in range(4) for j in range(i + 1, 4)]
    res_k4 = _run_fiedler(4, k4_edges)
    assert res_k4["is_connected"] is True
    assert res_k4["can_partition"] is True
    assert res_k4["lambda_2"] == pytest.approx(4.0, abs=1e-8)
    g1_k4 = set(res_k4["partition"]["group_1"])
    g2_k4 = set(res_k4["partition"]["group_2"])
    assert len(g1_k4) > 0 and len(g2_k4) > 0
    assert g1_k4 | g2_k4 == {0, 1, 2, 3}
    assert g1_k4 & g2_k4 == set()

    # Two-node connected K2: eigenvalues [0, 2]
    res_k2 = _run_fiedler(2, [(0, 1)])
    assert res_k2["is_connected"] is True
    assert res_k2["can_partition"] is True
    assert res_k2["lambda_2"] == pytest.approx(2.0, abs=1e-8)
    assert sorted([res_k2["partition"]["group_1"], res_k2["partition"]["group_2"]]) == [[0], [1]]


def test_fiedler_edge_cases_empty_single_and_disconnected():
    """Test n=0, n=1, disconnected 2xK3, and graph with isolated node."""
    # Empty graph (n=0)
    res_empty = _run_fiedler(0, [])
    assert res_empty["lambda_2"] is None
    assert res_empty["fiedler_vector"] is None
    assert res_empty["is_connected"] is False
    assert res_empty["can_partition"] is False
    assert res_empty["partition"] is None
    assert "n=0" in res_empty["explanation"]

    # Single-node graph (n=1)
    res_single = _run_fiedler(1, [])
    assert res_single["lambda_2"] is None
    assert res_single["fiedler_vector"] is None
    assert res_single["is_connected"] is True
    assert res_single["can_partition"] is False
    assert res_single["partition"] is None
    assert "n=1" in res_single["explanation"]

    # Disconnected 2xK3
    res_disc = _run_fiedler(6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
    assert res_disc["is_connected"] is False
    assert res_disc["can_partition"] is False
    assert res_disc["partition"] is None
    assert res_disc["lambda_2"] == pytest.approx(0.0, abs=1e-8)
    assert "disconnected" in res_disc["explanation"].lower()

    # Graph with isolated node (K2 + node 2)
    res_iso = _run_fiedler(3, [(0, 1)])
    assert res_iso["is_connected"] is False
    assert res_iso["can_partition"] is False
    assert res_iso["lambda_2"] == pytest.approx(0.0, abs=1e-8)


def test_fiedler_unsorted_input_fallback_and_validation():
    """Verify compute_fiedler handles unsorted eigenvalues, fallback partitioning, and invalid shapes."""
    # Unsorted eigenvalues/eigenvectors for P2: lambda_0=0, lambda_1=2 in reverse column order
    eigs_unsorted = np.array([2.0, 0.0])
    vecs_unsorted = np.array(
        [
            [1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0)],
            [-1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0)],
        ]
    )
    res_sorted = compute_fiedler(eigs_unsorted, vecs_unsorted)
    assert res_sorted["is_connected"] is True
    assert res_sorted["lambda_2"] == pytest.approx(2.0)
    assert sorted([res_sorted["partition"]["group_1"], res_sorted["partition"]["group_2"]]) == [[0], [1]]

    # Fallback when Fiedler vector has all non-negative coordinates (median fallback splits cleanly)
    eigs_synth = np.array([0.0, 1.0, 3.0])
    vecs_synth = np.array(
        [
            [0.577, 0.1, 0.0],
            [0.577, 0.2, 0.0],
            [0.577, 0.9, 0.0],
        ]
    )
    res_fallback = compute_fiedler(eigs_synth, vecs_synth)
    assert res_fallback["can_partition"] is True
    assert len(res_fallback["partition"]["group_1"]) > 0
    assert len(res_fallback["partition"]["group_2"]) > 0

    with pytest.raises(ValueError):
        compute_fiedler(np.array([[0.0, 1.0]]), np.eye(2))

    with pytest.raises(ValueError):
        compute_fiedler(np.array([0.0, 1.0]), np.eye(3))
