# Mathematical Model — SpectraGraph

This document formalizes the graph-theoretic and linear-algebraic framework underlying **SpectraGraph** (`math_engine/`), including matrix definitions, structural proofs, eigenvalue computation via Jacobi rotations and `numpy.linalg.eigh`, null-space component theory, and Fiedler-vector spectral bisection.

---

## 1. Problem Statement

Given a network modeled as a finite graph $G = (V, E)$, two fundamental structural questions arise:

1. **Connectivity & Component Decomposition**: Is the network connected, and if not, how many isolated subnetworks (connected components) $k$ does it contain?
2. **Bottleneck Identification & Bisection**: If the network is connected, how resilient is it against disconnection, and how can its vertices be partitioned into two balanced, sparsely interconnected groups?

Classical computer science solves connectivity via discrete graph traversal (BFS/DFS) or Disjoint-Set Union (Union-Find). **SpectraGraph** investigates how **spectral graph theory** solves both connectivity counting and graph bisection purely through the eigenvalues and eigenvectors of a linear operator—the **combinatorial Graph Laplacian** $L = D - A$—and verifies numerical spectral results against discrete combinatorial algorithms.

---

## 2. Graph Mathematical Model

SpectraGraph models **simple, undirected, unweighted graphs**:

$$G = (V, E)$$

where:
- $V = \{v_0, v_1, \dots, v_{n-1}\}$ is a finite ordered set of $n = |V|$ vertices (indexed $0$ to $n-1$ internally in `math_engine/` and `ds/`, with human-readable labels such as `v1, ..., vn` in the UI).
- $E \subseteq \{\{u, v\} : u, v \in V,\; u \ne v\}$ is a set of $m = |E|$ undirected edges.

Because $G$ is **simple** and **undirected**:
- **No self-loops**: $\{v, v\} \notin E$. In `math_engine/adjacency.py` (`build_adjacency_matrix`), pairs with $i = j$ are explicitly skipped so the main diagonal remains zero.
- **No multi-edges (parallel edges)**: At most one edge exists between any pair $\{u, v\}$. In `app/routes.py` (`_extract_graph_topology`), unordered pairs $(\min(u, v), \max(u, v))$ are deduplicated before building matrices.
- **Unweighted**: Every edge carries uniform unit weight $1$.
- **Graph Density**: For $n > 1$, edge density is defined as
  $$\rho(G) = \frac{2m}{n(n - 1)} \in [0, 1],$$
  and $\rho(G) = 0$ for $n \le 1$.

---

## 3. Adjacency ($A$), Degree ($D$), and Laplacian ($L$) Matrices

### 3.1 Adjacency Matrix ($A$)

Implemented in `math_engine/adjacency.py` (`build_adjacency_matrix(n, edges)`), the adjacency matrix $A \in \mathbb{R}^{n \times n}$ is defined entrywise as:

$$A_{ij} = \begin{cases} 1, & \text{if } \{v_i, v_j\} \in E, \\ 0, & \text{otherwise.} \end{cases}$$

`math_engine/validation.py` (`validate_adjacency`) enforces four structural invariants:
1. **Square**: $A \in \mathbb{R}^{n \times n}$.
2. **Symmetric**: $A = A^T$ ($A_{ij} = A_{ji}$ for all $i, j$).
3. **Binary**: $A_{ij} \in \{0, 1\}$.
4. **Zero Diagonal**: $A_{ii} = 0$ for all $i \in \{0, \dots, n-1\}$.

### 3.2 Degree Matrix ($D$)

The **degree** of vertex $v_i$ is the number of incident edges, equal to the $i$-th row sum of $A$:

$$d_i = \deg(v_i) = \sum_{j=0}^{n-1} A_{ij}.$$

Implemented in `math_engine/degree.py` (`build_degree_matrix(adjacency)`), the degree matrix $D \in \mathbb{R}^{n \times n}$ is the diagonal matrix:

$$D = \operatorname{diag}(d_0, d_1, \dots, d_{n-1}), \qquad D_{ij} = \begin{cases} d_i, & \text{if } i = j, \\ 0, & \text{if } i \ne j. \end{cases}$$

### 3.3 Combinatorial Graph Laplacian ($L = D - A$)

Implemented in `math_engine/laplacian.py` (`build_laplacian(adjacency)`), the unnormalized combinatorial Laplacian $L \in \mathbb{R}^{n \times n}$ is:

