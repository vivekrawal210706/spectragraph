"""Degree matrix construction from a graph adjacency matrix."""

from __future__ import annotations

import numpy as np


def build_degree_matrix(adjacency: np.ndarray) -> np.ndarray:
    """
    Build the diagonal degree matrix D from the adjacency matrix.

    D[i][i] = sum of row i in A (i.e., degree of node i).
    Off-diagonal entries are 0.
    """
    adj = np.asarray(adjacency, dtype=float)
    if adj.ndim != 2 or adj.shape[0] != adj.shape[1]:
        raise ValueError(
            f"Adjacency matrix must be a 2D square matrix, got shape {adj.shape}."
        )

    if adj.shape[0] == 0:
        return np.zeros((0, 0), dtype=float)

    degrees = np.sum(adj, axis=1)
    return np.diag(degrees)
