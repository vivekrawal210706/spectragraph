"""Unit tests for Jacobi and NumPy Laplacian eigenvalue solvers."""

from __future__ import annotations

import math
import numpy as np
import pytest

from math_engine.adjacency import build_adjacency_matrix
from math_engine.eigenvalues import (
    compute_eigenvalues,
    count_zero_eigenvalues,
    jacobi_eigen,
    numpy_eigen,
)
from math_engine.laplacian import build_laplacian


def _laplacian_from_edges(n: int, edges: list[tuple[int, int]]) -> np.ndarray:
    adj = build_adjacency_matrix(n, edges)
    return build_laplacian(adj)


# ---------------------------------------------------------------------------
# Jacobi & NumPy solver tests on known graph spectra
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,n,edges,expected_eigs",
    [
        ("K3", 3, [(0, 1), (1, 2), (2, 0)], [0.0, 3.0, 3.0]),
        ("P2", 2, [(0, 1)], [0.0, 2.0]),
        ("single_node", 1, [], [0.0]),
        (
            "disconnected_2xK3",
            6,
            [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
            [0.0, 0.0, 3.0, 3.0, 3.0, 3.0],
        ),
        ("star_S4", 4, [(0, 1), (0, 2), (0, 3)], [0.0, 1.0, 1.0, 4.0]),
        ("cycle_C4", 4, [(0, 1), (1, 2), (2, 3), (3, 0)], [0.0, 2.0, 2.0, 4.0]),
        (
            "path_P4",
            4,
            [(0, 1), (1, 2), (2, 3)],
            [0.0, 2.0 - math.sqrt(2.0), 2.0, 2.0 + math.sqrt(2.0)],
        ),
        ("isolated_plus_K2", 4, [(0, 1)], [0.0, 0.0, 0.0, 2.0]),
    ],
)
def test_jacobi_and_numpy_known_spectra(name, n, edges, expected_eigs):
    """Both jacobi_eigen and numpy_eigen must match analytical Laplacian eigenvalues."""
    lap = _laplacian_from_edges(n, edges)

    j_vals, j_vecs = jacobi_eigen(lap, max_iterations=250)
    n_vals, n_vecs = numpy_eigen(lap)

    np.testing.assert_allclose(j_vals, expected_eigs, atol=1e-8)
    np.testing.assert_allclose(n_vals, expected_eigs, atol=1e-10)
    np.testing.assert_allclose(j_vals, n_vals, atol=1e-8)

    # Verify eigenvalue equation L @ V = V @ diag(lambda) and orthonormality V^T V = I
    np.testing.assert_allclose(lap @ j_vecs, j_vecs @ np.diag(j_vals), atol=1e-7)
    np.testing.assert_allclose(j_vecs.T @ j_vecs, np.eye(n), atol=1e-8)
    np.testing.assert_allclose(lap @ n_vecs, n_vecs @ np.diag(n_vals), atol=1e-10)
    np.testing.assert_allclose(n_vecs.T @ n_vecs, np.eye(n), atol=1e-10)


def test_eigen_solvers_empty_graph_and_invalid_inputs():
    """Empty graph returns empty arrays; non-square/asymmetric matrices raise ValueError."""
    empty_lap = _laplacian_from_edges(0, [])
    j_vals, j_vecs = jacobi_eigen(empty_lap)
    n_vals, n_vecs = numpy_eigen(empty_lap)
    assert j_vals.shape == (0,)
    assert j_vecs.shape == (0, 0)
    assert n_vals.shape == (0,)
    assert n_vecs.shape == (0, 0)

    with pytest.raises(ValueError):
        jacobi_eigen(np.zeros((2, 3)))

    with pytest.raises(ValueError):
        jacobi_eigen(np.array([[1.0, -1.0], [0.0, 1.0]]))

    with pytest.raises(ValueError):
        jacobi_eigen(np.eye(2), max_iterations=-1)

    with pytest.raises(ValueError):
        numpy_eigen(np.array([[1.0, 2.0], [0.0, 1.0]]))


# ---------------------------------------------------------------------------
# compute_eigenvalues tests (auto routing and validation)
# ---------------------------------------------------------------------------


