"""Integration tests for SpectraGraph Flask page routes and REST API endpoints."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import tempfile
import pytest

import db.database as db_module

# Dynamically import create_app from root app.py (distinguishing from app/ package)
_APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
_spec = importlib.util.spec_from_file_location("root_app", _APP_PATH)
_root_app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root_app)
create_app = _root_app.create_app


@pytest.fixture
def app(monkeypatch):
    """Create a fresh test Flask app instance with an isolated temporary SQLite DB."""
    temp_dir = tempfile.mkdtemp()
    temp_db_path = os.path.join(temp_dir, "test_spectragraph.db")
    monkeypatch.setattr(db_module, "DB_PATH", temp_db_path)

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    yield flask_app

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    """Flask test client fixture."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Page routes (Phase 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route",
    [
        "/",
        "/graph-builder",
        "/analysis",
        "/saved-graphs",
        "/about",
    ],
)
def test_all_navigation_pages(client, route):
    """All 5 Phase 2 page routes return HTTP 200."""
    response = client.get(route)
    assert response.status_code == 200


def test_database_tables_exist(app):
    """All 4 required tables (graphs, nodes, edges, analysis_results) exist on startup."""
    conn = db_module.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}
        required = {"graphs", "nodes", "edges", "analysis_results"}
        assert required.issubset(tables), f"Missing tables: {required - tables}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Graph CRUD API tests
# ---------------------------------------------------------------------------


def test_graph_crud_lifecycle(client):
    """Test POST, GET list, GET single, PUT update, and DELETE /api/graphs."""
    payload = {
        "name": "Triangle Graph",
        "description": "Complete graph on 3 vertices (K3)",
        "nodes": [{"label": "v0"}, {"label": "v1"}, {"label": "v2"}],
        "edges": [
            {"source": 0, "target": 1},
            {"source": 1, "target": 2},
            {"source": 2, "target": 0},
        ],
    }
    post_res = client.post("/api/graphs", json=payload)
    assert post_res.status_code == 201
    post_data = post_res.get_json()
    assert post_data["success"] is True
    graph_id = post_data["graph_id"]
    assert isinstance(graph_id, int)

    # List graphs
    list_res = client.get("/api/graphs")
    assert list_res.status_code == 200
    graphs_list = list_res.get_json()["graphs"]
    assert len(graphs_list) == 1
    assert graphs_list[0]["id"] == graph_id
    assert graphs_list[0]["node_count"] == 3
    assert graphs_list[0]["edge_count"] == 3

    # Retrieve single graph
    get_res = client.get(f"/api/graphs/{graph_id}")
    assert get_res.status_code == 200
    graph = get_res.get_json()
    assert graph["name"] == "Triangle Graph"
    assert [n["label"] for n in graph["nodes"]] == ["v0", "v1", "v2"]
    assert len(graph["edges"]) == 3

    # Update graph via PUT
    put_res = client.put(
        f"/api/graphs/{graph_id}",
        json={
            "name": "Path P4",
            "description": "Updated to 4-node path",
            "nodes": [{"label": "a"}, {"label": "b"}, {"label": "c"}, {"label": "d"}],
            "edges": [{"source": 0, "target": 1}, {"source": 1, "target": 2}, {"source": 2, "target": 3}],
        },
    )
    assert put_res.status_code == 200
    put_data = put_res.get_json()
    assert put_data["success"] is True
    assert put_data["graph"]["name"] == "Path P4"
    assert len(put_data["graph"]["nodes"]) == 4
    assert len(put_data["graph"]["edges"]) == 3

    # Delete graph
    del_res = client.delete(f"/api/graphs/{graph_id}")
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True
    assert client.get(f"/api/graphs/{graph_id}").status_code == 404


def test_graph_crud_validation_and_not_found(client):
    """Missing name returns 400; missing graph IDs return 404."""
    bad_post = client.post("/api/graphs", json={"name": "   ", "nodes": [], "edges": []})
    assert bad_post.status_code == 400

    assert client.get("/api/graphs/9999").status_code == 404
    assert client.put("/api/graphs/9999", json={"name": "X"}).status_code == 404
    assert client.delete("/api/graphs/9999").status_code == 404


def test_get_graph_stats(client):
    """Save a graph and confirm db stats reflect updated counts."""
    initial_stats = db_module.get_graph_stats()
    payload = {
        "name": "Stats Star S4",
        "description": "Star graph with center and 3 leaves",
        "nodes": [{"label": "Center"}, {"label": "L1"}, {"label": "L2"}, {"label": "L3"}],
        "edges": [{"source": 0, "target": 1}, {"source": 0, "target": 2}, {"source": 0, "target": 3}],
    }
    res = client.post("/api/graphs", json=payload)
    assert res.status_code == 201

    updated_stats = db_module.get_graph_stats()
    assert updated_stats["total_graphs"] == initial_stats["total_graphs"] + 1
    assert updated_stats["total_nodes"] == initial_stats["total_nodes"] + 4
    assert updated_stats["total_edges"] == initial_stats["total_edges"] + 3


