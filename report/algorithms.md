# Algorithms, Data Structures, and Database Design — SpectraGraph

This document details the classical graph algorithms implemented alongside the spectral engine (`ds/`), the relational SQLite schema and transaction architecture (`db/`), comparative time/space complexity across all three connectivity solvers, and current engineering limitations with future directions.

---

## 1. Breadth-First Search (BFS) Connected Components (`ds/bfs.py`)

SpectraGraph uses Breadth-First Search as an exact, discrete reference algorithm to cross-validate the Laplacian null-space component count.

### 1.1 Implementation Details

The module provides two functions:
- `edges_to_adj_list(n, edges)`: Validates $n \ge 0$ and edge bounds $0 \le u, v < n$, skips self-loops ($u = v$), deduplicates undirected connections using per-vertex `set`s, and returns `{node: sorted(neighbors)}` for every vertex $0 \le i < n$ (ensuring isolated vertices appear with empty neighbor lists `[]`).
- `bfs_connected_components(n, adj_list)`: Uses `collections.deque` as a FIFO traversal queue and a `visited: set[int]` tracker. Iterating `start` from `0` to `n - 1`, each unvisited vertex triggers a new BFS sweep that identifies one full connected component, assigns `component_map[node] = comp_id`, and stores the sorted vertex list of that component.

### 1.2 Pseudocode

```text
ALGORITHM BFS-Connected-Components(n, edges)
Input:  Vertex count n >= 0, list of undirected edges E
Output: component_count, components (list of vertex lists), component_map

1.  if n == 0:
2.      return {component_count: 0, components: [], component_map: {}}
3.
4.  adj_list <- Build-Sorted-Adjacency-List(n, edges)   // ignoring self-loops, deduplicated
5.  visited <- empty set
6.  components <- empty list
7.  component_map <- empty map
8.
9.  for start = 0 to n - 1:
10.     if start in visited:
11.         continue
12.     comp_id <- length(components)
13.     component <- empty list
14.     queue <- Queue([start])
15.     visited.add(start)
16.
17.     while queue is not empty:
18.         u <- queue.pop_front()
19.         component.append(u)
20.         component_map[u] <- comp_id
21.         for each v in adj_list[u]:
22.             if 0 <= v < n and v not in visited:
23.                 visited.add(v)
24.                 queue.push_back(v)
25.
26.     components.append(sorted(component))
27.
28. return {
29.     component_count: length(components),
30.     components: components,
31.     component_map: component_map
32. }
```

### 1.3 Edge Cases Handled

- **Empty Graph ($n = 0$)**: Returns `component_count = 0`, `components = []`, and `component_map = {}` immediately.
- **Isolated Vertices**: Because `edges_to_adj_list` initializes keys for all $0 \dots n-1$ and the outer loop iterates over every vertex index, isolated nodes with degree $0$ are properly recorded as singleton components `[i]`.
- **Self-Loops & Duplicate Edges**: Self-loops are skipped during adjacency list construction, and `set` insertion deduplicates repeated undirected edges.
- **Invalid Inputs**: Negative $n$, malformed edge tuples, or out-of-range node indices raise `ValueError`.

---

## 2. Union-Find / Disjoint-Set Union (`ds/union_find.py`)

SpectraGraph implements a second independent discrete connectivity solver via the **Union-Find (Disjoint-Set Union, DSU)** data structure in `UnionFind` and its convenience wrapper `union_find_components(n, edges)`.

### 2.1 Implementation Details

- **State Representation**:
  - `parent = [0, 1, ..., n - 1]` — initially each vertex is the root of its own singleton tree.
  - `rank = [0] * n` — upper bound on tree height for balancing merges.
  - `component_count = n` — decremented by `1` whenever two distinct sets are merged.
- **Path Compression (`find(x)`)**:
  Implemented iteratively in two passes to avoid Python recursion depth limits:
  1. Walk parent pointers upward until `parent[root] == root`.
  2. Walk from `x` to `root` a second time, re-pointing every visited node's `parent` directly to `root`.
- **Union by Rank (`union(x, y)`)**:
  Attaches the root of smaller `rank` beneath the root of larger `rank`. When both roots have equal `rank`, `root_y` is attached under `root_x` and `rank[root_x]` is incremented by `1`.
