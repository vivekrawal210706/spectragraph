"""Breadth-First Search (BFS) connected components and adjacency list helpers."""

from __future__ import annotations

from collections import deque


def edges_to_adj_list(n: int, edges: list[tuple[int, int]]) -> dict[int, list[int]]:
    """Convert edge list to adjacency list for all n nodes."""
    if n < 0:
        raise ValueError(f"Number of nodes n must be non-negative, got {n}.")

    neighbors: dict[int, set[int]] = {i: set() for i in range(n)}
    for edge in edges:
        if len(edge) != 2:
            raise ValueError(f"Each edge must be a pair (u, v), got {edge!r}.")
        u, v = int(edge[0]), int(edge[1])
        if not (0 <= u < n and 0 <= v < n):
            raise ValueError(f"Edge ({u}, {v}) is out of bounds for n={n} nodes.")
        if u == v:
            continue
        neighbors[u].add(v)
        neighbors[v].add(u)

    return {node: sorted(nbrs) for node, nbrs in neighbors.items()}


def bfs_connected_components(n: int, adj_list: dict[int, list[int]]) -> dict:
    """
    Count connected components using BFS.

    Parameters:
        n: number of nodes (0 to n-1)
        adj_list: adjacency list {node: [neighbors]}

    Returns:
    {
        'component_count': int,
        'components': list of lists (each component's node indices),
        'component_map': dict mapping node -> component_id
    }

    Implementation:
    - Use collections.deque as queue
    - Track visited set
    - For each unvisited node, start new BFS traversal
    - Handle isolated nodes (no neighbors)
    - Handle empty graph (n=0)
    """
    if n < 0:
        raise ValueError(f"Number of nodes n must be non-negative, got {n}.")

    if n == 0:
        return {
            "component_count": 0,
            "components": [],
            "component_map": {},
        }

    visited: set[int] = set()
    components: list[list[int]] = []
    component_map: dict[int, int] = {}

    for start in range(n):
        if start in visited:
            continue

        comp_id = len(components)
        component: list[int] = []
        queue: deque[int] = deque([start])
        visited.add(start)

        while queue:
            node = queue.popleft()
            component.append(node)
            component_map[node] = comp_id

            for neighbor in adj_list.get(node, []):
                if 0 <= neighbor < n and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        components.append(sorted(component))

    return {
        "component_count": len(components),
        "components": components,
        "component_map": component_map,
    }