$$L = D - A, \qquad L_{ij} = \begin{cases} d_i, & \text{if } i = j, \\ -1, & \text{if } i \ne j \text{ and } \{v_i, v_j\} \in E, \\ 0, & \text{otherwise.} \end{cases}$$

### 3.4 Fundamental Properties of $L$

`math_engine/laplacian.py` (`verify_laplacian(laplacian, tol=1e-10)`) explicitly verifies three essential linear-algebraic properties:

1. **Symmetry ($L = L^T$)**:
   Since $D$ is diagonal ($D = D^T$) and $A$ is symmetric ($A = A^T$),
   $$L^T = (D - A)^T = D^T - A^T = D - A = L.$$
   By the **Real Spectral Theorem**, all eigenvalues of $L$ are **real**, and there exists an **orthonormal eigenbasis** $\{u_1, u_2, \dots, u_n\} \subset \mathbb{R}^n$ such that $L = U \Lambda U^T$.

2. **Zero Row Sums ($L\mathbf{1} = \mathbf{0}$)**:
   Let $\mathbf{1} = (1, 1, \dots, 1)^T \in \mathbb{R}^n$. For every row $i$:
   $$(L\mathbf{1})_i = \sum_{j=0}^{n-1} L_{ij} = d_i - \sum_{j=0}^{n-1} A_{ij} = d_i - d_i = 0.$$
   Therefore, for every non-empty graph ($n \ge 1$), $\mathbf{1}$ is an eigenvector of $L$ with eigenvalue $\lambda = 0$.

3. **Positive Semi-Definiteness ($x^T L x \ge 0$)**:
   For any vector $x = (x_0, x_1, \dots, x_{n-1})^T \in \mathbb{R}^n$, expanding the quadratic form yields:
   $$x^T L x = x^T D x - x^T A x = \sum_{i=0}^{n-1} d_i x_i^2 - \sum_{i=0}^{n-1}\sum_{j=0}^{n-1} A_{ij} x_i x_j.$$
   Since each undirected edge $\{i, j\} \in E$ contributes $x_i^2$ to $d_i x_i^2$, $x_j^2$ to $d_j x_j^2$, and $-2x_i x_j$ to $-x^T A x$ (via both $(i, j)$ and $(j, i)$ entries of $A$), we obtain the sum-of-squares identity:
   $$x^T L x = \sum_{\{i, j\} \in E} (x_i - x_j)^2 \ge 0.$$
   Consequently, for any eigenpair $(\lambda, v)$ with $Lv = \lambda v$ and $\|v\|_2 = 1$:
   $$\lambda = v^T L v = \sum_{\{i, j\} \in E} (v_i - v_j)^2 \ge 0.$$
   Thus all eigenvalues are real and non-negative, ordered in SpectraGraph as:
   $$0 = \lambda_1 \le \lambda_2 \le \dots \le \lambda_n.$$

---

## 4. Eigenvalue Methods and Numerical Limitations

SpectraGraph computes the complete eigendecomposition $L = V \Lambda V^T$ in `math_engine/eigenvalues.py` using two complementary methods:

### 4.1 Jacobi Rotation Method (`jacobi_eigen`)

The **Jacobi eigenvalue algorithm** is an iterative similarity-transformation method for real symmetric matrices. Starting from $A_0 = L$ and $V_0 = I_n$, each step $k$ preserves the spectrum of $L$ via an orthogonal **Givens rotation** $G(p, q, \theta)$:

1. **Pivot Selection**: Scan the strict upper triangle ($0 \le p < q < n$) to locate the largest off-diagonal entry in magnitude:
   $$(p, q) = \arg\max_{i < j} |(A_k)_{ij}|.$$
