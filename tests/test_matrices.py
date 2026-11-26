"""Unit tests for adjacency, degree, Laplacian matrices, and matrix validation."""

from __future__ import annotations

import numpy as np
import pytest

from math_engine.adjacency import build_adjacency_matrix
from math_engine.degree import build_degree_matrix
from math_engine.laplacian import build_laplacian, verify_laplacian
from math_engine.validation import validate_adjacency, validate_all_matrices


# ---------------------------------------------------------------------------
# Adjacency matrix tests
# ---------------------------------------------------------------------------


def test_adjacency_known_graphs():
    """Verify exact adjacency matrices for K3, P4, and two-node connected K2."""
    # Complete graph K3
    adj_k3 = build_adjacency_matrix(3, [(0, 1), (1, 2), (2, 0)])
    expected_k3 = np.array(
        [
            [0.0, 1.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 0.0],
        ]
    )
    assert np.array_equal(adj_k3, expected_k3)

    # Path graph P4
    adj_p4 = build_adjacency_matrix(4, [(0, 1), (1, 2), (2, 3)])
    expected_p4 = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [1.0, 0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0, 1.0],
            [0.0, 0.0, 1.0, 0.0],
        ]
    )
    assert np.array_equal(adj_p4, expected_p4)

    # Two-node connected graph K2
    adj_k2 = build_adjacency_matrix(2, [(0, 1)])
    expected_k2 = np.array([[0.0, 1.0], [1.0, 0.0]])
    assert np.array_equal(adj_k2, expected_k2)


def test_adjacency_symmetry_self_loops_and_duplicates():
    """Adjacency matrix must be symmetric, ignore self-loops, and deduplicate edges."""
    adj = build_adjacency_matrix(
        4,
        [
            (0, 2),
            (2, 0),  # duplicate reversed edge
            (0, 2),  # duplicate identical edge
            (0, 0),  # self-loop
            (3, 3),  # self-loop on isolated node
        ],
    )
    assert np.array_equal(adj, adj.T)
    assert np.array_equal(np.diag(adj), np.zeros(4))
    assert adj[0, 2] == 1.0
    assert adj[2, 0] == 1.0
    assert adj[1].sum() == 0.0
    assert adj[3].sum() == 0.0


def test_adjacency_edge_cases_and_validation():
    """Test empty graph (n=0), single node (n=1), and invalid inputs."""
    adj_empty = build_adjacency_matrix(0, [])
    assert adj_empty.shape == (0, 0)

    adj_single = build_adjacency_matrix(1, [(0, 0)])
    assert adj_single.shape == (1, 1)
    assert np.array_equal(adj_single, np.array([[0.0]]))

    with pytest.raises(ValueError):
        build_adjacency_matrix(-1, [])

    with pytest.raises(ValueError):
        build_adjacency_matrix(3, [(0, 3)])

    with pytest.raises(ValueError):
        build_adjacency_matrix(3, [(0, 1, 2)])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Degree matrix tests
# ---------------------------------------------------------------------------


def test_degree_matrix_star_and_standard_graphs():
    """Verify diagonal degrees and zero off-diagonals on Star S5, P4, and K3."""
    # Star graph S5: center 0 connected to leaves 1, 2, 3, 4
    adj_s5 = build_adjacency_matrix(5, [(0, 1), (0, 2), (0, 3), (0, 4)])
    deg_s5 = build_degree_matrix(adj_s5)
    expected_s5 = np.diag([4.0, 1.0, 1.0, 1.0, 1.0])
    assert np.array_equal(deg_s5, expected_s5)
    assert np.array_equal(deg_s5 - np.diag(np.diag(deg_s5)), np.zeros((5, 5)))

    # Path graph P4: degrees [1, 2, 2, 1]
    adj_p4 = build_adjacency_matrix(4, [(0, 1), (1, 2), (2, 3)])
    assert np.array_equal(np.diag(build_degree_matrix(adj_p4)), np.array([1.0, 2.0, 2.0, 1.0]))

    # Handshaking lemma check: trace(D) == 2 * |E|
    assert np.trace(deg_s5) == 8.0


