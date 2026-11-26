"""Flask routes and REST API endpoints for SpectraGraph."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, render_template, request, send_file

from db.database import (
    delete_graph,
    get_analysis_results,
    get_graph,
    get_graph_stats,
    get_graphs,
    save_analysis_result,
    save_graph_data,
    update_graph_data,
)
from ds.bfs import bfs_connected_components, edges_to_adj_list
from ds.union_find import union_find_components
from math_engine.adjacency import build_adjacency_matrix
from math_engine.degree import build_degree_matrix
from math_engine.eigenvalues import EIGENVALUE_TOLERANCE, compute_eigenvalues
from math_engine.fiedler import compute_fiedler
from math_engine.laplacian import build_laplacian, compute_null_space, verify_laplacian
from math_engine.validation import validate_all_matrices

main = Blueprint("main", __name__)

_ALLOWED_METHODS = {"auto", "jacobi", "numpy"}


# -------------------------------------------------------------------------
# Helper Utilities
# -------------------------------------------------------------------------


def _circular_positions(
    count: int,
    cx: float = 350.0,
    cy: float = 260.0,
    radius: float = 160.0,
    start_angle: float = -math.pi / 2.0,
) -> List[Tuple[float, float]]:
    """Generate evenly spaced circular 2D coordinates for vertices."""
    if count <= 0:
        return []
    if count == 1:
        return [(cx, cy)]
    coords: List[Tuple[float, float]] = []
    for idx in range(count):
        angle = start_angle + (2.0 * math.pi * idx) / count
        x = round(cx + radius * math.cos(angle), 2)
        y = round(cy + radius * math.sin(angle), 2)
        coords.append((x, y))
    return coords


def _build_sample_graph_spec(sample_type: str) -> Optional[Dict[str, Any]]:
    """Return name, description, nodes, and edges for a named sample topology."""
    key = sample_type.strip().lower()

    if key == "path":
        nodes = [
            {"label": f"v{i + 1}", "x": round(110.0 + i * 96.0, 2), "y": 260.0}
            for i in range(6)
        ]
        edges = [{"source": i, "target": i + 1} for i in range(5)]
        return {
            "name": "Path Graph P6",
            "description": (
                "Path graph P6 on 6 vertices with 5 edges. Tree topology: connected "
                "(1 component) with low algebraic connectivity lambda_2 = 2(1 - cos(pi/6)) ~= 0.2679."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    if key == "cycle":
        coords = _circular_positions(6, radius=165.0)
        nodes = [
            {"label": f"v{i + 1}", "x": coords[i][0], "y": coords[i][1]}
            for i in range(6)
        ]
        edges = [{"source": i, "target": (i + 1) % 6} for i in range(6)]
        return {
            "name": "Cycle Graph C6",
            "description": (
                "Cycle graph C6 on 6 vertices with 6 edges. 2-regular connected ring "
                "with eigenvalues 2 - 2cos(2*pi*k/6) and algebraic connectivity lambda_2 = 1.0."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    if key == "complete":
        coords = _circular_positions(5, radius=165.0)
        nodes = [
            {"label": f"v{i + 1}", "x": coords[i][0], "y": coords[i][1]}
            for i in range(5)
        ]
        edges = [
            {"source": i, "target": j}
            for i in range(5)
            for j in range(i + 1, 5)
        ]
        return {
            "name": "Complete Graph K5",
            "description": (
                "Complete graph K5 on 5 vertices with all 10 edges. Maximally connected "
                "4-regular clique with Laplacian eigenvalues {0, 5, 5, 5, 5} and lambda_2 = 5.0."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    if key == "star":
        outer = _circular_positions(5, radius=170.0)
        nodes = [{"label": "v1", "x": 350.0, "y": 260.0}] + [
            {"label": f"v{i + 2}", "x": outer[i][0], "y": outer[i][1]}
            for i in range(5)
        ]
        edges = [{"source": 0, "target": i} for i in range(1, 6)]
        return {
            "name": "Star Graph S6",
            "description": (
                "Star graph S6 (K_{1,5}) with hub v1 connected to 5 leaves v2-v6. "
                "Connected tree with Laplacian spectrum {0, 1, 1, 1, 1, 6} and lambda_2 = 1.0."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    if key == "disconnected":
        left = _circular_positions(3, cx=200.0, cy=260.0, radius=95.0)
        right = _circular_positions(3, cx=500.0, cy=260.0, radius=95.0)
        coords = left + right
        nodes = [
            {"label": f"v{i + 1}", "x": coords[i][0], "y": coords[i][1]}
            for i in range(6)
        ]
        edges = [
            {"source": 0, "target": 1},
            {"source": 1, "target": 2},
            {"source": 2, "target": 0},
            {"source": 3, "target": 4},
            {"source": 4, "target": 5},
            {"source": 5, "target": 3},
        ]
        return {
            "name": "Disconnected Graph",
            "description": (
                "Disconnected 6-vertex graph consisting of two disjoint triangles (K3 + K3). "
                "Has 2 connected components, so lambda = 0 has multiplicity 2 and lambda_2 = 0."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    if key == "two_community":
        left = _circular_positions(5, cx=195.0, cy=260.0, radius=110.0)
        right = _circular_positions(5, cx=515.0, cy=260.0, radius=110.0)
        coords = left + right
        nodes = [
            {"label": f"v{i + 1}", "x": coords[i][0], "y": coords[i][1]}
            for i in range(10)
        ]
        # Group A (v1-v5, indices 0-4): 8 edges (K5 minus (0,3) and (1,4))
        group_a_edges = [
            (0, 1), (0, 2), (0, 4),
            (1, 2), (1, 3),
            (2, 3), (2, 4),
            (3, 4),
        ]
        # Group B (v6-v10, indices 5-9): 8 edges (K5 minus (5,8) and (6,9))
        group_b_edges = [
            (5, 6), (5, 7), (5, 9),
            (6, 7), (6, 8),
            (7, 8), (7, 9),
            (8, 9),
        ]
        # Bridge edges connecting Group A and Group B: (v3,v8) -> (2,7), (v5,v6) -> (4,5)
        bridge_edges = [(2, 7), (4, 5)]
        edges = [
            {"source": u, "target": v}
            for (u, v) in (group_a_edges + group_b_edges + bridge_edges)
        ]
        return {
            "name": "Two-Community Graph",
            "description": (
                "10-vertex modular network with two dense 5-node communities (8 edges each) "
                "linked by two bridge edges (v3,v8) and (v5,v6). Ideal for Fiedler spectral bisection."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    if key == "petersen":
        outer = _circular_positions(5, cx=350.0, cy=260.0, radius=180.0)
        inner = _circular_positions(5, cx=350.0, cy=260.0, radius=85.0)
        coords = outer + inner
        nodes = [
            {"label": f"v{i + 1}", "x": coords[i][0], "y": coords[i][1]}
            for i in range(10)
        ]
        petersen_edges = [
            # Outer 5-cycle
            (0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
            # Inner 5-star
            (5, 7), (7, 9), (9, 6), (6, 8), (8, 5),
            # Spokes
            (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
        ]
        edges = [{"source": u, "target": v} for (u, v) in petersen_edges]
        return {
            "name": "Petersen Graph",
            "description": (
                "Canonical 10-vertex, 15-edge 3-regular symmetric Petersen graph. Connected "
                "with Laplacian spectrum {0, 2^5, 5^4} and algebraic connectivity lambda_2 = 2.0."
            ),
            "nodes": nodes,
            "edges": edges,
        }

    return None


def _extract_graph_topology(graph: Dict[str, Any]) -> Tuple[int, List[str], List[Tuple[int, int]]]:
    """Map DB graph nodes and edges to 0-based indices, node labels, and unique edge pairs."""
    nodes = graph.get("nodes", [])
    n = len(nodes)
    node_id_to_idx = {node["id"]: idx for idx, node in enumerate(nodes)}
    node_labels = [str(node.get("label", f"v{idx + 1}")) for idx, node in enumerate(nodes)]

    edge_tuples: List[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()
    for edge in graph.get("edges", []):
        src_id = edge.get("source_node_id", edge.get("source"))
        tgt_id = edge.get("target_node_id", edge.get("target"))
        u = node_id_to_idx.get(src_id)
        v = node_id_to_idx.get(tgt_id)
        if u is not None and v is not None and u != v:
            pair = (min(u, v), max(u, v))
            if pair not in seen:
                seen.add(pair)
                edge_tuples.append(pair)

    return n, node_labels, edge_tuples


def _clean_float_list(values: Any) -> List[float]:
    """Convert numeric sequence to plain floats, clamping tiny negative zeros to 0.0."""
    cleaned: List[float] = []
    for val in values:
        fval = float(val)
        if abs(fval) < 1e-12:
            fval = 0.0
        cleaned.append(fval)
    return cleaned


def _clean_matrix_list(matrix: Any) -> List[List[float]]:
    """Convert 2D numpy array to nested Python float lists."""
    return [_clean_float_list(row) for row in matrix.tolist()]


def _safe_filename(name: str, fallback: str) -> str:
    """Create a filesystem-safe download filename stem."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", (name or "").strip()).strip("_")
    return cleaned or fallback