def test_compute_eigenvalues_auto_uses_jacobi_for_small_and_numpy_for_large():
    """method='auto' uses Jacobi + NumPy validation for n<=10, and NumPy for n>10."""
    # n = 10 cycle C10 -> should select 'jacobi' and validate against NumPy
    edges_c10 = [(i, (i + 1) % 10) for i in range(10)]
    res_small = compute_eigenvalues(_laplacian_from_edges(10, edges_c10), method="auto")
    expected_c10 = sorted(2.0 - 2.0 * math.cos(2.0 * math.pi * k / 10.0) for k in range(10))

    assert res_small["method_used"] == "jacobi"
    assert res_small["jacobi_validated"] is True
    assert res_small["validation_max_error"] < 1e-8
    assert res_small["zero_eigenvalue_count"] == 1
    assert res_small["is_connected"] is True
    assert res_small["lambda_2"] == pytest.approx(2.0 - 2.0 * math.cos(2.0 * math.pi / 10.0), abs=1e-7)
    np.testing.assert_allclose(res_small["eigenvalues"], expected_c10, atol=1e-7)

    # n = 12 cycle C12 -> should select 'numpy' directly
    edges_c12 = [(i, (i + 1) % 12) for i in range(12)]
    res_large = compute_eigenvalues(_laplacian_from_edges(12, edges_c12), method="auto")
    expected_c12 = sorted(2.0 - 2.0 * math.cos(2.0 * math.pi * k / 12.0) for k in range(12))

    assert res_large["method_used"] == "numpy"
    assert res_large["jacobi_validated"] is False
    assert res_large["validation_max_error"] == 0.0
    assert res_large["zero_eigenvalue_count"] == 1
    assert res_large["is_connected"] is True
    assert res_large["lambda_2"] == pytest.approx(2.0 - math.sqrt(3.0), abs=1e-9)
    np.testing.assert_allclose(res_large["eigenvalues"], expected_c12, atol=1e-9)


def test_compute_eigenvalues_explicit_methods_and_edge_cases():
    """Test explicit method='numpy'/'jacobi', n=0, n=1, and invalid method."""
    lap_k3 = _laplacian_from_edges(3, [(0, 1), (1, 2), (2, 0)])
    res_np = compute_eigenvalues(lap_k3, method="numpy")
    assert res_np["method_used"] == "numpy"
    assert res_np["jacobi_validated"] is False
    np.testing.assert_allclose(res_np["eigenvalues"], [0.0, 3.0, 3.0], atol=1e-10)

    res_empty = compute_eigenvalues(_laplacian_from_edges(0, []), method="auto")
    assert res_empty["zero_eigenvalue_count"] == 0
    assert res_empty["lambda_2"] is None
    assert res_empty["is_connected"] is False

    res_single = compute_eigenvalues(_laplacian_from_edges(1, []), method="auto")
    assert res_single["zero_eigenvalue_count"] == 1
    assert res_single["lambda_2"] is None
    assert res_single["is_connected"] is True

    with pytest.raises(ValueError):
        compute_eigenvalues(lap_k3, method="power_iteration")


# ---------------------------------------------------------------------------
# count_zero_eigenvalues tests
# ---------------------------------------------------------------------------


def test_count_zero_eigenvalues_tolerance_and_edge_cases():
    """Verify tolerance thresholding and empty/all-zero eigenvalue arrays."""
    assert count_zero_eigenvalues(np.array([])) == 0
    assert count_zero_eigenvalues(np.array([0.0])) == 1
    assert count_zero_eigenvalues(np.array([0.0, 0.0, 0.0])) == 3

    sample = np.array([-5e-10, 4e-10, 1e-6, 2.0])
    # Default tolerance is 1e-9 -> two values within (-1e-9, 1e-9)
    assert count_zero_eigenvalues(sample) == 2
    # Looser tolerance catches 1e-6 as well
    assert count_zero_eigenvalues(sample, tol=1e-5) == 3
    # Strict tolerance excludes -5e-10 and 4e-10
    assert count_zero_eigenvalues(sample, tol=1e-11) == 0


@pytest.mark.parametrize(
    "n,edges,expected_components",
    [
        (0, [], 0),  # empty graph
        (1, [], 1),  # single-node graph
        (2, [(0, 1)], 1),  # two-node connected
        (5, [(0, 1), (1, 2), (2, 3), (3, 4)], 1),  # path P5
        (5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], 1),  # cycle C5
        (4, [(i, j) for i in range(4) for j in range(i + 1, 4)], 1),  # complete K4
        (5, [(0, 1), (0, 2), (0, 3), (0, 4)], 1),  # star S5
        (6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)], 2),  # disconnected 2xK3
        (5, [(0, 1), (1, 2), (2, 0)], 3),  # K3 + 2 isolated nodes
    ],
)
def test_spectral_zero_count_matches_expected_components(n, edges, expected_components):
    """Number of zero Laplacian eigenvalues equals connected component count across all graph types."""
    lap = _laplacian_from_edges(n, edges)
    result = compute_eigenvalues(lap, method="auto")
    assert result["zero_eigenvalue_count"] == expected_components
    assert result["is_connected"] is (expected_components == 1)