# ---------------------------------------------------------------------------
# Sample & Random graph generation routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_type,expected_name,expected_nodes,expected_edges",
    [
        ("path", "Path Graph P6", 6, 5),
        ("cycle", "Cycle Graph C6", 6, 6),
        ("complete", "Complete Graph K5", 5, 10),
        ("star", "Star Graph S6", 6, 5),
        ("disconnected", "Disconnected Graph", 6, 6),
        ("two_community", "Two-Community Graph", 10, 18),
        ("petersen", "Petersen Graph", 10, 15),
    ],
)
def test_all_sample_graphs(client, sample_type, expected_name, expected_nodes, expected_edges):
    """POST /api/graphs/sample creates all 7 canonical sample graphs accurately."""
    res = client.post("/api/graphs/sample", json={"type": sample_type})
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    graph = data["graph"]
    assert graph["name"] == expected_name
    assert len(graph["nodes"]) == expected_nodes
    assert len(graph["edges"]) == expected_edges


def test_sample_graph_invalid_type(client):
    """Unknown sample graph type returns 400."""
    res = client.post("/api/graphs/sample", json={"type": "dodecahedron"})
    assert res.status_code == 400


def test_random_graph_generation(client):
    """POST /api/graphs/random generates valid Erdos-Renyi graphs and validates bounds."""
    # Empty edge probability (p=0.0) -> 0 edges
    res_zero = client.post("/api/graphs/random", json={"node_count": 6, "edge_probability": 0.0})
    assert res_zero.status_code == 201
    g_zero = res_zero.get_json()["graph"]
    assert len(g_zero["nodes"]) == 6
    assert len(g_zero["edges"]) == 0

    # Full edge probability (p=1.0) -> complete graph K5 with 10 edges
    res_full = client.post("/api/graphs/random", json={"node_count": 5, "edge_probability": 1.0})
    assert res_full.status_code == 201
    g_full = res_full.get_json()["graph"]
    assert len(g_full["nodes"]) == 5
    assert len(g_full["edges"]) == 10

    # Invalid parameters return 400
    assert client.post("/api/graphs/random", json={"node_count": 1, "edge_probability": 0.5}).status_code == 400
    assert client.post("/api/graphs/random", json={"node_count": 8, "edge_probability": 1.5}).status_code == 400


# ---------------------------------------------------------------------------
# Spectral analysis API routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample_type,expected_components,expected_connected",
    [
        ("two_community", 1, True),
        ("disconnected", 2, False),
        ("petersen", 1, True),
    ],
)
def test_analyze_and_retrieve_analysis(client, sample_type, expected_components, expected_connected):
    """POST /api/analyze/<id> computes and persists results where spectral == bfs == union_find."""
    sample_res = client.post("/api/graphs/sample", json={"type": sample_type})
    graph_id = sample_res.get_json()["graph_id"]

    analyze_res = client.post(f"/api/analyze/{graph_id}", json={"method": "auto"})
    assert analyze_res.status_code == 200
    data = analyze_res.get_json()

    assert data["success"] is True
    assert data["all_agree"] is True
    assert data["component_count_spectral"] == expected_components
    assert data["component_count_bfs"] == expected_components
    assert data["component_count_union_find"] == expected_components
    assert data["is_connected"] is expected_connected
    assert data["laplacian_verification"] == {
        "is_symmetric": True,
        "row_sums_zero": True,
        "is_positive_semidefinite": True,
    }
    assert data["matrix_validation"]["is_valid"] is True

    if sample_type == "two_community":
        assert data["fiedler"]["can_partition"] is True
        g1 = frozenset(data["fiedler"]["partition"]["group_1"])
        g2 = frozenset(data["fiedler"]["partition"]["group_2"])
        assert {g1, g2} == {frozenset(range(0, 5)), frozenset(range(5, 10))}
    elif sample_type == "disconnected":
        assert data["fiedler"]["can_partition"] is False
        assert data["fiedler"]["partition"] is None

    # Retrieve persisted analysis via GET /api/analysis/<id>
    hist_res = client.get(f"/api/analysis/{graph_id}")
    assert hist_res.status_code == 200
    hist_data = hist_res.get_json()
    assert hist_data["success"] is True
    assert hist_data["latest"]["id"] == data["analysis_id"]
    assert hist_data["latest"]["component_count_spectral"] == expected_components
    assert hist_data["latest"]["component_count_bfs"] == expected_components
    assert hist_data["latest"]["component_count_union_find"] == expected_components


def test_analyze_error_cases(client):
    """Invalid graph_id returns 404; unsupported method returns 400."""
    assert client.post("/api/analyze/9999", json={}).status_code == 404
    assert client.get("/api/analysis/9999").status_code == 404

    gid = client.post("/api/graphs/sample", json={"type": "path"}).get_json()["graph_id"]
    bad_method = client.post(f"/api/analyze/{gid}", json={"method": "invalid"})
    assert bad_method.status_code == 400


# ---------------------------------------------------------------------------
# Export, Import, and Eigenvalue Plot API routes
# ---------------------------------------------------------------------------