def _build_observations(
    n: int,
    m: int,
    lap_verif: Dict[str, bool],
    comp_spectral: int,
    comp_bfs: int,
    comp_uf: int,
    all_agree: bool,
    fiedler_result: Dict[str, Any],
    eigen_result: Dict[str, Any],
) -> List[str]:
    """Generate concise, human-readable mathematical observations for the UI."""
    observations: List[str] = []
    if n == 0:
        return ["The graph has 0 vertices; matrices and spectra are empty."]

    density = (2.0 * m) / (n * (n - 1)) if n > 1 else 0.0
    observations.append(
        f"Graph contains |V| = {n} vertices and |E| = {m} undirected edges "
        f"(density = {density:.3f})."
    )

    if lap_verif["is_symmetric"] and lap_verif["row_sums_zero"] and lap_verif["is_positive_semidefinite"]:
        observations.append(
            "Laplacian L = D - A passed all structural checks: symmetric, zero row sums (L*1 = 0), "
            "and positive semi-definite (all eigenvalues >= 0)."
        )

    observations.append(
        f"Eigenvalue decomposition ran using the '{eigen_result['method_used']}' solver"
        + (
            f" (cross-validated against NumPy with max error {eigen_result['validation_max_error']:.2e})."
            if eigen_result.get("jacobi_validated")
            else "."
        )
    )

    if all_agree:
        observations.append(
            f"All three connectivity methods agree: Spectral ({comp_spectral}), "
            f"BFS ({comp_bfs}), and Union-Find ({comp_uf}) each report {comp_spectral} component(s)."
        )
    else:
        observations.append(
            f"Component counts differ across methods: Spectral={comp_spectral}, "
            f"BFS={comp_bfs}, Union-Find={comp_uf}."
        )

    observations.append(fiedler_result["explanation"])
    return observations