def test_degree_matrix_isolated_nodes_and_empty():
    """Isolated nodes must have degree 0; empty graph yields 0x0 matrix."""
    # Triangle on 0,1,2 plus isolated nodes 3 and 4
    adj_iso = build_adjacency_matrix(5, [(0, 1), (1, 2), (2, 0)])
    deg_iso = build_degree_matrix(adj_iso)
    assert np.array_equal(deg_iso, np.diag([2.0, 2.0, 2.0, 0.0, 0.0]))

    # Single isolated node
    deg_single = build_degree_matrix(np.array([[0.0]]))
    assert np.array_equal(deg_single, np.array([[0.0]]))

    # Empty graph
    deg_empty = build_degree_matrix(np.zeros((0, 0)))
    assert deg_empty.shape == (0, 0)


def test_degree_matrix_invalid_input():
    """Non-square or non-2D matrices must raise ValueError."""
    with pytest.raises(ValueError):
        build_degree_matrix(np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 1.0]]))

    with pytest.raises(ValueError):
        build_degree_matrix(np.array([1.0, 2.0, 3.0]))


# ---------------------------------------------------------------------------
# Laplacian matrix and verification tests
# ---------------------------------------------------------------------------


def test_laplacian_exact_values_k3_p4_s4():
    """Verify exact L = D - A matrices for K3, P4, and S4."""
    # K3
    lap_k3 = build_laplacian(build_adjacency_matrix(3, [(0, 1), (1, 2), (2, 0)]))
    expected_k3 = np.array(
        [
            [2.0, -1.0, -1.0],
            [-1.0, 2.0, -1.0],
            [-1.0, -1.0, 2.0],
        ]
    )
    assert np.array_equal(lap_k3, expected_k3)

    # P4
    lap_p4 = build_laplacian(build_adjacency_matrix(4, [(0, 1), (1, 2), (2, 3)]))
    expected_p4 = np.array(
        [
            [1.0, -1.0, 0.0, 0.0],
            [-1.0, 2.0, -1.0, 0.0],
            [0.0, -1.0, 2.0, -1.0],
            [0.0, 0.0, -1.0, 1.0],
        ]
    )
    assert np.array_equal(lap_p4, expected_p4)

    # S4 (center 0, leaves 1, 2, 3)
    lap_s4 = build_laplacian(build_adjacency_matrix(4, [(0, 1), (0, 2), (0, 3)]))
    expected_s4 = np.array(
        [
            [3.0, -1.0, -1.0, -1.0],
            [-1.0, 1.0, 0.0, 0.0],
            [-1.0, 0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0, 1.0],
        ]
    )
    assert np.array_equal(lap_s4, expected_s4)


def test_verify_laplacian_properties_and_edge_cases():
    """Verify symmetry, zero row sums, PSD on normal, cycle, disconnected, and n=0/1 graphs."""
    # Cycle C4 and disconnected K2 + isolated node
    for n, edges in [
        (0, []),
        (1, []),
        (2, [(0, 1)]),
        (4, [(0, 1), (1, 2), (2, 3), (3, 0)]),
        (3, [(0, 1)]),
    ]:
        lap = build_laplacian(build_adjacency_matrix(n, edges))
        checks = verify_laplacian(lap)
        assert checks == {
            "is_symmetric": True,
            "row_sums_zero": True,
            "is_positive_semidefinite": True,
        }


def test_verify_laplacian_detects_invalid_matrices():
    """verify_laplacian must distinguish asymmetry, non-zero row sums, and indefiniteness."""
    # Asymmetric matrix with zero row sums
    asym = np.array([[1.0, -1.0], [0.0, 0.0]])
    res_asym = verify_laplacian(asym)
    assert res_asym["is_symmetric"] is False
    assert res_asym["row_sums_zero"] is True

    # Symmetric PSD matrix with non-zero row sums (shifted identity)
    shifted = np.array([[2.0, -1.0], [-1.0, 2.0]])
    res_shifted = verify_laplacian(shifted)
    assert res_shifted["is_symmetric"] is True
    assert res_shifted["row_sums_zero"] is False
    assert res_shifted["is_positive_semidefinite"] is True

    # Symmetric matrix with zero row sums, but negative eigenvalue (-2 and 0)
    indef = np.array([[-1.0, 1.0], [1.0, -1.0]])
    res_indef = verify_laplacian(indef)
    assert res_indef["is_symmetric"] is True
    assert res_indef["row_sums_zero"] is True
    assert res_indef["is_positive_semidefinite"] is False

    with pytest.raises(ValueError):
        verify_laplacian(np.zeros((2, 3)))


# ---------------------------------------------------------------------------
# Matrix validation tests
# ---------------------------------------------------------------------------