def test_export_and_import_json_and_csv(client):
    """Test JSON and CSV export and round-trip file import via /api/graphs/import."""
    sample_res = client.post("/api/graphs/sample", json={"type": "cycle"})
    graph_id = sample_res.get_json()["graph_id"]

    # Export JSON
    exp_json = client.get(f"/api/graphs/{graph_id}/export?format=json")
    assert exp_json.status_code == 200
    assert "application/json" in exp_json.content_type
    exported_payload = json.loads(exp_json.data.decode("utf-8"))
    assert len(exported_payload["nodes"]) == 6
    assert len(exported_payload["edges"]) == 6

    # Re-import exported JSON file
    imp_json = client.post(
        "/api/graphs/import",
        data={"file": (io.BytesIO(exp_json.data), "cycle.json")},
        content_type="multipart/form-data",
    )
    assert imp_json.status_code == 201
    imp_json_data = imp_json.get_json()
    assert imp_json_data["success"] is True
    assert len(imp_json_data["graph"]["nodes"]) == 6
    assert len(imp_json_data["graph"]["edges"]) == 6

    # Export CSV
    exp_csv = client.get(f"/api/graphs/{graph_id}/export?format=csv")
    assert exp_csv.status_code == 200
    assert "text/csv" in exp_csv.content_type
    csv_text = exp_csv.data.decode("utf-8")
    csv_lines = [line.strip() for line in csv_text.strip().splitlines()]
    assert csv_lines[0] == "source,target"
    assert len(csv_lines) == 7  # header + 6 edges

    # Re-import exported CSV file
    imp_csv = client.post(
        "/api/graphs/import",
        data={"file": (io.BytesIO(exp_csv.data), "cycle.csv")},
        content_type="multipart/form-data",
    )
    assert imp_csv.status_code == 201
    imp_csv_data = imp_csv.get_json()
    assert imp_csv_data["success"] is True
    assert len(imp_csv_data["graph"]["nodes"]) == 6
    assert len(imp_csv_data["graph"]["edges"]) == 6

    # Unsupported export format
    assert client.get(f"/api/graphs/{graph_id}/export?format=xml").status_code == 400


@pytest.mark.parametrize(
    "filename,content",
    [
        ("empty.json", b""),
        ("malformed.json", b"{not valid json"),
        ("missing_fields.json", json.dumps({"name": "Bad", "nodes": []}).encode("utf-8")),
        ("empty_nodes.json", json.dumps({"nodes": [], "edges": []}).encode("utf-8")),
        ("bad_csv.csv", b"source,target\nonly_one_column\n"),
        ("header_only.csv", b"source,target\n"),
        ("bad_ext.xml", b"<graph></graph>"),
        ("bad_encoding.json", b"\xff\xfe\x00\x00"),
    ],
)
def test_import_rejects_invalid_files(client, filename, content):
    """POST /api/graphs/import returns HTTP 400 for malformed or unsupported files."""
    res = client.post(
        "/api/graphs/import",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_eigenvalue_plot_endpoint(client):
    """GET /api/graphs/<id>/eigenvalue-plot returns a valid PNG image."""
    sample_res = client.post("/api/graphs/sample", json={"type": "star"})
    graph_id = sample_res.get_json()["graph_id"]

    plot_res = client.get(f"/api/graphs/{graph_id}/eigenvalue-plot")
    assert plot_res.status_code == 200
    assert plot_res.mimetype == "image/png"
    assert plot_res.data.startswith(b"\x89PNG\r\n\x1a\n")

    # Empty graph (0 nodes) also renders a valid PNG without error
    empty_id = client.post(
        "/api/graphs",
        json={"name": "Empty", "nodes": [], "edges": []},
    ).get_json()["graph_id"]
    empty_plot = client.get(f"/api/graphs/{empty_id}/eigenvalue-plot")
    assert empty_plot.status_code == 200
    assert empty_plot.mimetype == "image/png"

    # Missing graph returns 404
    assert client.get("/api/graphs/9999/eigenvalue-plot").status_code == 404


def test_demonstrations_and_null_space_api(client):
    """GET /api/demonstrations verifies 6 graphs and /api/analyze returns null_space."""
    demo_res = client.get("/api/demonstrations")
    assert demo_res.status_code == 200
    demo_data = demo_res.get_json()
    assert demo_data["success"] is True
    assert len(demo_data["demonstrations"]) == 6
    assert all(row["all_agree"] is True for row in demo_data["demonstrations"])
    assert demo_data["two_community_split"] is not None
    assert len(demo_data["two_community_split"]["group_1_labels"]) == 5
    assert len(demo_data["two_community_split"]["group_2_labels"]) == 5

    # Verify null_space payload in /api/analyze/<id>
    gid = client.post("/api/graphs/sample", json={"type": "disconnected"}).get_json()["graph_id"]
    an_res = client.post(f"/api/analyze/{gid}", json={})
    assert an_res.status_code == 200
    an_data = an_res.get_json()
    assert an_data["null_space"]["dimension"] == 2
    assert len(an_data["null_space"]["component_indicators"]) == 2
    assert an_data["null_space"]["max_residual"] < 1e-8