2. **Convergence Check**: If $|(A_k)_{pq}| < \text{tol}$ (default $\text{tol} = 10^{-10}$), stop.
3. **Rotation Angle**: Choose $\theta$ so that the $(p, q)$ and $(q, p)$ entries of $A_{k+1} = G^T A_k G$ become zero. Expanding the $2 \times 2$ similarity block gives:
   $$(A_{k+1})_{pq} = \left((A_k)_{qq} - (A_k)_{pp}\right)\sin\theta\cos\theta + (A_k)_{pq}\left(\cos^2\theta - \sin^2\theta\right) = 0.$$
   Using $\sin(2\theta) = 2\sin\theta\cos\theta$ and $\cos(2\theta) = \cos^2\theta - \sin^2\theta$:
   $$\tan(2\theta) = \frac{2(A_k)_{pq}}{(A_k)_{pp} - (A_k)_{qq}} \implies \theta = \frac{1}{2}\arctan\left(\frac{2(A_k)_{pq}}{(A_k)_{pp} - (A_k)_{qq}}\right),$$
   with the special case $\theta = \frac{\pi}{4}$ when $|(A_k)_{pp} - (A_k)_{qq}| < 10^{-15}$.
4. **Givens Matrix & Update**:
   Construct $G \in \mathbb{R}^{n \times n}$ equal to $I_n$ except at rows/columns $\{p, q\}$:
   $$G_{pp} = \cos\theta, \quad G_{qq} = \cos\theta, \quad G_{pq} = -\sin\theta, \quad G_{qp} = \sin\theta.$$
   Update:
   $$A_{k+1} = G^T A_k G, \qquad V_{k+1} = V_k G.$$
   Because $G$ is orthogonal ($G^T G = I_n$), $A_{k+1}$ has identical eigenvalues to $A_k$ while monotonically decreasing the off-diagonal Frobenius norm:
   $$\sum_{i \ne j} (A_{k+1})_{ij}^2 = \sum_{i \ne j} (A_k)_{ij}^2 - 2 (A_k)_{pq}^2.$$
5. **Extraction & Sorting**: Upon termination, eigenvalues are read from $\operatorname{diag}(A_k)$, eigenvectors from the columns of $V_k$, and both are sorted in ascending order of $\lambda$.

### 4.2 NumPy Validation & Hybrid Solver Selection (`compute_eigenvalues`)

- `numpy_eigen(matrix)` calls `np.linalg.eigh` (backed by LAPACK symmetric tridiagonal reduction and divide-and-conquer / QR).
- In `compute_eigenvalues(laplacian, method="auto")`:
  - **`auto` mode**: Selects `jacobi` when $n \le 10$ (with iteration budget $\max(100, 25n^2)$) and **always validates** the result against `numpy_eigen` by computing:
    $$\text{validation\_max\_error} = \max_{1 \le i \le n} \left|\lambda_i^{\text{jacobi}} - \lambda_i^{\text{numpy}}\right|.$$
  - For $n > 10$ in `auto` mode (or `method="numpy"`), `numpy_eigen` is invoked directly for speed and stability.

### 4.3 Numerical Limitations

1. **Zero-Eigenvalue Floating-Point Tolerance (`EIGENVALUE_TOLERANCE = 1e-9`)**:
   In `count_zero_eigenvalues`, an eigenvalue is counted as zero if $|\lambda_i| < 10^{-9}$. Due to IEEE-754 floating-point rounding, true zero eigenvalues often compute as $\pm 10^{-16}$ to $\pm 10^{-13}$. Conversely, on large sparse graphs with weak connectivity—for example, a path graph $P_n$ where $\lambda_2 = 2\left(1 - \cos\frac{\pi}{n}\right) \approx \frac{\pi^2}{n^2}$—$\lambda_2$ shrinks quadratically with $n$ and could approach the tolerance threshold at very large $n$.
2. **Repeated (Degenerate) Eigenvalues**:
   Symmetric and regular graphs exhibit eigenvalues with multiplicity greater than $1$ (e.g., $K_5$ has spectrum $\{0, 5, 5, 5, 5\}$; $S_6$ has $\{0, 1, 1, 1, 1, 6\}$; the Petersen graph has $\{0, 2^5, 5^4\}$). Whenever $\lambda_2 = \lambda_3$, the $\lambda_2$-eigenspace has dimension $\ge 2$, so the Fiedler vector $v_2$ is **not unique** (any unit vector in that eigenspace orthogonal to $\mathbf{1}$ is valid), and different solvers or iteration orders can return rotated bases yielding different valid bisections.
3. **Jacobi Iteration Budget & Cost**:
   Each explicit Givens update `givens.T @ a_k @ givens` in `jacobi_eigen` multiplies dense $n \times n$ matrices ($O(n^3)$ per step) for educational clarity rather than performing $O(n)$ two-row/two-column updates. On degenerate small matrices up to $n = 10$, convergence requires up to $O(n^2)$ rotations (hence the `25 * n * n` budget in `compute_eigenvalues`).

