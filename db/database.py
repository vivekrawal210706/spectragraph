"""SQLite database access layer for SpectraGraph.

Manages relational persistence for graphs, nodes, edges, and spectral analysis results.
"""

import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "spectragraph.db")

_JSON_ANALYSIS_FIELDS = (
    "adjacency_matrix",
    "degree_matrix",
    "laplacian_matrix",
    "eigenvalues",
    "eigenvectors",
    "fiedler_vector",
    "group_assignments",
)


def get_db_connection() -> sqlite3.Connection:
    """Create and return a SQLite connection with foreign keys enabled and Row factory."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """Add a column to an existing table if it is missing (lightweight migration)."""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cursor.fetchall()}
    if column not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    """Initialize the database schema and migrate any missing columns on existing tables."""
    conn = get_db_connection()
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS graphs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    position_x REAL DEFAULT 0,
                    position_y REAL DEFAULT 0,
                    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id INTEGER NOT NULL,
                    source_node_id INTEGER NOT NULL,
                    target_node_id INTEGER NOT NULL,
                    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_node_id) REFERENCES nodes(id),
                    FOREIGN KEY (target_node_id) REFERENCES nodes(id)
                );

                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_id INTEGER NOT NULL,
                    adjacency_matrix TEXT,
                    degree_matrix TEXT,
                    laplacian_matrix TEXT,
                    eigenvalues TEXT,
                    eigenvectors TEXT,
                    component_count_spectral INTEGER,
                    component_count_bfs INTEGER,
                    component_count_union_find INTEGER,
                    fiedler_value REAL,
                    fiedler_vector TEXT,
                    group_assignments TEXT,
                    method_used TEXT DEFAULT 'auto',
                    is_connected INTEGER DEFAULT 0,
                    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (graph_id) REFERENCES graphs(id) ON DELETE CASCADE
                );
                """
            )
            cursor = conn.cursor()
            _ensure_column(cursor, "nodes", "position_x", "REAL DEFAULT 0")
            _ensure_column(cursor, "nodes", "position_y", "REAL DEFAULT 0")
            _ensure_column(cursor, "analysis_results", "adjacency_matrix", "TEXT")
            _ensure_column(cursor, "analysis_results", "degree_matrix", "TEXT")
            _ensure_column(cursor, "analysis_results", "laplacian_matrix", "TEXT")
            _ensure_column(cursor, "analysis_results", "eigenvectors", "TEXT")
            _ensure_column(cursor, "analysis_results", "fiedler_value", "REAL")
            _ensure_column(cursor, "analysis_results", "fiedler_vector", "TEXT")
            _ensure_column(cursor, "analysis_results", "group_assignments", "TEXT")
            _ensure_column(cursor, "analysis_results", "method_used", "TEXT DEFAULT 'auto'")
            _ensure_column(cursor, "analysis_results", "is_connected", "INTEGER DEFAULT 0")
            _ensure_column(
                cursor,
                "analysis_results",
                "analysis_date",
                "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            )
    finally:
        conn.close()


def _to_json_safe(value: Any) -> Any:
    """Recursively convert numpy arrays/scalars and tuples to JSON-serializable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "tolist"):
        return _to_json_safe(value.tolist())
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return str(value)


def _serialize_json_field(value: Any) -> Optional[str]:
    """Serialize a structured field (list, dict, ndarray) into a JSON string for SQLite."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(_to_json_safe(value))


def _deserialize_analysis_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert an analysis_results SQLite row into a dict with parsed JSON fields."""
    data = dict(row)
    for field in _JSON_ANALYSIS_FIELDS:
        raw = data.get(field)
        if isinstance(raw, str):
            try:
                data[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
    if "is_connected" in data and data["is_connected"] is not None:
        data["is_connected"] = bool(data["is_connected"])
    return data


def _insert_nodes_and_edges(
    cursor: sqlite3.Cursor,
    graph_id: int,
    nodes_list: Optional[List[Any]],
    edges_list: Optional[List[Dict[str, Any]]],
) -> Tuple[List[int], int]:
    """Insert nodes and edges for a graph, resolving index, external id, or label endpoints."""
    node_ids: List[int] = []
    ext_id_to_db_id: Dict[Any, int] = {}
    label_to_db_id: Dict[str, int] = {}
    has_external_ids = False

    for idx, node in enumerate(nodes_list or []):
        if isinstance(node, dict):
            label = str(node.get("label", f"v{idx + 1}"))
            pos_x = float(node.get("position_x", node.get("x", 0)) or 0)
            pos_y = float(node.get("position_y", node.get("y", 0)) or 0)
            ext_id = node.get("id")
        else:
            label = str(node)
            pos_x = 0.0
            pos_y = 0.0
            ext_id = None

        cursor.execute(
            "INSERT INTO nodes (graph_id, label, position_x, position_y) VALUES (?, ?, ?, ?)",
            (graph_id, label, pos_x, pos_y),
        )
        db_id = cursor.lastrowid
        node_ids.append(db_id)

        if ext_id is not None:
            has_external_ids = True
            ext_id_to_db_id[ext_id] = db_id
            ext_id_to_db_id[str(ext_id)] = db_id
        if label not in label_to_db_id:
            label_to_db_id[label] = db_id

    def resolve_node(ref: Any) -> Optional[int]:
        if ref is None:
            return None
        if has_external_ids and ref in ext_id_to_db_id:
            return ext_id_to_db_id[ref]
        if has_external_ids and str(ref) in ext_id_to_db_id:
            return ext_id_to_db_id[str(ref)]
        if isinstance(ref, int) and not isinstance(ref, bool):
            if 0 <= ref < len(node_ids):
                return node_ids[ref]
        if isinstance(ref, str):
            stripped = ref.strip()
            if stripped.isdigit():
                idx_val = int(stripped)
                if 0 <= idx_val < len(node_ids):
                    return node_ids[idx_val]
            if stripped in label_to_db_id:
                return label_to_db_id[stripped]
        return None

    edge_count = 0
    for edge in edges_list or []:
        if not isinstance(edge, dict):
            continue
        raw_src = edge.get("source", edge.get("source_node_id"))
        raw_tgt = edge.get("target", edge.get("target_node_id"))
        src_db_id = resolve_node(raw_src)
        tgt_db_id = resolve_node(raw_tgt)
        if src_db_id is not None and tgt_db_id is not None:
            cursor.execute(
                "INSERT INTO edges (graph_id, source_node_id, target_node_id) VALUES (?, ?, ?)",
                (graph_id, src_db_id, tgt_db_id),
            )
            edge_count += 1

    return node_ids, edge_count


def create_graph(name: str, description: str = "") -> int:
    """Insert a new graph record and return its generated ID."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO graphs (name, description, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (name, description or ""),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_graphs() -> List[Dict[str, Any]]:
    """Retrieve all graphs with node, edge, and analysis counts ordered by updated_at desc."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                g.id,
                g.name,
                g.description,
                g.created_at,
                g.updated_at,
                (SELECT COUNT(*) FROM nodes n WHERE n.graph_id = g.id) AS node_count,
                (SELECT COUNT(*) FROM edges e WHERE e.graph_id = g.id) AS edge_count,
                (SELECT COUNT(*) FROM analysis_results a WHERE a.graph_id = g.id) AS analysis_count
            FROM graphs g
            ORDER BY g.updated_at DESC, g.id DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_graph(graph_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single graph by ID along with its associated nodes and edges."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, created_at, updated_at FROM graphs WHERE id = ?",
            (graph_id,),
        )
        graph = cursor.fetchone()
        if not graph:
            return None

        cursor.execute(
            """
            SELECT id, label, position_x, position_y
            FROM nodes
            WHERE graph_id = ?
            ORDER BY id ASC
            """,
            (graph_id,),
        )
        nodes = []
        for row in cursor.fetchall():
            node_dict = dict(row)
            node_dict["x"] = node_dict["position_x"]
            node_dict["y"] = node_dict["position_y"]
            nodes.append(node_dict)

        cursor.execute(
            """
            SELECT id, source_node_id, target_node_id
            FROM edges
            WHERE graph_id = ?
            ORDER BY id ASC
            """,
            (graph_id,),
        )
        edges = []
        for row in cursor.fetchall():
            edge_dict = dict(row)
            edge_dict["source"] = edge_dict["source_node_id"]
            edge_dict["target"] = edge_dict["target_node_id"]
            edges.append(edge_dict)

        return {
            "id": graph["id"],
            "name": graph["name"],
            "description": graph["description"],
            "created_at": graph["created_at"],
            "updated_at": graph["updated_at"],
            "nodes": nodes,
            "edges": edges,
        }
    finally:
        conn.close()


def save_graph_data(
    name: str,
    description: str,
    nodes_list: List[Dict[str, Any]],
    edges_list: List[Dict[str, Any]],
) -> int:
    """Save a complete graph with nodes and edges inside a single atomic transaction."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO graphs (name, description, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (name, description or ""),
            )
            graph_id = cursor.lastrowid
            _insert_nodes_and_edges(cursor, graph_id, nodes_list, edges_list)
            return graph_id
    finally:
        conn.close()


