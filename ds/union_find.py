"""Disjoint Set Union (Union-Find) data structure for graph connectivity."""

from __future__ import annotations


class UnionFind:
    """
    Disjoint Set Union (Union-Find) data structure.

    Implements:
    - Path compression in find()
    - Union by rank in union()
    """

    def __init__(self, n: int):
        """Initialize n disjoint sets."""
        if n < 0:
            raise ValueError(f"Number of nodes n must be non-negative, got {n}.")
        self.parent = list(range(n))
        self.rank = [0] * n
        self.component_count = n

    def _validate_node(self, x: int) -> None:
        if not (0 <= x < len(self.parent)):
            raise ValueError(
                f"Node index {x} is out of bounds for n={len(self.parent)} nodes."
            )

    def find(self, x: int) -> int:
        """Find root with path compression."""
        self._validate_node(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]

        while self.parent[x] != root:
            next_parent = self.parent[x]
            self.parent[x] = root
            x = next_parent

        return root

    def union(self, x: int, y: int) -> bool:
        """Union by rank. Returns True if merged, False if already same set."""
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return False

        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1

        self.component_count -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        """Check if x and y are in same component."""
        return self.find(x) == self.find(y)

    def get_components(self) -> dict:
        """
        Returns:
        {
            'component_count': int,
            'components': list of lists,
            'component_map': dict mapping node -> component_id
        }
        """
        n = len(self.parent)
        if n == 0:
            return {
                "component_count": 0,
                "components": [],
                "component_map": {},
            }

        groups: dict[int, list[int]] = {}
        for node in range(n):
            root = self.find(node)
            groups.setdefault(root, []).append(node)

        components = sorted(groups.values(), key=lambda comp: comp[0])
        component_map: dict[int, int] = {}
        for comp_id, comp in enumerate(components):
            for node in comp:
                component_map[node] = comp_id

        return {
            "component_count": self.component_count,
            "components": components,
            "component_map": component_map,
        }


def union_find_components(n: int, edges: list[tuple[int, int]]) -> dict:
    """Convenience function: build UF from edges and return component info."""
    uf = UnionFind(n)
    for edge in edges:
        if len(edge) != 2:
            raise ValueError(f"Each edge must be a pair (u, v), got {edge!r}.")
        u, v = int(edge[0]), int(edge[1])
        uf.union(u, v)
    return uf.get_components()