---

## 5. Null Space Interpretation ($\ker(L)$ and Connected Components)

### Theorem (Multiplicity of Zero Eigenvalue)
Let $G = (V, E)$ be an undirected graph with Laplacian $L = D - A$ and $k$ connected components $C_1, C_2, \dots, C_k$. Then:

$$\dim(\ker(L)) = k,$$

and since $L$ is real symmetric (hence diagonalizable), the algebraic multiplicity of $\lambda = 0$ in the spectrum of $L$ equals $k$.

### Proof

1. **Characterization of $\ker(L)$**:
   Suppose $x \in \ker(L)$, so $Lx = \mathbf{0}$. Multiplying on the left by $x^T$ gives:
   $$0 = x^T L x = \sum_{\{i, j\} \in E} (x_i - x_j)^2.$$
   Because each summand $(x_i - x_j)^2 \ge 0$, every edge $\{i, j\} \in E$ must satisfy $x_i = x_j$.
   If vertices $u$ and $w$ lie in the same connected component $C_r$, there exists a path $u = u_0, u_1, \dots, u_t = w$ in $G$, implying $x_{u_0} = x_{u_1} = \dots = x_{u_t}$. Thus **every vector $x \in \ker(L)$ is constant on each connected component $C_r$**.

2. **Component Indicator Basis**:
   For each connected component $C_r$ ($r = 1, \dots, k$), define its indicator vector $\mathbf{1}_{C_r} \in \mathbb{R}^n$:
   $$(\mathbf{1}_{C_r})_i = \begin{cases} 1, & \text{if } v_i \in C_r, \\ 0, & \text{otherwise.} \end{cases}$$
   For any edge $\{i, j\} \in E$, vertices $v_i$ and $v_j$ belong to the exact same component, so $(\mathbf{1}_{C_r})_i - (\mathbf{1}_{C_r})_j = 0$. Therefore:
   $$\mathbf{1}_{C_r}^T L \mathbf{1}_{C_r} = \sum_{\{i, j\} \in E} \big((\mathbf{1}_{C_r})_i - (\mathbf{1}_{C_r})_j\big)^2 = 0.$$
   Writing $\mathbf{1}_{C_r} = \sum_{m=1}^n c_m u_m$ in an orthonormal eigenbasis $\{u_m\}$ of $L$ with eigenvalues $\lambda_m \ge 0$, we have $\sum_{m=1}^n \lambda_m c_m^2 = 0$, forcing $c_m = 0$ whenever $\lambda_m > 0$. Hence $L\mathbf{1}_{C_r} = \mathbf{0}$, so $\mathbf{1}_{C_r} \in \ker(L)$.

3. **Linear Independence & Spanning**:
   Because the components $C_1, \dots, C_k$ form a partition of $V$, the indicator vectors $\{\mathbf{1}_{C_1}, \dots, \mathbf{1}_{C_k}\}$ have mutually disjoint non-zero supports ($\mathbf{1}_{C_r}^T \mathbf{1}_{C_s} = 0$ for $r \ne s$), so they are **orthogonal and linearly independent**. Moreover, any $x \in \ker(L)$ taking constant value $\alpha_r$ on $C_r$ satisfies:
   $$x = \sum_{r=1}^k \alpha_r \mathbf{1}_{C_r}.$$
   Therefore $\{\mathbf{1}_{C_1}, \dots, \mathbf{1}_{C_k}\}$ is an orthogonal basis for $\ker(L)$, proving $\dim(\ker(L)) = k$.

### Corollaries Used in SpectraGraph
- **Connectivity Test**: $G$ is connected $\iff k = 1 \iff$ `zero_eigenvalue_count == 1` $\iff \lambda_2 > 0$.
- **Disconnected Graphs**: If $k \ge 2$, then $0 = \lambda_1 = \lambda_2 = \dots = \lambda_k$, so $\lambda_2 = 0$.

---

## 6. Fiedler-Vector Partitioning ($\lambda_2$ and Spectral Bisection)

### 6.1 Algebraic Connectivity and Rayleigh Quotient Relaxation

For a graph with $n \ge 2$ vertices, the second-smallest eigenvalue $\lambda_2(L)$ is called the **algebraic connectivity** (Fiedler, 1973), and its corresponding eigenvector $v_2$ is the **Fiedler vector**.