def update_graph(graph_id: int, name: str, description: str = "") -> bool:
    """Update graph name and description."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE graphs
                SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, description or "", graph_id),
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def update_graph_data(
    graph_id: int,
    name: str,
    description: str,
    nodes_list: List[Dict[str, Any]],
    edges_list: List[Dict[str, Any]],
) -> bool:
    """Update an existing graph's metadata, nodes, and edges atomically."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE graphs
                SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (name, description or "", graph_id),
            )
            if cursor.rowcount == 0:
                return False

            # Delete edges before nodes to respect node foreign keys cleanly
            cursor.execute("DELETE FROM edges WHERE graph_id = ?", (graph_id,))
            cursor.execute("DELETE FROM nodes WHERE graph_id = ?", (graph_id,))
            _insert_nodes_and_edges(cursor, graph_id, nodes_list, edges_list)
            return True
    finally:
        conn.close()


def delete_graph(graph_id: int) -> bool:
    """Delete a graph and cascade deletion to nodes, edges, and analysis results."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM edges WHERE graph_id = ?", (graph_id,))
            cursor.execute("DELETE FROM graphs WHERE id = ?", (graph_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_graph_stats() -> Dict[str, int]:
    """Return aggregated counts of graphs, nodes, edges, and analyses."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM graphs")
        total_graphs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM nodes")
        total_nodes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM edges")
        total_edges = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        total_analyses = cursor.fetchone()[0]

        return {
            "total_graphs": total_graphs,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_analyses": total_analyses,
        }
    finally:
        conn.close()


