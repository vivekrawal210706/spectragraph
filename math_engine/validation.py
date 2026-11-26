"""Matrix validation helpers for adjacency, degree, and Laplacian matrices."""

from __future__ import annotations

import numpy as np

from .laplacian import verify_laplacian


def validate_adjacency(adj: np.ndarray) -> dict:
    """Check: square, symmetric, binary, zero diagonal."""
    mat = np.asarray(adj, dtype=float)
    is_square = bool(mat.ndim == 2 and mat.shape[0] == mat.shape[1])

    if not is_square:
        return {
            "is_square": False,
            "is_symmetric": False,
            "is_binary": False,
            "zero_diagonal": False,
            "is_valid": False,
        }

    if mat.shape[0] == 0:
        return {
            "is_square": True,
            "is_symmetric": True,
            "is_binary": True,
            "zero_diagonal": True,
            "is_valid": True,
        }

    is_symmetric = bool(np.allclose(mat, mat.T, atol=1e-10, rtol=0.0))
    is_binary = bool(
        np.all(
            np.isclose(mat, 0.0, atol=1e-10, rtol=0.0)
            | np.isclose(mat, 1.0, atol=1e-10, rtol=0.0)
        )
    )
    zero_diagonal = bool(np.all(np.isclose(np.diag(mat), 0.0, atol=1e-10, rtol=0.0)))
    is_valid = bool(is_square and is_symmetric and is_binary and zero_diagonal)

    return {
        "is_square": is_square,
        "is_symmetric": is_symmetric,
        "is_binary": is_binary,
        "zero_diagonal": zero_diagonal,
        "is_valid": is_valid,
    }


def validate_all_matrices(
    adj: np.ndarray,
    deg: np.ndarray,
    lap: np.ndarray,
) -> dict:
    """Validate all three matrices and their relationships."""
    adj_arr = np.asarray(adj, dtype=float)
    deg_arr = np.asarray(deg, dtype=float)
    lap_arr = np.asarray(lap, dtype=float)

    adj_check = validate_adjacency(adj_arr)
    shapes_match = bool(
        adj_check["is_square"]
        and deg_arr.ndim == 2
        and lap_arr.ndim == 2
        and adj_arr.shape == deg_arr.shape == lap_arr.shape
    )

    if shapes_match:
        if adj_arr.shape[0] == 0:
            degree_is_diagonal = True
            degree_matches_adjacency = True
            laplacian_equals_d_minus_a = True
        else:
            deg_diag = np.diag(np.diag(deg_arr))
            degree_is_diagonal = bool(
                np.allclose(deg_arr, deg_diag, atol=1e-10, rtol=0.0)
            )
            degree_matches_adjacency = bool(
                np.allclose(np.diag(deg_arr), np.sum(adj_arr, axis=1), atol=1e-10, rtol=0.0)
            )
            laplacian_equals_d_minus_a = bool(
                np.allclose(lap_arr, deg_arr - adj_arr, atol=1e-10, rtol=0.0)
            )
        lap_check = verify_laplacian(lap_arr)
    else:
        degree_is_diagonal = False
        degree_matches_adjacency = False
        laplacian_equals_d_minus_a = False
        lap_check = {
            "is_symmetric": False,
            "row_sums_zero": False,
            "is_positive_semidefinite": False,
        }

    is_valid = bool(
        adj_check["is_valid"]
        and shapes_match
        and degree_is_diagonal
        and degree_matches_adjacency
        and laplacian_equals_d_minus_a
        and lap_check["is_symmetric"]
        and lap_check["row_sums_zero"]
        and lap_check["is_positive_semidefinite"]
    )

    return {
        "adjacency": adj_check,
        "laplacian": lap_check,
        "shapes_match": shapes_match,
        "degree_is_diagonal": degree_is_diagonal,
        "degree_matches_adjacency": degree_matches_adjacency,
        "laplacian_equals_d_minus_a": laplacian_equals_d_minus_a,
        "is_valid": is_valid,
    }
