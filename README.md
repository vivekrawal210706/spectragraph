# SpectraGraph — Spectral Graph Connectivity Analyzer

**Project 14 · BTech Computer Science — Linear Algebra**

SpectraGraph is an interactive full-stack mathematical web application that bridges **spectral graph theory**, **numerical linear algebra**, and **classical discrete graph algorithms**. Given an undirected simple graph $G = (V, E)$, SpectraGraph constructs its Adjacency ($A$), Degree ($D$), and combinatorial Laplacian ($L = D - A$) matrices, computes its eigenvalue spectrum and eigenvectors, determines graph connectivity from the null space of $L$, cross-checks the connected-component count against **Breadth-First Search (BFS)** and **Union-Find**, and performs **Fiedler-vector ($\lambda_2$) spectral bisection** with interactive visual and database support.

---

## 1. Project Overview

In classical discrete mathematics, graph connectivity is found using traversal (BFS/DFS) or Disjoint-Set Union (Union-Find). Spectral graph theory provides an algebraic alternative grounded in linear algebra:

- Every simple undirected graph $G = (V, E)$ corresponds to a real symmetric, positive semi-definite Laplacian matrix $L = D - A$.
- The multiplicity of the eigenvalue $\lambda = 0$ (equivalently, $\dim(\ker(L))$) equals the exact number of connected components $k$.
- The second-smallest eigenvalue $\lambda_2$ (**algebraic connectivity**) is strictly positive if and only if $G$ is connected, and its corresponding eigenvector $v_2$ (the **Fiedler vector**) induces a natural two-way partition (spectral bisection) of the graph.

SpectraGraph provides an end-to-end interactive environment to build or import graphs, inspect matrices and spectral plots, verify component counts across three independent paradigms, visualize Fiedler bisections, and persist both graphs and analysis snapshots in SQLite.

---

## 2. Features

- **Interactive Graph Builder (`/graph-builder`)**:
  - Cytoscape.js canvas to add, drag, inspect, rename, and delete vertices and undirected edges.
  - Live vertex count ($|V|$), edge count ($|E|$), and graph density $\rho = \frac{2|E|}{|V|(|V|-1)}$ statistics, plus layout re-organization and keyboard shortcuts (`Delete`/`Backspace`, `Esc`).
- **7 Built-in Sample Topologies & Random Erdős–Rényi Generator**:
  - Canonical sample graphs (`POST /api/graphs/sample`): **Path Graph ($P_6$)**, **Cycle Graph ($C_6$)**, **Complete Graph ($K_5$)**, **Star Graph ($S_6$)**, **Disconnected Graph ($K_3 + K_3$)**, **Two-Community Graph** (10 vertices, 2 bridge edges), and **Petersen Graph** (10 vertices, 15 edges).
  - Erdős–Rényi random graph generator $G(n, p)$ (`POST /api/graphs/random`) with configurable vertex count ($2 \le n \le 100$ in API; $2 \le n \le 50$ in UI dialog) and edge probability $p \in [0, 1]$.
- **JSON & CSV Import / Export**:
  - Import graphs from `.json` or `.csv` edge-list files (`POST /api/graphs/import`).
  - Export saved graphs to JSON or CSV (`GET /api/graphs/<id>/export?format=json|csv`) from either the Graph Builder or the Saved Graphs view (`/saved-graphs`).
- **Matrix Construction & Structural Validation (`math_engine/`)**:
  - Constructs the Adjacency matrix ($A$), Degree matrix ($D$), and combinatorial Graph Laplacian ($L = D - A$).
  - Programmatically verifies symmetry ($L = L^T$), zero row sums ($L\mathbf{1} = \mathbf{0}$), positive semi-definiteness ($\lambda_i \ge 0$), binary/zero-diagonal adjacency, and matrix consistency.
- **Dual Eigenvalue Decomposition (Jacobi Rotation + NumPy `eigh`)**:
  - Transparent educational **Jacobi rotation** solver (`jacobi_eigen`) using iterative Givens similarity transforms, paired with `numpy.linalg.eigh` (`numpy_eigen`).
  - In `auto` mode, graphs with $n \le 10$ use Jacobi decomposition cross-validated against NumPy (`validation_max_error`), while graphs with $n > 10$ use `numpy.linalg.eigh`.
- **Three-Method Connectivity Comparison**:
  - Compares connected component counts from **Spectral Nullity** ($|\lambda_i| < 10^{-9}$), **Breadth-First Search** (`ds/bfs.py`), and **Union-Find** with path compression and union by rank (`ds/union_find.py`), flagging agreement or discrepancies.
