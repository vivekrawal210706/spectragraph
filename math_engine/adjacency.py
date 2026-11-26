"""Adjacency matrix construction for undirected, unweighted simple graphs."""

from __future__ import annotations

import numpy as np


def build_adjacency_matrix(n: int, edges: list[tuple[int, int]]) -> np.ndarray:
    """
    Build the adjacency matrix A for an undirected, unweighted simple graph.

    Parameters:
        n: number of nodes (0 to n-1)
        edges: list of (i, j) pairs

    Returns:
        n x n symmetric numpy array where A[i][j] = 1 if edge (i, j) exists, 0 otherwise.
        Diagonal is always 0 (no self-loops).

    The matrix is guaranteed symmetric: A[i][j] = A[j][i].
    """
    if n < 0:
        raise ValueError(f"Number of nodes n must be non-negative, got {n}.")

    adjacency = np.zeros((n, n), dtype=float)
    for edge in edges:
        if len(edge) != 2:
            raise ValueError(f"Each edge must be a pair (i, j), got {edge!r}.")
        i, j = int(edge[0]), int(edge[1])
        if not (0 <= i < n and 0 <= j < n):
            raise ValueError(f"Edge ({i}, {j}) is out of bounds for n={n} nodes.")
        if i == j:
            # Simple graph: ignore self-loops so diagonal stays zero.
            continue
        adjacency[i, j] = 1.0
        adjacency[j, i] = 1.0

    return adjacency
