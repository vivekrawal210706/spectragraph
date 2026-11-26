"""Fiedler value and vector computation for spectral graph bisection."""

from __future__ import annotations

import numpy as np

from .eigenvalues import EIGENVALUE_TOLERANCE, count_zero_eigenvalues


def _bisect_with_fallback(fiedler_vector: np.ndarray) -> tuple[list[int], list[int]]:
    """Partition nodes into two non-empty groups using Fiedler vector signs."""
    n = len(fiedler_vector)
    group_1 = [i for i in range(n) if fiedler_vector[i] >= 0.0]
    group_2 = [i for i in range(n) if fiedler_vector[i] < 0.0]

    if group_1 and group_2:
        return group_1, group_2

    # Adjust threshold to median if sign threshold left one side empty.
    median_val = float(np.median(fiedler_vector))
    group_1 = [i for i in range(n) if fiedler_vector[i] >= median_val]
    group_2 = [i for i in range(n) if fiedler_vector[i] < median_val]
    if group_1 and group_2:
        return group_1, group_2

    group_1 = [i for i in range(n) if fiedler_vector[i] > median_val]
    group_2 = [i for i in range(n) if fiedler_vector[i] <= median_val]
    if group_1 and group_2:
        return group_1, group_2

    # Final fallback if all coordinates are numerically equal.
    sorted_indices = list(np.argsort(fiedler_vector, kind="stable"))
    mid = n // 2
    return [int(i) for i in sorted_indices[mid:]], [int(i) for i in sorted_indices[:mid]]


def compute_fiedler(eigenvalues: np.ndarray, eigenvectors: np.ndarray) -> dict:
    """
    Compute the Fiedler value and vector for spectral bisection.

    The Fiedler value is lambda_2 (second smallest eigenvalue).
    The Fiedler vector is the corresponding eigenvector.

    Returns dict:
    {
        'lambda_2': float,
        'fiedler_vector': numpy array,
        'is_connected': bool,
        'partition': {
            'group_1': list of node indices where fiedler_vector >= 0,
            'group_2': list of node indices where fiedler_vector < 0,
        } or None if graph is disconnected,
        'can_partition': bool (True if connected and n >= 2),
        'explanation': str (human-readable explanation of the result)
    }

    Special cases:
    - n < 2: cannot partition
    - Disconnected graph (lambda_2 ~ 0): explain that partition is not meaningful
    - If one group would be empty, adjust threshold slightly
    """
    eigs = np.asarray(eigenvalues, dtype=float)
    vecs = np.asarray(eigenvectors, dtype=float)

    if eigs.ndim != 1:
        raise ValueError(f"eigenvalues must be 1D, got shape {eigs.shape}.")

    n = int(eigs.size)
    if n > 0 and (vecs.ndim != 2 or vecs.shape != (n, n)):
        raise ValueError(
            f"eigenvectors must have shape ({n}, {n}), got {vecs.shape}."
        )

    if n < 2:
        is_connected = bool(n == 1 and abs(float(eigs[0])) < EIGENVALUE_TOLERANCE)
        return {
            "lambda_2": None,
            "fiedler_vector": None,
            "is_connected": is_connected,
            "partition": None,
            "can_partition": False,
            "explanation": (
                f"Cannot perform spectral bisection on a graph with n={n} node(s); "
                "at least 2 nodes are required."
            ),
        }

    # Ensure ascending eigenvalue order.
    order = np.argsort(eigs)
    eigs_sorted = eigs[order]
    vecs_sorted = vecs[:, order]

    lambda_2 = float(eigs_sorted[1])
    fiedler_vector = vecs_sorted[:, 1].copy()

    zero_count = count_zero_eigenvalues(eigs_sorted)
    is_connected = bool(
        abs(lambda_2) >= EIGENVALUE_TOLERANCE and zero_count == 1
    )

    if not is_connected:
        return {
            "lambda_2": lambda_2,
            "fiedler_vector": fiedler_vector,
            "is_connected": False,
            "partition": None,
            "can_partition": False,
            "explanation": (
                f"Graph is disconnected (lambda_2 = {lambda_2:.6g}, "
                f"{zero_count} zero eigenvalue(s)). Spectral bisection via the "
                "Fiedler vector is not meaningful because the graph already splits "
                "into multiple connected components."
            ),
        }

    group_1, group_2 = _bisect_with_fallback(fiedler_vector)
    return {
        "lambda_2": lambda_2,
        "fiedler_vector": fiedler_vector,
        "is_connected": True,
        "partition": {
            "group_1": group_1,
            "group_2": group_2,
        },
        "can_partition": True,
        "explanation": (
            f"Graph is connected with algebraic connectivity lambda_2 = {lambda_2:.6g}. "
            f"Fiedler bisection partitioned {n} nodes into group_1 ({len(group_1)} nodes) "
            f"and group_2 ({len(group_2)} nodes)."
        ),
    }