- **Fiedler-Vector Spectral Bisection**:
  - Computes $\lambda_2$ and $v_2$ (`math_engine/fiedler.py`), assigns connected vertices ($n \ge 2$) into `group_1` ($v_2(i) \ge 0$) and `group_2` ($v_2(i) < 0$, with median/index fallbacks if needed), and renders side-by-side **Before partition** and **After partition** Cytoscape.js views.
- **Matplotlib Eigenvalue Spectrum Plot**:
  - Generates a dark-themed Laplacian eigenvalue bar chart PNG (`GET /api/graphs/<id>/eigenvalue-plot`), highlighting zero eigenvalues ($\lambda \approx 0$) in red and positive eigenvalues ($\lambda > 0$) in violet.
- **Relational SQLite Persistence (`db/database.py`)**:
  - Persists graphs, node labels and coordinates, edges, and full analysis snapshots (matrices, eigenvalues, eigenvectors, component counts, Fiedler data) in `db/spectragraph.db`.

---

## 3. Technologies Used

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3 | Core application, mathematical algorithms, data structures |
| **Web Framework** | Flask (`>=3.0`) | Blueprint routing, Jinja2 template rendering, REST API |
| **Numerical Computing** | NumPy (`>=1.26`) | Matrix operations, Jacobi array arithmetic, `numpy.linalg.eigh` validation |
| **Plotting** | Matplotlib (`>=3.8`) | Server-side Agg rendering of Laplacian eigenvalue spectrum PNG charts |
| **Database** | SQLite 3 (`sqlite3`) | Local relational persistence with foreign keys and atomic transactions |
| **Frontend UI** | HTML5, CSS3, JavaScript (ES6+) | Multi-page dark UI, fetch API integration, dynamic tables & observations |
| **Graph Visualization** | Cytoscape.js (`3.28.1` via CDN) | Interactive graph editor and spectral bisection comparison canvases |
| **Testing** | Pytest (`>=8.0`) | Automated Flask client and SQLite persistence tests |

---

## 4. Folder Structure

```text
spectragraph/
├── app.py                         # Flask application factory (create_app) and dev server entry point
├── requirements.txt               # Python package dependencies
├── README.md                      # Project documentation
│
├── app/
│   ├── __init__.py                # Flask app package initializer
│   ├── routes.py                  # Web page routes and REST API endpoints
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css         # Application styling
│   │   └── js/
│   │       ├── main.js            # Shared navigation, toast notifications, delete helper
│   │       ├── graph_builder.js   # Cytoscape.js interactive builder, samples, random, import/export
│   │       └── analysis.js        # Spectral analysis runner, matrix tables, Fiedler bisection views
│   └── templates/
│       ├── base.html              # Shared sidebar layout and base template
│       ├── index.html             # Dashboard (/) with database stats and recent graphs
│       ├── graph_builder.html     # Interactive Graph Builder (/graph-builder)
│       ├── analysis.html          # Spectral Analysis dashboard (/analysis)
│       ├── saved_graphs.html      # Saved graphs management and export (/saved-graphs)
│       └── about.html             # Mathematical overview & project guide (/about)
│
├── math_engine/
│   ├── __init__.py                # Public math_engine exports
│   ├── adjacency.py               # Adjacency matrix builder (build_adjacency_matrix)
│   ├── degree.py                  # Degree matrix builder (build_degree_matrix)
│   ├── laplacian.py               # Laplacian L = D - A and property checks (verify_laplacian)
│   ├── eigenvalues.py             # Jacobi rotation solver, NumPy eigh, zero-eigenvalue counter
│   ├── fiedler.py                 # Algebraic connectivity lambda_2 and Fiedler bisection
│   └── validation.py              # Structural validation across A, D, and L
│
├── ds/
│   ├── __init__.py                # Public ds exports
│   ├── bfs.py                     # Edge-list to adjacency-list conversion and BFS components
│   └── union_find.py              # Disjoint-Set Union (path compression + union by rank)
│
├── db/
│   ├── __init__.py                # Database exports (init_db, get_db_connection)
│   ├── database.py                # SQLite schema DDL, migrations, transactions, CRUD operations
│   └── spectragraph.db            # SQLite database file (created/updated on init_db)
│
├── report/
│   ├── mathematical_model.md      # Formal linear algebra model, proofs, and numerical analysis
│   └── algorithms.md              # BFS, Union-Find, SQLite schema, complexity, and future work
│
└── tests/
    ├── __init__.py                # Test package initializer
    └── test_app.py                # Flask & SQLite integration tests with temporary DB fixture
```

---

## 5. Installation Instructions

### Prerequisites
- Python **3.10+** installed and available on your `PATH`.
- `pip` package manager.
- Internet access in the browser when opening the web UI (required to load Cytoscape.js `3.28.1` and Google Fonts from CDN).