By the **Courant–Fischer min-max theorem**, since the first eigenvector of $L$ is $u_1 = \frac{1}{\sqrt{n}}\mathbf{1}$ with $\lambda_1 = 0$:

$$\lambda_2 = \min_{\substack{x \in \mathbb{R}^n \setminus \{\mathbf{0}\} \\ x^T \mathbf{1} = 0}} \frac{x^T L x}{x^T x} = \min_{\substack{\sum_i x_i = 0 \\ \sum_i x_i^2 = 1}} \sum_{\{i, j\} \in E} (x_i - x_j)^2.$$

This continuous minimization problem arises directly as a relaxation of the discrete **balanced minimum graph cut** problem:
- Suppose we wish to partition $V$ into two disjoint sets $(S, \bar{S})$ using an indicator vector $s \in \{-1, +1\}^n$ where $s_i = +1$ for $v_i \in S$ and $s_i = -1$ for $v_i \in \bar{S}$.
- Then $(s_i - s_j)^2 = 4$ if $\{i, j\}$ crosses between $S$ and $\bar{S}$, and $0$ otherwise, so:
  $$\operatorname{cut}(S, \bar{S}) = \frac{1}{4} s^T L s = \frac{1}{4} \sum_{\{i, j\} \in E} (s_i - s_j)^2.$$
- Balancing $|S| = |\bar{S}|$ requires $\sum_i s_i = s^T \mathbf{1} = 0$, while $\|s\|_2^2 = n$.
- Relaxing the combinatorial constraint $s \in \{-1, +1\}^n$ to real vectors $x \in \mathbb{R}^n$ with $x^T \mathbf{1} = 0$ and $\|x\|_2^2 = n$ yields the Rayleigh quotient minimization above, whose exact global minimizer is $x = \sqrt{n}\, v_2$ with optimal value $n \lambda_2$.
- Because $v_2$ minimizes $\sum_{\{i,j\}\in E} (v_2(i) - v_2(j))^2$, strongly connected vertices tend to have similar values in $v_2$ (same sign), whereas bottlenecks / sparse bridge edges bridge positive and negative coordinates.

### 6.2 Sign-Based Bisection in `math_engine/fiedler.py`

In `compute_fiedler(eigenvalues, eigenvectors)`:

1. Eigenvalues and eigenvectors are verified and sorted in ascending order so $\lambda_2 = \lambda_{\text{sorted}}[1]$ and $v_2 = V_{\text{sorted}}[:, 1]$.
2. For connected graphs with $n \ge 2$ (`abs(lambda_2) >= 1e-9` and `zero_count == 1`), vertices are partitioned by the sign of their Fiedler coordinate:
   $$\text{group}_1 = \{i \in V : v_2(i) \ge 0\}, \qquad \text{group}_2 = \{i \in V : v_2(i) < 0\}.$$

### 6.3 Special Cases Handled

`compute_fiedler` and `_bisect_with_fallback` explicitly handle three edge cases:

1. **Trivial Graphs ($n < 2$)**:
   With $0$ or $1$ vertices, bisection into two non-empty subsets is impossible. `compute_fiedler` returns `lambda_2 = None`, `fiedler_vector = None`, `partition = None`, and `can_partition = False`.
2. **Disconnected Graphs ($\lambda_2 \approx 0$ or `zero_count != 1`)**:
   If $|\lambda_2| < 10^{-9}$ or `zero_eigenvalue_count != 1`, the graph is disconnected (`is_connected = False`, `can_partition = False`, `partition = None`). Here $v_2$ lies inside $\ker(L)$ and is constant across components rather than bisecting a single component, so spectral bisection is disabled and explained to the user.
3. **Degenerate Threshold / Empty-Group Fallback (`_bisect_with_fallback`)**:
   If $v_2(i) \ge 0$ vs. $v_2(i) < 0$ ever leaves either `group_1` or `group_2` empty (for instance under extreme skew or numerical precision artifacts), `_bisect_with_fallback` shifts the split threshold to $\operatorname{median}(v_2)$ (checking $\ge / <$, then $> / \le$), and finally splits the stably sorted indices at $\lfloor n / 2 \rfloor$ if all coordinates of $v_2$ are numerically equal.
