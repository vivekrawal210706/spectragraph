"""Eigenvalue and eigenvector solvers for symmetric graph matrices."""

from __future__ import annotations

import numpy as np

EIGENVALUE_TOLERANCE = 1e-9


def _validate_symmetric_matrix(matrix: np.ndarray) -> np.ndarray:
    """Validate that input is a 2D square symmetric matrix and return float64 copy."""
    mat = np.array(matrix, dtype=float, copy=True)
    if mat.ndim != 2 or mat.shape[0] != mat.shape[1]:
        raise ValueError(
            f"Input matrix must be 2D and square, got shape {mat.shape}."
        )
    if mat.shape[0] > 0 and not np.allclose(mat, mat.T, atol=1e-8, rtol=1e-8):
        raise ValueError("Input matrix must be symmetric.")
    if mat.shape[0] > 0:
        mat = 0.5 * (mat + mat.T)
    return mat


def jacobi_eigen(
    matrix: np.ndarray,
    max_iterations: int = 100,
    tol: float = 1e-10,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Jacobi rotation method for symmetric matrix eigenvalue decomposition.

    This is a transparent, educational implementation suitable for small matrices.
    It iteratively applies Givens rotations to zero out off-diagonal elements.

    Algorithm:
    1. Start with A_0 = matrix, V_0 = Identity
    2. For each iteration:
       a. Find the largest off-diagonal element |A[p][q]|
       b. If max off-diagonal < tol, converged
       c. Compute rotation angle: theta = 0.5 * arctan(2*A[p][q] / (A[p][p] - A[q][q]))
          (handle A[p][p] == A[q][q] case: theta = pi/4)
       d. Construct Givens rotation matrix G
       e. A_{k+1} = G^T @ A_k @ G
       f. V_{k+1} = V_k @ G
    3. Eigenvalues = diagonal of final A
    4. Eigenvectors = columns of final V

    Returns:
        (eigenvalues_sorted, eigenvectors_sorted) sorted in ascending order
    """
    if max_iterations < 0:
        raise ValueError("max_iterations must be non-negative.")

    a_k = _validate_symmetric_matrix(matrix)
    n = a_k.shape[0]

    if n == 0:
        return np.array([], dtype=float), np.zeros((0, 0), dtype=float)
    if n == 1:
        return np.array([float(a_k[0, 0])], dtype=float), np.array([[1.0]], dtype=float)

    v_k = np.eye(n, dtype=float)
    upper_i, upper_j = np.triu_indices(n, k=1)

    for _ in range(max_iterations):
        # Step 2a: Find largest off-diagonal element |A[p][q]| (upper triangle suffices by symmetry).
        off_diag = np.abs(a_k[upper_i, upper_j])
        max_idx = int(np.argmax(off_diag))
        max_val = float(off_diag[max_idx])

        # Step 2b: Check convergence.
        if max_val < tol:
            break

        p = int(upper_i[max_idx])
        q = int(upper_j[max_idx])

        # Step 2c: Compute Givens rotation angle.
        diff = a_k[p, p] - a_k[q, q]
        if abs(diff) < 1e-15:
            theta = np.pi / 4.0
        else:
            theta = 0.5 * np.arctan((2.0 * a_k[p, q]) / diff)

        cos_t = float(np.cos(theta))
        sin_t = float(np.sin(theta))

        # Step 2d: Construct Givens rotation matrix G.
        givens = np.eye(n, dtype=float)
        givens[p, p] = cos_t
        givens[q, q] = cos_t
        givens[p, q] = -sin_t
        givens[q, p] = sin_t

        # Steps 2e-2f: Similarity transform and accumulate eigenvectors.
        a_k = givens.T @ a_k @ givens
        v_k = v_k @ givens

    # Steps 3-4: Extract eigenvalues/eigenvectors and sort in ascending order.
    eigenvalues = np.diag(a_k).copy()
    order = np.argsort(eigenvalues)
    return eigenvalues[order], v_k[:, order]


def numpy_eigen(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Eigenvalue decomposition using numpy.linalg.eigh (for symmetric matrices).
    Returns (eigenvalues_sorted, eigenvectors_sorted) in ascending order.
    """
    mat = _validate_symmetric_matrix(matrix)
    n = mat.shape[0]
    if n == 0:
        return np.array([], dtype=float), np.zeros((0, 0), dtype=float)

    eigenvalues, eigenvectors = np.linalg.eigh(mat)
    order = np.argsort(eigenvalues)
    return eigenvalues[order], eigenvectors[:, order]


def count_zero_eigenvalues(
    eigenvalues: np.ndarray,
    tol: float = EIGENVALUE_TOLERANCE,
) -> int:
    """Count eigenvalues that are approximately zero."""
    eigs = np.asarray(eigenvalues, dtype=float)
    if eigs.size == 0:
        return 0
    return int(np.sum(np.abs(eigs) < tol))


def compute_eigenvalues(laplacian: np.ndarray, method: str = "auto") -> dict:
    """
    Compute eigenvalues of the Laplacian matrix.

    method: 'jacobi' for small matrices, 'numpy' for large, 'auto' selects based
    on size (<=10 uses jacobi with numpy validation).

    Returns dict:
    {
        'eigenvalues': sorted numpy array,
        'eigenvectors': corresponding eigenvectors (columns),
        'method_used': 'jacobi' or 'numpy',
        'jacobi_validated': True/False (if jacobi was validated against numpy),
        'validation_max_error': float (max absolute difference if validated),
        'zero_eigenvalue_count': int (count of eigenvalues < EIGENVALUE_TOLERANCE),
        'lambda_2': float or None (second smallest eigenvalue),
        'is_connected': bool (True if zero_eigenvalue_count == 1)
    }
    """
    if method not in {"auto", "jacobi", "numpy"}:
        raise ValueError(
            f"Unsupported method {method!r}. Expected 'auto', 'jacobi', or 'numpy'."
        )

    lap = _validate_symmetric_matrix(laplacian)
    n = lap.shape[0]

    use_jacobi = method == "jacobi" or (method == "auto" and n <= 10)

    if use_jacobi:
        method_used = "jacobi"
        # Allow enough single-element Givens rotations for degenerate small matrices (e.g. n=10).
        jacobi_iters = max(100, 25 * n * n)
        eigenvalues, eigenvectors = jacobi_eigen(lap, max_iterations=jacobi_iters)

        np_eigenvalues, _ = numpy_eigen(lap)
        validation_max_error = (
            float(np.max(np.abs(eigenvalues - np_eigenvalues))) if n > 0 else 0.0
        )
        jacobi_validated = True
    else:
        method_used = "numpy"
        eigenvalues, eigenvectors = numpy_eigen(lap)
        jacobi_validated = False
        validation_max_error = 0.0

    zero_count = count_zero_eigenvalues(eigenvalues)
    lambda_2 = float(eigenvalues[1]) if n >= 2 else None
    is_connected = bool(zero_count == 1)

    return {
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "method_used": method_used,
        "jacobi_validated": jacobi_validated,
        "validation_max_error": validation_max_error,
        "zero_eigenvalue_count": zero_count,
        "lambda_2": lambda_2,
        "is_connected": is_connected,
    }