### Setup Steps

1. **Navigate to the project directory**:
   ```bash
   cd spectragraph
   ```

2. **Create and activate a virtual environment**:
   ```powershell
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   This installs `flask>=3.0`, `numpy>=1.26`, `matplotlib>=3.8`, and `pytest>=8.0`.

---

## 6. How to Run the Project

Start the Flask development server from the `spectragraph/` root directory:

```bash
python app.py
```

On startup, `create_app()` automatically initializes `db/spectragraph.db` via `init_db()` and starts the server at:

- **Application URL**: [http://localhost:5000](http://localhost:5000)

### Available Web Pages
- `/` — **Dashboard**: Database totals, quick actions, and recent graphs.
- `/graph-builder` — **Graph Builder**: Visual graph editor, sample/random generators, JSON/CSV import & export.
- `/analysis` — **Spectral Analysis**: Matrices ($A, D, L$), eigenvalues, Matplotlib spectrum plot, BFS/Union-Find comparison, and Fiedler bisection.
- `/saved-graphs` — **Saved Graphs**: View, re-open, analyze, export, or delete persisted graphs.
- `/about` — **About Project**: Concise conceptual reference on spectral graph theory.

---

## 7. How to Run Tests

Run the Pytest suite from inside `spectragraph/`:

```bash
python -m pytest tests/ -v
```

`tests/test_app.py` configures an isolated temporary SQLite database per test using `monkeypatch` on `db.database.DB_PATH`, leaving `db/spectragraph.db` untouched.

---

## 8. Example Usage

### A. Building or Loading a Graph & Running Spectral Analysis

1. Open `/graph-builder` in your browser.
2. Load a sample topology from **Sample Graphs**, such as **Two-Community Graph** (10 vertices divided into two dense 5-node clusters connected by bridge edges `(v3, v8)` and `(v5, v6)`), or manually place nodes with **Add Node** and connect them with **Add Edge**.
3. Click **Analyse** (this saves the graph via `POST /api/graphs` and opens `/analysis?graph_id=<id>`, which calls `POST /api/analyze/<id>`).
4. Review the generated output:
   - **Matrices ($A$, $D$, $L$)**: Confirm $L = D - A$ is symmetric with zero row sums.
   - **Eigenvalues & Plot**: Check the zero-eigenvalue count and view the Matplotlib spectrum bar chart.
   - **Connected Components**: Verify that Spectral, BFS, and Union-Find all agree on the component count $k$.

Alternatively, via the REST API:
```bash
# 1. Create a sample Two-Community Graph
curl -X POST http://localhost:5000/api/graphs/sample \
  -H "Content-Type: application/json" \
  -d '{"type": "two_community"}'

# 2. Run spectral + BFS + Union-Find analysis (replace <graph_id> with returned ID)
curl -X POST http://localhost:5000/api/analyze/<graph_id> \
  -H "Content-Type: application/json" \
  -d '{"method": "auto"}'