def _parse_json_import(raw_text: str, default_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse and validate a JSON graph payload for import."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON file: {exc}"

    if not isinstance(data, dict):
        return None, "Invalid JSON format: top-level JSON value must be an object."

    if "nodes" not in data or "edges" not in data:
        return None, "Invalid JSON graph format: 'nodes' and 'edges' fields are required."

    raw_nodes = data["nodes"]
    raw_edges = data["edges"]
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        return None, "Invalid JSON graph format: 'nodes' and 'edges' must be lists."

    if len(raw_nodes) == 0:
        return None, "Invalid JSON graph format: graph must contain at least one node."

    nodes: List[Dict[str, Any]] = []
    ext_id_to_idx: Dict[Any, int] = {}
    label_to_idx: Dict[str, int] = {}
    has_ext_ids = False

    for idx, item in enumerate(raw_nodes):
        if isinstance(item, dict):
            label = str(item.get("label", item.get("id", f"v{idx + 1}"))).strip()
            if not label:
                label = f"v{idx + 1}"
            try:
                pos_x = float(item.get("position_x", item.get("x", 0)) or 0)
                pos_y = float(item.get("position_y", item.get("y", 0)) or 0)
            except (TypeError, ValueError):
                return None, f"Invalid coordinate value on node index {idx}."
            node_entry: Dict[str, Any] = {"label": label, "x": pos_x, "y": pos_y}
            if "id" in item and item["id"] is not None:
                has_ext_ids = True
                ext_id_to_idx[item["id"]] = idx
                ext_id_to_idx[str(item["id"])] = idx
            if label not in label_to_idx:
                label_to_idx[label] = idx
            nodes.append(node_entry)
        elif isinstance(item, (str, int)):
            label = str(item).strip() or f"v{idx + 1}"
            if label not in label_to_idx:
                label_to_idx[label] = idx
            nodes.append({"label": label, "x": 0.0, "y": 0.0})
        else:
            return None, f"Invalid node entry at index {idx}."

    def resolve_endpoint(ref: Any) -> Optional[int]:
        if ref is None:
            return None
        if has_ext_ids and ref in ext_id_to_idx:
            return ext_id_to_idx[ref]
        if has_ext_ids and str(ref) in ext_id_to_idx:
            return ext_id_to_idx[str(ref)]
        if isinstance(ref, int) and not isinstance(ref, bool):
            if 0 <= ref < len(nodes):
                return ref
        if isinstance(ref, str):
            stripped = ref.strip()
            if stripped.isdigit():
                idx_val = int(stripped)
                if 0 <= idx_val < len(nodes):
                    return idx_val
            if stripped in label_to_idx:
                return label_to_idx[stripped]
        return None

    edges: List[Dict[str, int]] = []
    for idx, edge in enumerate(raw_edges):
        if isinstance(edge, dict):
            raw_src = edge.get("source", edge.get("source_node_id"))
            raw_tgt = edge.get("target", edge.get("target_node_id"))
        elif isinstance(edge, (list, tuple)) and len(edge) == 2:
            raw_src, raw_tgt = edge[0], edge[1]
        else:
            return None, f"Invalid edge entry at index {idx}."

        src_idx = resolve_endpoint(raw_src)
        tgt_idx = resolve_endpoint(raw_tgt)
        if src_idx is None or tgt_idx is None:
            return None, f"Edge at index {idx} references an unknown node ({raw_src!r}, {raw_tgt!r})."
        edges.append({"source": src_idx, "target": tgt_idx})

    name = str(data.get("name") or default_name or "Imported Graph").strip()
    description = str(data.get("description") or "").strip()

    return {
        "name": name,
        "description": description,
        "nodes": nodes,
        "edges": edges,
    }, None


def _parse_csv_import(raw_text: str, default_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse and validate a CSV edge list (source,target) for import."""
    reader = csv.reader(io.StringIO(raw_text))
    rows = [
        [cell.strip() for cell in row]
        for row in reader
        if any(cell.strip() for cell in row)
    ]

    if not rows:
        return None, "CSV file is empty."

    header_candidates = {
        ("source", "target"),
        ("src", "tgt"),
        ("u", "v"),
        ("from", "to"),
        ("node1", "node2"),
        ("source_label", "target_label"),
    }
    first_pair = tuple(cell.lower() for cell in rows[0][:2]) if len(rows[0]) >= 2 else ()
    data_rows = rows[1:] if first_pair in header_candidates else rows

    if not data_rows:
        return None, "CSV file contains a header but no edge rows."

    label_to_idx: Dict[str, int] = {}
    ordered_labels: List[str] = []
    edges: List[Dict[str, int]] = []

    for row_num, row in enumerate(data_rows, start=1):
        if len(row) < 2 or not row[0] or not row[1]:
            return None, (
                f"Invalid CSV format on edge row {row_num}: expected at least two non-empty columns (source,target)."
            )
        src_label, tgt_label = row[0], row[1]
        for lbl in (src_label, tgt_label):
            if lbl not in label_to_idx:
                label_to_idx[lbl] = len(ordered_labels)
                ordered_labels.append(lbl)
        edges.append(
            {"source": label_to_idx[src_label], "target": label_to_idx[tgt_label]}
        )

    coords = _circular_positions(len(ordered_labels))
    nodes = [
        {"label": lbl, "x": coords[idx][0], "y": coords[idx][1]}
        for idx, lbl in enumerate(ordered_labels)
    ]

    return {
        "name": default_name or "Imported CSV Graph",
        "description": f"Imported from CSV edge list ({len(nodes)} vertices, {len(edges)} edges).",
        "nodes": nodes,
        "edges": edges,
    }, None


# -------------------------------------------------------------------------
# Page Routes (GET)
# -------------------------------------------------------------------------


@main.route("/")
def dashboard():
    """Render the main dashboard page with summary statistics and recent graphs."""
    stats = get_graph_stats()
    recent_graphs = get_graphs()[:5]
    return render_template(
        "index.html",
        active_page="dashboard",
        stats=stats,
        recent_graphs=recent_graphs,
    )


@main.route("/graph-builder")
def graph_builder():
    """Render the interactive Graph Builder canvas interface."""
    return render_template("graph_builder.html", active_page="graph_builder")


@main.route("/analysis")
def analysis():
    """Render the Spectral Analysis page."""
    return render_template("analysis.html", active_page="analysis")


@main.route("/saved-graphs")
def saved_graphs():
    """Render the Saved Graphs management page."""
    graphs = get_graphs()
    return render_template(
        "saved_graphs.html",
        active_page="saved_graphs",
        graphs=graphs,
    )


@main.route("/about")
def about():
    """Render the About Project & mathematical foundations page."""
    return render_template("about.html", active_page="about")


# -------------------------------------------------------------------------
# Graph CRUD & Generation API Routes
# -------------------------------------------------------------------------


@main.route("/api/graphs", methods=["POST"])
def api_create_graph():
    """Save a new graph with nodes and edges."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name or not str(name).strip():
        return jsonify({"success": False, "error": "Graph name is required"}), 400

    description = data.get("description", "")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return jsonify({"success": False, "error": "'nodes' and 'edges' must be lists"}), 400

    try:
        graph_id = save_graph_data(str(name).strip(), str(description or ""), nodes, edges)
        graph = get_graph(graph_id)
        return jsonify({"success": True, "graph_id": graph_id, "graph": graph}), 201
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@main.route("/api/graphs/<int:graph_id>", methods=["PUT"])
def api_update_graph(graph_id: int):
    """Update an existing graph's metadata, nodes, and edges."""
    existing = get_graph(graph_id)
    if not existing:
        return jsonify({"success": False, "error": "Graph not found"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        raw_name = data.get("name")
        if not raw_name or not str(raw_name).strip():
            return jsonify({"success": False, "error": "Graph name cannot be empty"}), 400
        name = str(raw_name).strip()
    else:
        name = existing["name"]

    description = str(data.get("description", existing.get("description") or ""))
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return jsonify({"success": False, "error": "'nodes' and 'edges' must be lists"}), 400

    try:
        updated = update_graph_data(graph_id, name, description, nodes, edges)
        if not updated:
            return jsonify({"success": False, "error": "Graph not found"}), 404
        graph = get_graph(graph_id)
        return jsonify({"success": True, "graph_id": graph_id, "graph": graph}), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@main.route("/api/graphs", methods=["GET"])
def api_get_graphs():
    """Return a list of all saved graphs with node and edge counts."""
    graphs = get_graphs()
    return jsonify({"graphs": graphs}), 200


@main.route("/api/graphs/<int:graph_id>", methods=["GET"])
def api_get_graph(graph_id: int):
    """Retrieve a single graph by ID including all its nodes and edges."""
    graph = get_graph(graph_id)
    if not graph:
        return jsonify({"error": "Graph not found"}), 404
    return jsonify(graph), 200


@main.route("/api/graphs/<int:graph_id>", methods=["DELETE"])
def api_delete_graph(graph_id: int):
    """Delete a graph and all associated entities."""
    success = delete_graph(graph_id)
    if not success:
        return jsonify({"success": False, "error": "Graph not found"}), 404
    return jsonify({"success": True}), 200


@main.route("/api/graphs/sample", methods=["POST"])
def api_create_sample_graph():
    """Generate and persist one of the canonical sample graphs."""
    data = request.get_json(silent=True) or {}
    sample_type = str(data.get("type") or "petersen").strip().lower()
    spec = _build_sample_graph_spec(sample_type)
    if not spec:
        return jsonify(
            {
                "success": False,
                "error": (
                    f"Unknown sample graph type {sample_type!r}. Expected one of: "
                    "path, cycle, complete, star, disconnected, two_community, petersen."
                ),
            }
        ), 400

    try:
        graph_id = save_graph_data(
            name=spec["name"],
            description=spec["description"],
            nodes_list=spec["nodes"],
            edges_list=spec["edges"],
        )
        graph = get_graph(graph_id)
        return jsonify({"success": True, "graph_id": graph_id, "graph": graph}), 201
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@main.route("/api/graphs/random", methods=["POST"])
def api_create_random_graph():
    """Generate and persist an Erdos-Renyi random graph G(n, p)."""
    data = request.get_json(silent=True) or {}
    raw_n = data.get("node_count", data.get("n", 8))
    raw_p = data.get("edge_probability", data.get("p", 0.3))

    try:
        node_count = int(raw_n)
        edge_prob = float(raw_p)
    except (TypeError, ValueError):
        return jsonify(
            {"success": False, "error": "node_count must be an integer and edge_probability a float"}
        ), 400

    if not (2 <= node_count <= 300):
        return jsonify(
            {"success": False, "error": "node_count must be between 2 and 300"}
        ), 400
    if not (0.0 <= edge_prob <= 1.0):
        return jsonify(
            {"success": False, "error": "edge_probability must be between 0.0 and 1.0"}
        ), 400

    coords = _circular_positions(node_count, radius=175.0)
    nodes = [
        {"label": f"v{i + 1}", "x": coords[i][0], "y": coords[i][1]}
        for i in range(node_count)
    ]
    edges = [
        {"source": i, "target": j}
        for i in range(node_count)
        for j in range(i + 1, node_count)
        if random.random() < edge_prob
    ]

    try:
        graph_id = save_graph_data(
            name=f"Random G({node_count}, {edge_prob:.2f})",
            description=(
                f"Erdos-Renyi random undirected graph G({node_count}, {edge_prob:.2f}) "
                f"with {node_count} vertices and {len(edges)} generated edges."
            ),
            nodes_list=nodes,
            edges_list=edges,
        )
        graph = get_graph(graph_id)
        return jsonify({"success": True, "graph_id": graph_id, "graph": graph}), 201
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# -------------------------------------------------------------------------
# Spectral Analysis API Routes
# -------------------------------------------------------------------------


@main.route("/api/analyze/<int:graph_id>", methods=["POST"])
def api_analyze_graph(graph_id: int):
    """Run full spectral, BFS, and Union-Find analysis on a saved graph."""
    graph = get_graph(graph_id)
    if not graph:
        return jsonify({"success": False, "error": "Graph not found"}), 404

    req_data = request.get_json(silent=True) or {}
    method = str(req_data.get("method") or "auto").strip().lower()
    if method not in _ALLOWED_METHODS:
        return jsonify(
            {"success": False, "error": f"Unsupported method {method!r}. Use auto, jacobi, or numpy."}
        ), 400

    try:
        n, node_labels, edge_tuples = _extract_graph_topology(graph)
        adj_list = edges_to_adj_list(n, edge_tuples)

        adj_matrix = build_adjacency_matrix(n, edge_tuples)
        deg_matrix = build_degree_matrix(adj_matrix)
        lap_matrix = build_laplacian(adj_matrix)
        lap_verification = verify_laplacian(lap_matrix)
        matrix_validation = validate_all_matrices(adj_matrix, deg_matrix, lap_matrix)

        eigen_result = compute_eigenvalues(lap_matrix, method=method)
        null_space_result = compute_null_space(
            lap_matrix,
            eigen_result["eigenvalues"],
            eigen_result["eigenvectors"],
        )
        fiedler_result = compute_fiedler(
            eigen_result["eigenvalues"],
            eigen_result["eigenvectors"],
        )

        bfs_result = bfs_connected_components(n, adj_list)
        uf_result = union_find_components(n, edge_tuples)

        component_indicators = []
        for comp in bfs_result["components"]:
            indicator = [1 if idx in comp else 0 for idx in range(n)]
            component_indicators.append(indicator)

        null_space_payload = {
            "dimension": null_space_result["dimension"],
            "basis_vectors": null_space_result["basis_vectors"],
            "component_indicators": component_indicators,
            "max_residual": null_space_result["max_residual"],
            "explanation": null_space_result["explanation"],
        }

        comp_spectral = int(eigen_result["zero_eigenvalue_count"])
        comp_bfs = int(bfs_result["component_count"])
        comp_uf = int(uf_result["component_count"])
        all_agree = bool(comp_spectral == comp_bfs == comp_uf)

        adj_nested = _clean_matrix_list(adj_matrix)
        deg_nested = _clean_matrix_list(deg_matrix)
        lap_nested = _clean_matrix_list(lap_matrix)
        eigenvalues_list = _clean_float_list(eigen_result["eigenvalues"].tolist())
        eigenvectors_nested = _clean_matrix_list(eigen_result["eigenvectors"])

        fiedler_vec_list = (
            None
            if fiedler_result["fiedler_vector"] is None
            else _clean_float_list(fiedler_result["fiedler_vector"].tolist())
        )

        partition = fiedler_result["partition"]
        group_assignments: Optional[List[int]] = None
        partition_payload: Optional[Dict[str, Any]] = None
        if partition is not None:
            group_1 = list(partition["group_1"])
            group_2 = list(partition["group_2"])
            group_assignments = [0] * n
            for idx in group_1:
                group_assignments[idx] = 1
            for idx in group_2:
                group_assignments[idx] = 2
            partition_payload = {
                "group_1": group_1,
                "group_2": group_2,
                "group_1_labels": [node_labels[idx] for idx in group_1],
                "group_2_labels": [node_labels[idx] for idx in group_2],
            }

        fiedler_payload = {
            "lambda_2": fiedler_result["lambda_2"],
            "fiedler_vector": fiedler_vec_list,
            "partition": partition_payload,
            "group_assignments": group_assignments,
            "is_connected": fiedler_result["is_connected"],
            "can_partition": fiedler_result["can_partition"],
            "explanation": fiedler_result["explanation"],
        }

        analysis_id = save_analysis_result(
            graph_id,
            {
                "adjacency_matrix": adj_nested,
                "degree_matrix": deg_nested,
                "laplacian_matrix": lap_nested,
                "eigenvalues": eigenvalues_list,
                "eigenvectors": eigenvectors_nested,
                "component_count_spectral": comp_spectral,
                "component_count_bfs": comp_bfs,
                "component_count_union_find": comp_uf,
                "fiedler_value": fiedler_result["lambda_2"],
                "fiedler_vector": fiedler_vec_list,
                "group_assignments": group_assignments,
                "method_used": eigen_result["method_used"],
                "is_connected": eigen_result["is_connected"],
            },
        )

        m = len(edge_tuples)
        density = (2.0 * m) / (n * (n - 1)) if n > 1 else 0.0
        observations = _build_observations(
            n=n,
            m=m,
            lap_verif=lap_verification,
            comp_spectral=comp_spectral,
            comp_bfs=comp_bfs,
            comp_uf=comp_uf,
            all_agree=all_agree,
            fiedler_result=fiedler_result,
            eigen_result=eigen_result,
        )

        graph_info = {
            "id": graph["id"],
            "name": graph["name"],
            "description": graph["description"],
            "node_count": n,
            "edge_count": m,
            "density": round(density, 6),
            "nodes": graph["nodes"],
            "edges": graph["edges"],
        }

        return jsonify(
            {
                "success": True,
                "analysis_id": analysis_id,
                "graph": graph_info,
                "node_labels": node_labels,
                "adjacency_matrix": adj_nested,
                "degree_matrix": deg_nested,
                "laplacian_matrix": lap_nested,
                "laplacian_verification": lap_verification,
                "matrix_validation": matrix_validation,
                "eigenvalues": eigenvalues_list,
                "eigenvectors": eigenvectors_nested,
                "zero_eigenvalue_count": comp_spectral,
                "lambda_2": fiedler_result["lambda_2"],
                "is_connected": eigen_result["is_connected"],
                "component_count_spectral": comp_spectral,
                "component_count_bfs": comp_bfs,
                "component_count_union_find": comp_uf,
                "bfs_components": bfs_result["components"],
                "union_find_components": uf_result["components"],
                "all_agree": all_agree,
                "null_space": null_space_payload,
                "fiedler": fiedler_payload,
                "method_used": eigen_result["method_used"],
                "jacobi_validated": eigen_result["jacobi_validated"],
                "validation_max_error": eigen_result["validation_max_error"],
                "observations": observations,
            }
        ), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@main.route("/api/analysis/<int:graph_id>", methods=["GET"])
def api_get_analysis(graph_id: int):
    """Return saved spectral analysis records for a graph."""
    graph = get_graph(graph_id)
    if not graph:
        return jsonify({"success": False, "error": "Graph not found"}), 404

    results = get_analysis_results(graph_id)
    latest = results[0] if results else None
    return jsonify(
        {
            "success": True,
            "graph_id": graph_id,
            "latest": latest,
            "analyses": results,
        }
    ), 200


# -------------------------------------------------------------------------
# Import / Export Routes
# -------------------------------------------------------------------------


@main.route("/api/graphs/<int:graph_id>/export", methods=["GET"])
def api_export_graph(graph_id: int):
    """Export a saved graph as JSON or CSV edge list."""
    graph = get_graph(graph_id)
    if not graph:
        return jsonify({"error": "Graph not found"}), 404

    fmt = (request.args.get("format") or "json").strip().lower()
    safe_stem = _safe_filename(graph["name"], f"graph_{graph_id}")

    if fmt == "json":
        export_payload = {
            "id": graph["id"],
            "name": graph["name"],
            "description": graph.get("description") or "",
            "nodes": [
                {
                    "id": n["id"],
                    "label": n["label"],
                    "x": n["position_x"],
                    "y": n["position_y"],
                }
                for n in graph["nodes"]
            ],
            "edges": [
                {
                    "source": e["source_node_id"],
                    "target": e["target_node_id"],
                }
                for e in graph["edges"]
            ],
        }
        buf = io.BytesIO(json.dumps(export_payload, indent=2).encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/json",
            as_attachment=True,
            download_name=f"{safe_stem}.json",
        )

    if fmt == "csv":
        label_by_id = {n["id"]: n["label"] for n in graph["nodes"]}
        text_buf = io.StringIO()
        writer = csv.writer(text_buf, lineterminator="\n")
        writer.writerow(["source", "target"])
        for edge in graph["edges"]:
            src_label = label_by_id.get(edge["source_node_id"], edge["source_node_id"])
            tgt_label = label_by_id.get(edge["target_node_id"], edge["target_node_id"])
            writer.writerow([src_label, tgt_label])
        byte_buf = io.BytesIO(text_buf.getvalue().encode("utf-8"))
        byte_buf.seek(0)
        return send_file(
            byte_buf,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{safe_stem}.csv",
        )

    return jsonify({"error": f"Unsupported export format {fmt!r}. Use 'json' or 'csv'."}), 400


@main.route("/api/graphs/import", methods=["POST"])
def api_import_graph():
    """Import a graph from an uploaded JSON or CSV file (or JSON payload)."""
    raw_text: Optional[str] = None
    filename = ""
    fmt = ""

    if request.files:
        uploaded = request.files.get("file") or next(iter(request.files.values()))
        if not uploaded or not uploaded.filename:
            return jsonify({"error": "No file selected for import."}), 400
        filename = uploaded.filename
        try:
            raw_text = uploaded.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return jsonify({"error": "Uploaded file must be UTF-8 encoded text."}), 400

        ext = os.path.splitext(filename)[1].lower()
        if ext == ".json":
            fmt = "json"
        elif ext == ".csv":
            fmt = "csv"
        else:
            fmt = (request.form.get("format") or "").strip().lower()
    else:
        json_body = request.get_json(silent=True)
        if json_body is None:
            return jsonify({"error": "No file or JSON graph data provided."}), 400
        if "content" in json_body and isinstance(json_body["content"], str):
            raw_text = json_body["content"]
            filename = str(json_body.get("filename") or "")
            fmt = str(json_body.get("format") or "").strip().lower()
        else:
            raw_text = json.dumps(json_body)
            fmt = "json"

    if not raw_text or not raw_text.strip():
        return jsonify({"error": "Imported file is empty."}), 400

    if not fmt:
        stripped = raw_text.lstrip()
        fmt = "json" if stripped.startswith("{") or stripped.startswith("[") else "csv"

    default_name = (
        str(request.form.get("name") or "").strip()
        or os.path.splitext(os.path.basename(filename))[0]
        or "Imported Graph"
    )

    if fmt == "json":
        parsed, err = _parse_json_import(raw_text, default_name)
    elif fmt == "csv":
        parsed, err = _parse_csv_import(raw_text, default_name)
    else:
        return jsonify({"error": f"Unsupported import format {fmt!r}. Expected JSON or CSV."}), 400

    if err or not parsed:
        return jsonify({"error": err or "Failed to parse imported graph."}), 400

    try:
        graph_id = save_graph_data(
            name=parsed["name"],
            description=parsed["description"],
            nodes_list=parsed["nodes"],
            edges_list=parsed["edges"],
        )
        graph = get_graph(graph_id)
        return jsonify({"success": True, "graph_id": graph_id, "graph": graph}), 201
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# -------------------------------------------------------------------------
# Eigenvalue Plot Route
# -------------------------------------------------------------------------


@main.route("/api/graphs/<int:graph_id>/eigenvalue-plot", methods=["GET"])
def api_eigenvalue_plot(graph_id: int):
    """Generate a dark-themed Laplacian eigenvalue bar chart PNG image."""
    graph = get_graph(graph_id)
    if not graph:
        return jsonify({"error": "Graph not found"}), 404

    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.patches import Patch
    except ImportError:
        return jsonify(
            {"error": "matplotlib is required for eigenvalue plotting. Install requirements.txt."}
        ), 500

    n, _, edge_tuples = _extract_graph_topology(graph)
    adj_matrix = build_adjacency_matrix(n, edge_tuples)
    lap_matrix = build_laplacian(adj_matrix)
    eigen_result = compute_eigenvalues(lap_matrix, method="auto")
    eigenvalues = _clean_float_list(eigen_result["eigenvalues"].tolist())

    fig = Figure(figsize=(8.0, 4.2), dpi=140, facecolor="#0f172a")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_facecolor("#111827")

    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.tick_params(colors="#cbd5e1", labelsize=9)

    if n == 0:
        ax.text(
            0.5,
            0.5,
            "No vertices in graph",
            ha="center",
            va="center",
            color="#94a3b8",
            fontsize=12,
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        indices = list(range(1, n + 1))
        is_zero = [abs(val) < EIGENVALUE_TOLERANCE for val in eigenvalues]
        colors = ["#ef4444" if zero else "#7c3aed" for zero in is_zero]
        max_val = max(eigenvalues) if eigenvalues else 1.0
        y_top = max(max_val * 1.18, 1.0)

        bars = ax.bar(
            indices,
            eigenvalues,
            color=colors,
            edgecolor="#e2e8f0",
            linewidth=0.6,
            width=0.62,
            zorder=3,
        )

        # Highlight zero eigenvalues clearly at y=0 so height-0 bars remain visible
        zero_indices = [idx for idx, zero in zip(indices, is_zero) if zero]
        if zero_indices:
            ax.scatter(
                zero_indices,
                [0.0] * len(zero_indices),
                color="#ef4444",
                edgecolors="#fecaca",
                s=65,
                zorder=4,
            )

        for bar, val, zero in zip(bars, eigenvalues, is_zero):
            if n <= 25 or zero:
                label_y = val + y_top * 0.025
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    label_y,
                    "0" if zero else f"{val:.2f}",
                    ha="center",
                    va="bottom",
                    color="#fca5a5" if zero else "#e2e8f0",
                    fontsize=8 if n <= 15 else 7,
                    fontweight="bold" if zero else "normal",
                )

        ax.axhline(0.0, color="#475569", linewidth=0.9, zorder=2)
        ax.grid(axis="y", color="#1e293b", linestyle="--", linewidth=0.8, zorder=1)
        if n <= 20:
            ax.set_xticks(indices)
            ax.set_xticklabels([f"λ{i}" for i in indices])
        else:
            step = max(1, n // 15)
            shown = indices[::step]
            ax.set_xticks(shown)
            ax.set_xticklabels([f"λ{i}" for i in shown], fontsize=8)
        ax.set_ylim(-y_top * 0.05, y_top)
        ax.set_xlabel("Eigenvalue Index", color="#cbd5e1", fontsize=10, labelpad=8)
        ax.set_ylabel("Eigenvalue Value", color="#cbd5e1", fontsize=10, labelpad=8)

        legend_handles = [
            Patch(facecolor="#ef4444", edgecolor="#e2e8f0", label="Zero Eigenvalue (λ ≈ 0)"),
            Patch(facecolor="#7c3aed", edgecolor="#e2e8f0", label="Positive Eigenvalue (λ > 0)"),
        ]
        ax.legend(
            handles=legend_handles,
            loc="upper left",
            facecolor="#1e293b",
            edgecolor="#334155",
            labelcolor="#e2e8f0",
            fontsize=8.5,
        )

    ax.set_title(
        "Laplacian Eigenvalue Spectrum",
        color="#f8fafc",
        fontsize=12.5,
        fontweight="bold",
        pad=12,
    )
    fig.tight_layout()

    img_buf = io.BytesIO()
    fig.savefig(img_buf, format="png", facecolor=fig.get_facecolor())
    img_buf.seek(0)
    return send_file(img_buf, mimetype="image/png")


@main.route("/api/demonstrations", methods=["GET"])
def api_demonstrations():
    """Run live spectral, BFS, and Union-Find verification across 6 canonical graphs."""
    demo_types = ["path", "cycle", "complete", "star", "disconnected", "two_community"]
    results = []
    two_community_split = None

    for key in demo_types:
        spec = _build_sample_graph_spec(key)
        if not spec:
            continue
        n = len(spec["nodes"])
        edge_tuples = [(int(e["source"]), int(e["target"])) for e in spec["edges"]]
        labels = [str(node["label"]) for node in spec["nodes"]]

        adj = build_adjacency_matrix(n, edge_tuples)
        lap = build_laplacian(adj)
        eig = compute_eigenvalues(lap, method="auto")
        fied = compute_fiedler(eig["eigenvalues"], eig["eigenvectors"])
        bfs = bfs_connected_components(n, edges_to_adj_list(n, edge_tuples))
        uf = union_find_components(n, edge_tuples)

        c_spec = int(eig["zero_eigenvalue_count"])
        c_bfs = int(bfs["component_count"])
        c_uf = int(uf["component_count"])

        results.append({
            "key": key,
            "name": spec["name"],
            "node_count": n,
            "edge_count": len(edge_tuples),
            "zero_eigenvalue_count": c_spec,
            "bfs_components": c_bfs,
            "union_find_components": c_uf,
            "lambda_2": round(float(eig["lambda_2"]), 4) if eig["lambda_2"] is not None else None,
            "method_used": eig["method_used"],
            "all_agree": bool(c_spec == c_bfs == c_uf),
        })

        if key == "two_community" and fied["partition"] is not None:
            g1 = fied["partition"]["group_1"]
            g2 = fied["partition"]["group_2"]
            two_community_split = {
                "lambda_2": round(float(fied["lambda_2"]), 4),
                "group_1_labels": [labels[i] for i in g1],
                "group_2_labels": [labels[i] for i in g2],
            }

    return jsonify({
        "success": True,
        "demonstrations": results,
        "two_community_split": two_community_split,
    }), 200
