"""Unit and integration tests for the SQLite persistence layer (db/database.py)."""

from __future__ import annotations

import os
import sqlite3
import numpy as np
import pytest

import db.database as db_module


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Configure an isolated temporary SQLite database and initialize schema."""
    db_path = os.path.join(str(tmp_path), "test_spectragraph.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    db_module.init_db()
    return db_path


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_schema_tables_and_columns(temp_db):
    """Verify all 4 tables exist with all expected columns."""
    expected_columns = {
        "graphs": {"id", "name", "description", "created_at", "updated_at"},
        "nodes": {"id", "graph_id", "label", "position_x", "position_y"},
        "edges": {"id", "graph_id", "source_node_id", "target_node_id"},
        "analysis_results": {
            "id",
            "graph_id",
            "adjacency_matrix",
            "degree_matrix",
            "laplacian_matrix",
            "eigenvalues",
            "eigenvectors",
            "component_count_spectral",
            "component_count_bfs",
            "component_count_union_find",
            "fiedler_value",
            "fiedler_vector",
            "group_assignments",
            "method_used",
            "is_connected",
            "analysis_date",
        },
    }

    conn = db_module.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}
        assert set(expected_columns.keys()).issubset(tables)

        for table, cols in expected_columns.items():
            cursor.execute(f"PRAGMA table_info({table})")
            actual_cols = {row["name"] for row in cursor.fetchall()}
            assert cols.issubset(actual_cols), f"Missing columns in {table}: {cols - actual_cols}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Graph CRUD and cascade tests
# ---------------------------------------------------------------------------


def test_save_get_and_update_graph_data(temp_db):
    """Test save_graph_data, get_graph, and update_graph_data round-trip integrity."""
    nodes = [
        {"label": "v1", "x": 10.5, "y": 20.5},
        {"label": "v2", "x": 30.0, "y": 40.0},
        {"label": "v3", "x": 50.0, "y": 60.0},
    ]
    edges = [{"source": 0, "target": 1}, {"source": 1, "target": 2}]

    graph_id = db_module.save_graph_data("Path P3", "Initial 3-node path", nodes, edges)
    assert isinstance(graph_id, int)

    loaded = db_module.get_graph(graph_id)
    assert loaded is not None
    assert loaded["name"] == "Path P3"
    assert loaded["description"] == "Initial 3-node path"
    assert len(loaded["nodes"]) == 3
    assert [n["label"] for n in loaded["nodes"]] == ["v1", "v2", "v3"]
    assert loaded["nodes"][0]["position_x"] == pytest.approx(10.5)
    assert loaded["nodes"][0]["position_y"] == pytest.approx(20.5)
    assert len(loaded["edges"]) == 2

    # Update graph metadata, nodes (4 nodes), and edges (cycle C4)
    new_nodes = [{"label": f"n{i}", "position_x": float(i * 10), "position_y": 0.0} for i in range(4)]
    new_edges = [{"source": i, "target": (i + 1) % 4} for i in range(4)]
    updated = db_module.update_graph_data(graph_id, "Cycle C4", "Updated to C4", new_nodes, new_edges)
    assert updated is True

    reloaded = db_module.get_graph(graph_id)
    assert reloaded is not None
    assert reloaded["name"] == "Cycle C4"
    assert reloaded["description"] == "Updated to C4"
    assert [n["label"] for n in reloaded["nodes"]] == ["n0", "n1", "n2", "n3"]
    assert len(reloaded["edges"]) == 4

    # Updating or retrieving non-existent IDs
    assert db_module.update_graph_data(99999, "Ghost", "", [], []) is False
    assert db_module.get_graph(99999) is None


def test_delete_graph_cascades_nodes_edges_and_analyses(temp_db):
    """Deleting a graph must cascade-delete its nodes, edges, and analysis_results."""
    graph_id = db_module.save_graph_data(
        "Cascade K3",
        "Triangle for cascade test",
        [{"label": "a"}, {"label": "b"}, {"label": "c"}],
        [{"source": 0, "target": 1}, {"source": 1, "target": 2}, {"source": 2, "target": 0}],
    )
    db_module.save_analysis_result(
        graph_id,
        {
            "adjacency_matrix": [[0, 1, 1], [1, 0, 1], [1, 1, 0]],
            "degree_matrix": [[2, 0, 0], [0, 2, 0], [0, 0, 2]],
            "laplacian_matrix": [[2, -1, -1], [-1, 2, -1], [-1, -1, 2]],
            "eigenvalues": [0.0, 3.0, 3.0],
            "eigenvectors": np.eye(3),
            "component_count_spectral": 1,
            "component_count_bfs": 1,
            "component_count_union_find": 1,
            "lambda_2": 3.0,
            "fiedler_vector": [0.0, 0.707, -0.707],
            "group_assignments": [1, 1, 2],
            "method_used": "jacobi",
            "is_connected": True,
        },
    )

    assert db_module.delete_graph(graph_id) is True
    assert db_module.delete_graph(graph_id) is False
    assert db_module.get_graph(graph_id) is None

    conn = db_module.get_db_connection()
    try:
        cursor = conn.cursor()
        for table in ("nodes", "edges", "analysis_results"):
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE graph_id = ?", (graph_id,))
            assert cursor.fetchone()[0] == 0, f"Orphan rows remain in {table}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Analysis results persistence tests
# ---------------------------------------------------------------------------


def test_analysis_results_save_get_latest_and_get_all(temp_db):
    """Verify save_analysis_result, get_analysis_results, get_latest_analysis, and get_all_analyses."""
    g1_id = db_module.save_graph_data(
        "Graph One",
        "K2 graph",
        [{"label": "u"}, {"label": "v"}],
        [{"source": 0, "target": 1}],
    )
    g2_id = db_module.save_graph_data(
        "Graph Two",
        "Isolated pair",
        [{"label": "p"}, {"label": "q"}],
        [],
    )

    assert db_module.get_latest_analysis(g1_id) is None
    assert db_module.get_analysis_results(g1_id) == []

    # Save two analyses for g1 (second one uses numpy arrays to test serialization)
    first_id = db_module.save_analysis_result(
        g1_id,
        {
            "adjacency_matrix": [[0, 1], [1, 0]],
            "degree_matrix": [[1, 0], [0, 1]],
            "laplacian_matrix": [[1, -1], [-1, 1]],
            "eigenvalues": [0.0, 2.0],
            "eigenvectors": [[0.7071, 0.7071], [0.7071, -0.7071]],
            "component_count_spectral": 1,
            "component_count_bfs": 1,
            "component_count_union_find": 1,
            "fiedler_value": 2.0,
            "fiedler_vector": [0.7071, -0.7071],
            "group_assignments": [1, 2],
            "method_used": "jacobi",
            "is_connected": True,
        },
    )
    second_id = db_module.save_analysis_result(
        g1_id,
        {
            "adjacency_matrix": np.array([[0.0, 1.0], [1.0, 0.0]]),
            "degree_matrix": np.eye(2),
            "laplacian_matrix": np.array([[1.0, -1.0], [-1.0, 1.0]]),
            "eigenvalues": np.array([0.0, 2.0]),
            "eigenvectors": np.eye(2),
            "component_count_spectral": 1,
            "component_count_bfs": 1,
            "component_count_union_find": 1,
            "lambda_2": 2.0,
            "fiedler_vector": np.array([0.7071, -0.7071]),
            "group_assignments": [1, 2],
            "method_used": "numpy",
            "is_connected": True,
        },
    )
    third_id = db_module.save_analysis_result(
        g2_id,
        {
            "adjacency_matrix": [[0, 0], [0, 0]],
            "degree_matrix": [[0, 0], [0, 0]],
            "laplacian_matrix": [[0, 0], [0, 0]],
            "eigenvalues": [0.0, 0.0],
            "eigenvectors": [[1.0, 0.0], [0.0, 1.0]],
            "component_count_spectral": 2,
            "component_count_bfs": 2,
            "component_count_union_find": 2,
            "fiedler_value": 0.0,
            "fiedler_vector": [0.0, 1.0],
            "group_assignments": None,
            "method_used": "auto",
            "is_connected": False,
        },
    )

    g1_history = db_module.get_analysis_results(g1_id)
    assert [row["id"] for row in g1_history] == [second_id, first_id]
    assert g1_history[0]["method_used"] == "numpy"
    assert g1_history[0]["is_connected"] is True
    assert g1_history[0]["eigenvalues"] == [0.0, 2.0]
    assert g1_history[0]["laplacian_matrix"] == [[1.0, -1.0], [-1.0, 1.0]]

    latest_g1 = db_module.get_latest_analysis(g1_id)
    assert latest_g1 is not None
    assert latest_g1["id"] == second_id

    all_analyses = db_module.get_all_analyses()
    assert len(all_analyses) == 3
    ids = {row["id"] for row in all_analyses}
    assert ids == {first_id, second_id, third_id}
    names_by_id = {row["id"]: row["graph_name"] for row in all_analyses}
    assert names_by_id[first_id] == "Graph One"
    assert names_by_id[third_id] == "Graph Two"


# ---------------------------------------------------------------------------
# Transaction rollback & error handling tests
# ---------------------------------------------------------------------------


def test_transaction_rollback_and_foreign_key_errors(temp_db):
    """Invalid DB operations raise errors and roll back partial transactions cleanly."""
    # Foreign key constraint rejects analysis for non-existent graph_id
    with pytest.raises(sqlite3.IntegrityError):
        db_module.save_analysis_result(
            99999,
            {
                "eigenvalues": [0.0],
                "component_count_spectral": 1,
                "component_count_bfs": 1,
                "component_count_union_find": 1,
            },
        )

    # NOT NULL constraint on graphs.name rejects None
    with pytest.raises(sqlite3.IntegrityError):
        db_module.save_graph_data(None, "Invalid", [{"label": "v1"}], [])  # type: ignore[arg-type]

    # Mid-transaction ValueError during node insertion must roll back the parent graph row
    with pytest.raises(ValueError):
        db_module.save_graph_data(
            "Broken Graph",
            "Should roll back",
            [{"label": "ok", "x": 1.0}, {"label": "bad", "x": "not-a-float"}],
            [],
        )
    assert db_module.get_graphs() == []

    # Mid-transaction error in update_graph_data must preserve original graph, nodes, and edges
    gid = db_module.save_graph_data(
        "Stable Graph",
        "Original",
        [{"label": "a"}, {"label": "b"}],
        [{"source": 0, "target": 1}],
    )
    with pytest.raises(ValueError):
        db_module.update_graph_data(
            gid,
            "Corrupted Update",
            "Should revert",
            [{"label": "x", "x": "bad-coord"}],
            [],
        )

    restored = db_module.get_graph(gid)
    assert restored is not None
    assert restored["name"] == "Stable Graph"
    assert restored["description"] == "Original"
    assert [n["label"] for n in restored["nodes"]] == ["a", "b"]
    assert len(restored["edges"]) == 1