def save_analysis_result(graph_id: int, result: Dict[str, Any]) -> int:
    """Save spectral analysis result for a graph, JSON-serializing array fields."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            fiedler_val = result.get("fiedler_value", result.get("lambda_2"))
            if fiedler_val is not None:
                fiedler_val = float(fiedler_val)

            is_conn = 1 if result.get("is_connected") else 0
            method_used = str(result.get("method_used") or "auto")

            cursor.execute(
                """
                INSERT INTO analysis_results (
                    graph_id,
                    adjacency_matrix,
                    degree_matrix,
                    laplacian_matrix,
                    eigenvalues,
                    eigenvectors,
                    component_count_spectral,
                    component_count_bfs,
                    component_count_union_find,
                    fiedler_value,
                    fiedler_vector,
                    group_assignments,
                    method_used,
                    is_connected
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    graph_id,
                    _serialize_json_field(result.get("adjacency_matrix")),
                    _serialize_json_field(result.get("degree_matrix")),
                    _serialize_json_field(result.get("laplacian_matrix")),
                    _serialize_json_field(result.get("eigenvalues")),
                    _serialize_json_field(result.get("eigenvectors")),
                    result.get("component_count_spectral"),
                    result.get("component_count_bfs"),
                    result.get("component_count_union_find"),
                    fiedler_val,
                    _serialize_json_field(result.get("fiedler_vector")),
                    _serialize_json_field(result.get("group_assignments")),
                    method_used,
                    is_conn,
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_analysis_results(graph_id: int) -> List[Dict[str, Any]]:
    """Get all analysis results for a graph, ordered by analysis_date descending."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM analysis_results
            WHERE graph_id = ?
            ORDER BY analysis_date DESC, id DESC
            """,
            (graph_id,),
        )
        return [_deserialize_analysis_row(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_latest_analysis(graph_id: int) -> Optional[Dict[str, Any]]:
    """Get the most recent analysis result for a graph, or None if unavailable."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM analysis_results
            WHERE graph_id = ?
            ORDER BY analysis_date DESC, id DESC
            LIMIT 1
            """,
            (graph_id,),
        )
        row = cursor.fetchone()
        return _deserialize_analysis_row(row) if row else None
    finally:
        conn.close()


def get_all_analyses() -> List[Dict[str, Any]]:
    """Get all saved analysis results joined with graph metadata."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                a.*,
                g.name AS graph_name,
                g.description AS graph_description
            FROM analysis_results a
            JOIN graphs g ON g.id = a.graph_id
            ORDER BY a.analysis_date DESC, a.id DESC
            """
        )
        return [_deserialize_analysis_row(row) for row in cursor.fetchall()]
    finally:
        conn.close()
