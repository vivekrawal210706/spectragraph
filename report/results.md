# Validation & Demonstration Results

All results in this document were obtained by executing the SpectraGraph mathematical engine (`math_engine/`), independent graph algorithms (`ds/`), REST API (`app/routes.py`), and automated test suite (`tests/`).

---

## 1. Five+ Required Demonstration Cases

The following six canonical graph structures were generated via `POST /api/graphs/sample` and evaluated via `POST /api/analyze/<graph_id>` against the live Flask + SQLite backend:

| Graph Name | Nodes ($|V|$) | Edges ($|E|$) | Zero Eigenvalues ($\lambda \approx 0$) | BFS Components | Union-Find Components | $\lambda_2$ (Algebraic Connectivity) | All Methods Agree? |
|---|---|---|---|---|---|---|---|
| Path Graph ($P_6$) | 6 | 5 | 1 | 1 | 1 | `0.2679` | Yes |
| Cycle Graph ($C_6$) | 6 | 6 | 1 | 1 | 1 | `1.0000` | Yes |
| Complete Graph ($K_5$) | 5 | 10 | 1 | 1 | 1 | `5.0000` | Yes |
| Star Graph ($S_6$) | 6 | 5 | 1 | 1 | 1 | `1.0000` | Yes |
| Disconnected Graph ($2 \times K_3$) | 6 | 6 | 2 | 2 | 2 | `0.0000` | Yes |
| Two-Community Graph | 10 | 18 | 1 | 1 | 1 | `0.5881` | Yes |

### Observations from Demonstration Cases

1. **Path ($P_6$) vs Cycle ($C_6$) vs Complete ($K_5$):** All three are connected ($1$ zero eigenvalue), and their algebraic connectivity $\lambda_2$ increases strictly with structural robustness: $0.2679 < 1.0000 < 5.0000$.
2. **Disconnected Graph ($2 \times K_3$):** Contains two disjoint triangles. The Laplacian spectrum has **2 zero eigenvalues** ($\lambda_1 = \lambda_2 = 0$), matching BFS ($2$) and Union-Find ($2$). Because $\lambda_2 = 0$, Fiedler partitioning is correctly reported as not meaningful for disconnected graphs.
3. **Method Agreement:** Across all six structures, the multiplicity of $\lambda = 0$ in $L = D - A$ matches both BFS and Union-Find component counts (`all_agree = True`).

---

## 2. Fiedler-Vector Bisection on Two-Community Graph

The 10-node Two-Community sample graph consists of two dense 5-node communities (`v1`–`v5` and `v6`–`v10`, 8 internal edges each) joined by 2 bridge edges (`(v3, v8)` and `(v5, v6)`), for a total of 18 edges.

- **Algebraic connectivity ($\lambda_2$):** `0.5881` ($> 0$, confirming the graph is connected).
- **Fiedler-vector partition (0-based node indices):**
  - **Group 1:** `[0, 1, 2, 3, 4]` (`v1`, `v2`, `v3`, `v4`, `v5`)
  - **Group 2:** `[5, 6, 7, 8, 9]` (`v6`, `v7`, `v8`, `v9`, `v10`)
- **Result:** Spectral bisection cleanly recovers the exact planted two-community structure, cutting only the 2 bridge edges.

---

## 3. Automated Test Suite Results

Command executed:

```bash
python -m pytest tests/ -v
```

Summary of observed test run:

- **Total tests collected:** 110
- **Passed:** 110 (100%)
- **Failed:** 0
- **Execution time:** 2.32s

Test coverage breakdown:
- `tests/test_matrices.py`: Adjacency, Degree, Laplacian ($L = D - A$), symmetry, zero row sums, PSD checks, and invalid matrix detection.
- `tests/test_eigenvalues.py`: Jacobi rotation method vs NumPy `eigh` cross-validation, analytical spectra ($K_3, P_2, P_4, C_4, S_4, 2\times K_3$), tolerance-based zero counting.
- `tests/test_bfs.py`: Queue-based BFS connected components across empty, single-node, connected, disconnected, and isolated-node graphs.
- `tests/test_union_find.py`: Disjoint-set Union-Find (path compression + union by rank) and cross-verification against BFS and Spectral counts.
- `tests/test_fiedler.py`: Fiedler value and spectral bisection on two-community, path, complete, disconnected, single-node, and empty graphs.
- `tests/test_database.py`: SQLite schema, cascade deletion, analysis result persistence, and transaction rollback.
- `tests/test_app.py`: All 5 Flask page routes, graph CRUD, 7 sample graphs, random graph generator, `/api/analyze/<id>`, JSON/CSV import & export, and Matplotlib PNG spectrum plot.