- **Component Extraction (`get_components()`)**:
  Calls `find(node)` on every vertex $0 \dots n-1$, groups vertices by canonical root, sorts component lists by their smallest vertex ID, and returns `component_count`, `components`, and `component_map`.

### 2.2 Pseudocode

```text
STRUCTURE UnionFind(n)
    parent[0..n-1] <- [0, 1, ..., n-1]
    rank[0..n-1]   <- [0, 0, ..., 0]
    component_count <- n

METHOD Find(x):
1.  root <- x
2.  while parent[root] != root:
3.      root <- parent[root]
4.  while parent[x] != root:              // Iterative path compression
5.      next_parent <- parent[x]
6.      parent[x] <- root
7.      x <- next_parent
8.  return root

METHOD Union(x, y):
1.  root_x <- Find(x)
2.  root_y <- Find(y)
3.  if root_x == root_y:
4.      return False                      // Already in the same component
5.  if rank[root_x] < rank[root_y]:
6.      parent[root_x] <- root_y
7.  else if rank[root_x] > rank[root_y]:
8.      parent[root_y] <- root_x
9.  else:
10.     parent[root_y] <- root_x
11.     rank[root_x] <- rank[root_x] + 1
12. component_count <- component_count - 1
13. return True

ALGORITHM Union-Find-Components(n, edges):
1.  uf <- UnionFind(n)
2.  for each (u, v) in edges:
3.      uf.Union(u, v)
4.  return uf.Get-Components()
```

### 2.3 Edge Cases Handled

- **Empty Graph ($n = 0$)**: `UnionFind(0)` creates empty lists with `component_count = 0`; `get_components()` returns `{component_count: 0, components: [], component_map: {}}`.
- **Self-Loops**: `Union(u, u)` resolves `root_x == root_y` and returns `False` without modifying `component_count`.
- **Cycles / Redundant Edges**: Any edge connecting two vertices already in the same component returns `False` immediately, keeping `component_count` exact.
- **Bounds Validation**: `_validate_node(x)` raises `ValueError` if `x < 0` or `x >= n`.

---

## 3. Database Design (`db/database.py`)

SpectraGraph persists graphs and spectral analysis results in a local SQLite database at `db/spectragraph.db`. Every connection created by `get_db_connection()` configures `sqlite3.Row` (dictionary-like row access) and enforces referential integrity via `PRAGMA foreign_keys = ON`.

### 3.1 Relational Schema

```text
+-------------------+       1 : N       +-------------------------+
|      graphs       |------------------>|          nodes          |
+-------------------+   ON DELETE       +-------------------------+
| id (PK)           |   CASCADE         | id (PK)                 |
| name              |                   | graph_id (FK)           |
| description       |                   | label                   |
| created_at        |                   | position_x              |
| updated_at        |                   | position_y              |
+-------------------+                   +-------------------------+
         |                                         ^     ^
         | 1 : N (ON DELETE CASCADE)               |     |
         v                                         |     |
+-------------------+       1 : N       +-------------------------+
| analysis_results  |                   |          edges          |
+-------------------+                   +-------------------------+
| id (PK)           |                   | id (PK)                 |
| graph_id (FK)     |                   | graph_id (FK -> graphs) |
| adjacency_matrix  |                   | source_node_id (FK)     |
| degree_matrix     |                   | target_node_id (FK)     |
| laplacian_matrix  |                   +-------------------------+
| eigenvalues       |
| eigenvectors      |
| component_count_* |
| fiedler_value     |
| fiedler_vector    |
| group_assignments |
| method_used       |
| is_connected      |
| analysis_date     |
+-------------------+
```

#### Table Definitions

1. **`graphs`**:
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `name` (`TEXT NOT NULL`)
   - `description` (`TEXT DEFAULT ''`)
   - `created_at` (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`)
   - `updated_at` (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`)
2. **`nodes`**:
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `graph_id` (`INTEGER NOT NULL`, `FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE`)
   - `label` (`TEXT NOT NULL`)
   - `position_x` (`REAL DEFAULT 0`), `position_y` (`REAL DEFAULT 0`)