def test_validate_adjacency_valid_and_invalid():
    """Test validate_adjacency across valid matrices and every invalid condition."""
    # Valid matrices: empty, single node, C4
    assert validate_adjacency(np.zeros((0, 0)))["is_valid"] is True
    assert validate_adjacency(np.zeros((1, 1)))["is_valid"] is True
    adj_c4 = build_adjacency_matrix(4, [(0, 1), (1, 2), (2, 3), (3, 0)])
    assert validate_adjacency(adj_c4) == {
        "is_square": True,
        "is_symmetric": True,
        "is_binary": True,
        "zero_diagonal": True,
        "is_valid": True,
    }

    # Non-square
    non_sq = validate_adjacency(np.zeros((2, 3)))
    assert non_sq["is_square"] is False
    assert non_sq["is_valid"] is False

    # Asymmetric
    asym = validate_adjacency(np.array([[0.0, 1.0], [0.0, 0.0]]))
    assert asym["is_square"] is True
    assert asym["is_symmetric"] is False
    assert asym["is_valid"] is False

    # Non-zero diagonal
    self_loop = validate_adjacency(np.array([[1.0, 0.0], [0.0, 0.0]]))
    assert self_loop["zero_diagonal"] is False
    assert self_loop["is_valid"] is False

    # Non-binary entries (weighted graph)
    weighted = validate_adjacency(np.array([[0.0, 2.0], [2.0, 0.0]]))
    assert weighted["is_binary"] is False
    assert weighted["is_valid"] is False


def test_validate_all_matrices_valid_and_mismatch_cases():
    """Test validate_all_matrices for consistency checks across A, D, and L."""
    # Valid case on P4 and empty graph
    for n, edges in [(0, []), (4, [(0, 1), (1, 2), (2, 3)])]:
        adj = build_adjacency_matrix(n, edges)
        deg = build_degree_matrix(adj)
        lap = build_laplacian(adj)
        res = validate_all_matrices(adj, deg, lap)
        assert res["is_valid"] is True
        assert res["shapes_match"] is True
        assert res["degree_is_diagonal"] is True
        assert res["degree_matches_adjacency"] is True
        assert res["laplacian_equals_d_minus_a"] is True

    adj = build_adjacency_matrix(3, [(0, 1), (1, 2)])
    deg = build_degree_matrix(adj)
    lap = build_laplacian(adj)

    # Shape mismatch
    res_shape = validate_all_matrices(adj, np.zeros((2, 2)), lap)
    assert res_shape["shapes_match"] is False
    assert res_shape["is_valid"] is False

    # Degree matrix has off-diagonal entries
    bad_deg = deg.copy()
    bad_deg[0, 1] = 0.5
    bad_deg[1, 0] = 0.5
    res_diag = validate_all_matrices(adj, bad_deg, bad_deg - adj)
    assert res_diag["degree_is_diagonal"] is False
    assert res_diag["is_valid"] is False

    # Degree matrix doesn't match row sums of A
    wrong_deg = np.diag([9.0, 2.0, 1.0])
    res_deg_match = validate_all_matrices(adj, wrong_deg, wrong_deg - adj)
    assert res_deg_match["degree_matches_adjacency"] is False
    assert res_deg_match["is_valid"] is False

    # Laplacian != D - A
    bad_lap = lap + np.eye(3)
    res_lap_eq = validate_all_matrices(adj, deg, bad_lap)
    assert res_lap_eq["laplacian_equals_d_minus_a"] is False
    assert res_lap_eq["is_valid"] is False


def test_compute_null_space_dimension_and_residual():
    """compute_null_space returns exact dimension, orthogonal basis, and ~0 residual."""
    from math_engine.eigenvalues import compute_eigenvalues
    from math_engine.laplacian import compute_null_space

    # Disconnected 2xK3 -> 2-dimensional null space
    adj = build_adjacency_matrix(6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)])
    lap = build_laplacian(adj)
    eig = compute_eigenvalues(lap, method="auto")
    ns = compute_null_space(lap, eig["eigenvalues"], eig["eigenvectors"])
    assert ns["dimension"] == 2
    assert len(ns["basis_vectors"]) == 2
    assert ns["max_residual"] < 1e-8

    # Empty graph -> 0-dimensional null space
    ns_empty = compute_null_space(np.zeros((0, 0)), np.array([]), np.zeros((0, 0)))
    assert ns_empty["dimension"] == 0
    assert ns_empty["basis_vectors"] == []