```

### B. Interpreting $\lambda_2$ and Fiedler Bisection

- **Disconnected graph ($\lambda_2 = 0$, e.g., `Disconnected Graph` $K_3 + K_3$)**:
  - Two eigenvalues satisfy $|\lambda| < 10^{-9}$ (`zero_eigenvalue_count = 2`).
  - `is_connected = False` and `can_partition = False`: SpectraGraph explains that Fiedler bisection is not meaningful because the graph already consists of multiple disconnected components.
- **Weakly connected modular graph (small $\lambda_2 > 0$, e.g., `Two-Community Graph` or `Path Graph P6`)**:
  - Exactly one zero eigenvalue ($\lambda_1 = 0$), so the graph is connected.
  - Because $\lambda_2$ is relatively small, there is a narrow bottleneck between regions. The **Fiedler vector** $v_2$ assigns positive values to one cluster and negative values to the other, cleanly splitting the **Two-Community Graph** across its two bridge edges into `group_1` (`v1`–`v5`) and `group_2` (`v6`–`v10`).
- **Strongly connected graph (large $\lambda_2$, e.g., `Complete Graph K5`)**:
  - $K_5$ has Laplacian spectrum $\{0, 5, 5, 5, 5\}$, giving maximum algebraic connectivity $\lambda_2 = 5.0 = n$.

### C. JSON and CSV Import Formats

You can import graphs from the Graph Builder **Import** button or `POST /api/graphs/import`.

#### JSON Format
Nodes may specify `id`, `label`, and optional `x`/`y` (`position_x`/`position_y`) coordinates, and edges reference node `id`, 0-based index, or `label`:
```json
{
  "name": "Bridge Example",
  "description": "Two triangles connected by a single bridge edge",
  "nodes": [
    {"id": 0, "label": "v1", "x": 150, "y": 200},
    {"id": 1, "label": "v2", "x": 150, "y": 320},
    {"id": 2, "label": "v3", "x": 250, "y": 260},
    {"id": 3, "label": "v4", "x": 390, "y": 260},
    {"id": 4, "label": "v5", "x": 490, "y": 200},
    {"id": 5, "label": "v6", "x": 490, "y": 320}
  ],
  "edges": [
    {"source": 0, "target": 1},
    {"source": 1, "target": 2},
    {"source": 2, "target": 0},
    {"source": 2, "target": 3},
    {"source": 3, "target": 4},
    {"source": 4, "target": 5},
    {"source": 5, "target": 3}
  ]
}
```
*(Compact formats with string node lists or `[source, target]` edge pairs are also accepted by `_parse_json_import`.)*

#### CSV Edge-List Format
Two non-empty columns per row representing undirected edges by node label. An optional header row (`source,target`, `src,tgt`, `u,v`, `from,to`, `node1,node2`, or `source_label,target_label`) is automatically recognized and skipped:
```csv
source,target
v1,v2
v2,v3
v3,v1
v3,v4
v4,v5
v5,v6
v6,v4
```
When importing CSV, SpectraGraph automatically arranges unique labels in a circular 2D layout.

---

## 9. Mathematical Methods

SpectraGraph implements the following core linear-algebraic pipeline (detailed proofs and derivations are in [`report/mathematical_model.md`](report/mathematical_model.md) and [`report/algorithms.md`](report/algorithms.md)):

1. **Graph Laplacian ($L = D - A$)**:
   - Constructed from the symmetric binary adjacency matrix $A$ and diagonal degree matrix $D_{ii} = \sum_j A_{ij}$.
   - Guaranteed symmetric ($L = L^T$), zero row-sum ($L\mathbf{1} = \mathbf{0}$), and positive semi-definite since $x^T L x = \sum_{(i,j)\in E}(x_i - x_j)^2 \ge 0$.
2. **Jacobi Rotation Decomposition**:
   - Applies iterative orthogonal Givens rotations $A_{k+1} = G^T A_k G$ targeting the largest off-diagonal entry $|A_{pq}|$ until $\max |A_{pq}| < 10^{-10}$, accumulating eigenvectors in $V_{k+1} = V_k G$.
3. **Null Space Multiplicity ($\dim(\ker(L))$)**:
   - A vector $x$ satisfies $Lx = \mathbf{0}$ iff $x$ is constant on every connected component. Counting eigenvalues with $|\lambda_i| < 10^{-9}$ therefore yields the exact component count $k$.
4. **Fiedler Vector ($v_2$)**:
   - Minimizes the Rayleigh quotient $\frac{x^T L x}{x^T x}$ over vectors orthogonal to $\mathbf{1}$, providing a continuous relaxation of balanced minimum graph cut. Vertices are bisected by the sign of $v_2(i)$.

---

## 10. Known Limitations

- **$O(n^3)$ Eigendecomposition Scaling**: Dense matrix construction ($O(n^2)$ memory) and symmetric eigendecomposition ($O(n^3)$ time) are designed for small-to-medium educational/analytical graphs rather than large networks ($n \gg 1000$).
- **Jacobi Solver Restriction in `auto` Mode**: In `auto` mode (`compute_eigenvalues`), Jacobi rotation is restricted to graphs with $n \le 10$ (with iteration cap $\max(100, 25n^2)$) and validated against NumPy; graphs with $n > 10$ automatically use `numpy.linalg.eigh`. Calling `method="jacobi"` on large dense matrices is computationally expensive because each Givens update performs full $n \times n$ matrix multiplication.
- **Simple Undirected Unweighted Graphs Only**: Self-loops ($u = v$) are ignored (`build_adjacency_matrix`, `edges_to_adj_list`), parallel/duplicate edges are deduplicated in `_extract_graph_topology`, and neither edge weights nor directed arcs are modeled.
- **Floating-Point Tolerance Sensitivity**: Zero eigenvalues are detected via $|\lambda_i| < 10^{-9}$ (`EIGENVALUE_TOLERANCE`). On very large sparse paths or poorly conditioned topologies where $\lambda_2 \to 0$, floating-point roundoff can blur the distinction between near-zero positive eigenvalues and exact zeros—making the included BFS and Union-Find cross-checks essential.
- **UI & Generator Bounds**: Random Erdős–Rényi generation is bounded to $2 \le n \le 100$ in `/api/graphs/random` ($2 \le n \le 50$ in the UI dialog), HTML matrix tables display only the top-left $15 \times 15$ submatrix when $n > 15$, and the frontend loads Cytoscape.js from a public CDN.