3. **`edges`**:
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `graph_id` (`INTEGER NOT NULL`, `FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE`)
   - `source_node_id` (`INTEGER NOT NULL`, `FOREIGN KEY (source_node_id) REFERENCES nodes(id)`)
   - `target_node_id` (`INTEGER NOT NULL`, `FOREIGN KEY (target_node_id) REFERENCES nodes(id)`)
4. **`analysis_results`**:
   - `id` (`INTEGER PRIMARY KEY AUTOINCREMENT`)
   - `graph_id` (`INTEGER NOT NULL`, `FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE`)
   - Serialized JSON text columns: `adjacency_matrix`, `degree_matrix`, `laplacian_matrix`, `eigenvalues`, `eigenvectors`, `fiedler_vector`, `group_assignments`
   - Scalar metrics: `component_count_spectral` (`INTEGER`), `component_count_bfs` (`INTEGER`), `component_count_union_find` (`INTEGER`), `fiedler_value` (`REAL`), `method_used` (`TEXT DEFAULT 'auto'`), `is_connected` (`INTEGER DEFAULT 0`), `analysis_date` (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`)

`init_db()` also performs lightweight schema evolution via `_ensure_column()` (`PRAGMA table_info` + `ALTER TABLE ... ADD COLUMN`) so existing databases automatically gain any newly introduced columns without manual migration scripts.

### 3.2 Foreign Keys, Cascade Deletion, and Deletion Ordering

All child tables (`nodes`, `edges`, `analysis_results`) carry `FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE`. However, `edges.source_node_id` and `edges.target_node_id` reference `nodes(id)` **without** `ON DELETE CASCADE`.

Because `PRAGMA foreign_keys = ON` is active on every connection, deleting from `nodes` (or cascading from `graphs` into `nodes`) while `edges` still reference those `nodes(id)` rows could trigger a foreign-key constraint violation depending on SQLite cascade evaluation order. Therefore:
- `delete_graph(graph_id)` explicitly deletes `FROM edges WHERE graph_id = ?` before deleting `FROM graphs WHERE id = ?` (which then cascades cleanly to `nodes` and `analysis_results`).
- `update_graph_data(...)` similarly runs `DELETE FROM edges WHERE graph_id = ?` before `DELETE FROM nodes WHERE graph_id = ?` prior to re-inserting updated nodes and edges.

### 3.3 Transaction Safety & Serialization

- **Atomic Transactions**: Every write operation (`init_db`, `create_graph`, `save_graph_data`, `update_graph`, `update_graph_data`, `delete_graph`, `save_analysis_result`) executes inside a `with conn:` transaction block followed by `finally: conn.close()`. Any exception rolls back partial inserts/deletes automatically.
- **Flexible Endpoint Resolution**: `_insert_nodes_and_edges` maps incoming edge endpoints across external node `id`s, 0-based vertex indices, or node `label`s within the same atomic transaction.
- **JSON Serialization**: `_to_json_safe` and `_serialize_json_field` convert NumPy arrays/scalars into JSON text on write, and `_deserialize_analysis_row` parses those JSON columns back into Python lists/structures on read.

---

## 4. Time and Space Complexity Comparison

Let $n = |V|$ be the number of vertices, $m = |E|$ be the number of edges, and $\alpha(n)$ be the inverse Ackermann function (for any practical $n$, $\alpha(n) \le 4$).

| Method | Module | Time Complexity | Space Complexity | Exactness | Additional Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Laplacian Spectral (`numpy_eigen`)** | `math_engine/` | $O(n^3)$ | $O(n^2)$ | Numerical ($\|\lambda\| < 10^{-9}$) | Full spectrum $\{\lambda_i\}$, $\lambda_2$, Fiedler vector $v_2$, bisection |
| **Laplacian Spectral (`jacobi_eigen`)** | `math_engine/` | $O(n^3)$ per Givens step; up to $O(n^5)$ over $25n^2$ steps* | $O(n^2)$ | Numerical ($\text{tol} = 10^{-10}$, $\|\lambda\| < 10^{-9}$) | Transparent step-by-step rotations; validated vs. `numpy_eigen` for $n \le 10$ |
| **Breadth-First Search (BFS)** | `ds/bfs.py` | $O(n + m \log \Delta)$ to build sorted adj list; $O(n + m)$ traversal ($O(V + E)$) | $O(n + m)$ ($O(V + E)$) | Exact | Explicit component lists and node-to-component mapping |
| **Union-Find (DSU)** | `ds/union_find.py` | $O((n + m)\,\alpha(n))$ ($O((V + E)\,\alpha(V))$) | $O(n)$ auxiliary ($O(V)$) | Exact | Dynamic incremental edge merging, `connected(u, v)`, component sets |

*\*Note on Jacobi complexity*: Standard textbook Jacobi with $O(n)$ selective row/column updates requires $O(n^3)$ per sweep. In `math_engine/eigenvalues.py`, `jacobi_eigen` performs `givens.T @ a_k @ givens` ($O(n^3)$ per single rotation) for transparency and restricts `auto` mode to $n \le 10$ (where $n^3 = 1000$ operations takes sub-millisecond time).

### Practical Trade-Offs

- **Union-Find** is asymptotically optimal in memory ($O(V)$) and ideal for streaming or dynamically arriving edges ($O((V + E)\alpha(V))$).
- **BFS** runs in linear $O(V + E)$ traversal time and directly produces explicit adjacency lists and layer-by-layer graph distances.
- **Spectral Analysis** is dramatically more expensive ($O(n^3)$ time, $O(n^2)$ space), so it is unnecessary if *only* component counts are needed—but it uniquely yields **continuous structural invariants** ($\lambda_2$ bottleneck strength and Fiedler-vector community bisection) that neither BFS nor Union-Find can compute.

---

## 5. Limitations and Future Improvements

### Current Limitations

1. **Dense $O(n^2)$ / $O(n^3)$ Bottleneck**: Storing full $n \times n$ NumPy matrices and computing all $n$ eigenpairs restricts interactive scalability to small and medium graphs.
2. **Simple, Undirected, Unweighted Model**: Weighted edges ($w_{ij} > 0$), self-loops, multi-edges, and directed graphs are not supported.
3. **Two-Way Bisection Only**: `compute_fiedler` only partitions connected graphs into two sets using $v_2$, rather than generalizing to $k$-way community clustering.
4. **Numerical Zero Thresholding**: Relying on `EIGENVALUE_TOLERANCE = 1e-9` can become sensitive on huge sparse graphs with small $\lambda_2$ (e.g., long paths where $\lambda_2 \approx \pi^2 / n^2$).
5. **No Dynamic/Incremental Spectral Updates**: Editing a single edge requires rebuilding $A, D, L$ and recomputing the entire eigendecomposition from scratch.

### Future Improvements

1. **Sparse Eigensolvers**: Represent $A$ and $L$ using `scipy.sparse.csr_matrix` and compute only the lowest $k + 1$ eigenvalues via iterative **Lanczos / ARPACK** (`scipy.sparse.linalg.eigsh`), reducing memory to $O(V + E)$ and runtime substantially for sparse graphs.
2. **Normalized & Weighted Laplacians**: Add support for weighted edges ($A_{ij} = w_{ij}$), the **Symmetric Normalized Laplacian** ($L_{\text{sym}} = D^{-1/2} L D^{-1/2}$), and the **Random-Walk Laplacian** ($L_{\text{rw}} = D^{-1} L$) to prevent high-degree hubs from skewing spectral cuts, as well as Chung's **Directed Laplacian**.
3. **Multi-Way Spectral Clustering ($k$-way)**: Compute the $k$ smallest eigenvectors $v_1, \dots, v_k$ and apply **$k$-means** clustering in the spectral embedding space (Ng–Jordan–Weiss algorithm) along with RatioCut/NCut quality metrics and Cheeger constant bounds.
4. **Optimized $O(n)$ Jacobi Updates**: Replace full `givens.T @ a_k @ givens` matrix multiplication in `jacobi_eigen` with $O(n)$ in-place updates restricted to rows and columns $p$ and $q$.
5. **Interactive Eigenvalue Exploration & Benchmark Suite**: Add side-by-side timing instrumentation in `/api/analyze/<id>` to log empirical wall-clock scaling across Spectral, BFS, and Union-Find as $n$ grows.
