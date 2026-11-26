"""Graph Laplacian construction and mathematical property verification."""

from __future__ import annotations

import numpy as np

from .degree import build_degree_matrix


def build_laplacian(adjacency: np.ndarray) -> np.ndarray:
    """
    Build the graph Laplacian L = D - A.
    """
    adj = np.asarray(adjacency, dtype=float)
    degree = build_degree_matrix(adj)
    return degree - adj


def verify_laplacian(laplacian: np.ndarray, tol: float = 1e-10) -> dict:
    """
    Verify properties of the Laplacian:
    - is_symmetric: L == L^T
    - row_sums_zero: all row sums are ~0 within tolerance
    - is_positive_semidefinite: all eigenvalues >= -tol

    Returns dict with these boolean fields.
    """
    lap = np.asarray(laplacian, dtype=float)
    if lap.ndim != 2 or lap.shape[0] != lap.shape[1]:
        raise ValueError(
            f"Laplacian matrix must be a 2D square matrix, got shape {lap.shape}."
        )

    if lap.shape[0] == 0:
        return {
            "is_symmetric": True,
            "row_sums_zero": True,
            "is_positive_semidefinite": True,
        }

    is_symmetric = bool(np.allclose(lap, lap.T, atol=tol, rtol=0.0))
    row_sums = np.sum(lap, axis=1)
    row_sums_zero = bool(np.all(np.abs(row_sums) <= tol))

    if is_symmetric:
        # Symmetrize tiny floating-point asymmetry before eigvalsh.
        sym_lap = 0.5 * (lap + lap.T)
        eigenvalues = np.linalg.eigvalsh(sym_lap)
        is_positive_semidefinite = bool(np.all(eigenvalues >= -tol))
    else:
        eigenvalues = np.linalg.eigvals(lap)
        is_positive_semidefinite = bool(
            np.all(np.abs(eigenvalues.imag) <= tol)
            and np.all(eigenvalues.real >= -tol)
        )

    return {
        "is_symmetric": is_symmetric,
        "row_sums_zero": row_sums_zero,
        "is_positive_semidefinite": is_positive_semidefinite,
    }


def compute_null_space(
    laplacian: np.ndarray,
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    tol: float = 1e-9,
) -> dict:
    """
    Compute the null space ker(L) = {x : Lx = 0} from the zero-eigenvalue
    eigenvectors of the graph Laplacian L.

    Returns dict:
    {
        'dimension': int (multiplicity of lambda ~ 0),
        'basis_vectors': list[list[float]] (orthonormal basis vectors),
        'max_residual': float (max |L @ v| across basis vectors),
        'explanation': str,
    }
    """
    lap = np.asarray(laplacian, dtype=float)
    eigs = np.asarray(eigenvalues, dtype=float)
    vecs = np.asarray(eigenvectors, dtype=float)

    if lap.ndim != 2 or lap.shape[0] != lap.shape[1]:
        raise ValueError(
            f"Laplacian matrix must be a 2D square matrix, got shape {lap.shape}."
        )

    n = lap.shape[0]
    if n == 0 or eigs.size == 0:
        return {
            "dimension": 0,
            "basis_vectors": [],
            "max_residual": 0.0,
            "explanation": "Empty graph has a trivial 0-dimensional null space.",
        }

    zero_indices = [int(i) for i in range(len(eigs)) if abs(float(eigs[i])) < tol]
    basis_vectors = []
    max_residual = 0.0

    for idx in zero_indices:
        vec = vecs[:, idx]
        residual = float(np.max(np.abs(lap @ vec)))
        if residual > max_residual:
            max_residual = residual
        cleaned = [0.0 if abs(float(x)) < 1e-12 else float(x) for x in vec]
        basis_vectors.append(cleaned)

    dim = len(zero_indices)
    explanation = (
        f"dim(ker(L)) = {dim}: the null space of L is spanned by {dim} orthogonal "
        f"vector(s) corresponding to λ ≈ 0, matching the {dim} connected component(s)."
    )
    return {
        "dimension": dim,
        "basis_vectors": basis_vectors,
        "max_residual": max_residual,
        "explanation": explanation,
    }
