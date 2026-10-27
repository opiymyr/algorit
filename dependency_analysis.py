import re
import sys
from collections import deque
from typing import Dict, List, Optional, Set, Tuple


class DependencyGraph:
    def __init__(self) -> None:
        self.deps: Dict[str, Dict[str, float]] = {}

    def add_component(self, name: str) -> None:
        self.deps.setdefault(name, {})

    def add_dependency(self, from_: str, to: str, weight: float = 1) -> None:
        self.add_component(from_)
        self.add_component(to)      
        self.deps[from_][to] = weight

    def get_topological_order(self) -> Optional[List[str]]:
        remaining = {v: len(d) for v, d in self.deps.items()}
        dependents: Dict[str, List[str]] = {v: [] for v in self.deps}
        for v, d in self.deps.items():
            for u in d:
                dependents[u].append(v)

        queue = deque(v for v, n in remaining.items() if n == 0)
        order: List[str] = []
        while queue:
            v = queue.popleft()
            order.append(v)
            for parent in dependents[v]:
                remaining[parent] -= 1
                if remaining[parent] == 0:
                    queue.append(parent)

        return order if len(order) == len(self.deps) else None

    def is_acyclic(self) -> bool:
        return self.get_topological_order() is not None

    def find_cycle(self) -> Optional[List[str]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {v: WHITE for v in self.deps}
        stack: List[str] = []

        def dfs(v: str) -> Optional[List[str]]:
            color[v] = GRAY
            stack.append(v)
            for u in self.deps[v]:
                if color[u] == GRAY:                     
                    return stack[stack.index(u):] + [u]
                if color[u] == WHITE:
                    c = dfs(u)
                    if c:
                        return c
            stack.pop()
            color[v] = BLACK
            return None

        for v in self.deps:
            if color[v] == WHITE:
                c = dfs(v)
                if c:
                    return c
        return None

    @classmethod
    def from_file(cls, path: str) -> "DependencyGraph":
        g = cls()
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^(\S+)\s+зависит\s+от\s*(.*)$", line)
                if not m:
                    raise ValueError(f"Неверный формат строки: {line!r}")
                name, rest = m.groups()
                g.add_component(name)
                for item in filter(None, (s.strip() for s in rest.split(","))):
                    mm = re.match(r"^(\S+?)(?:\((\d+(?:\.\d+)?)\))?$", item)
                    g.add_dependency(name, mm.group(1), float(mm.group(2) or 1))
        return g

    def critical_path(self) -> Optional[Tuple[List[str], float]]:       
        order = self.get_topological_order()
        if order is None:
            return None
        best: Dict[str, Tuple[float, Optional[str]]] = {}
        for v in order:                       
            best[v] = (0, None)
            for u, w in self.deps[v].items():
                cand = best[u][0] + w
                if cand > best[v][0]:
                    best[v] = (cand, u)
        end = max(best, key=lambda v: best[v][0])
        total, path = best[end][0], []
        node: Optional[str] = end
        while node is not None:
            path.append(node)
            node = best[node][1]
        return path, total

    def to_dot(self) -> str:
        lines = ["digraph deps {", "  rankdir=LR;"]
        for v, d in self.deps.items():
            lines.append(f'  "{v}";')
            for u, w in d.items():
                lines.append(f'  "{v}" -> "{u}" [label="{w:g}"];')
        lines.append("}")
        return "\n".join(lines)

    def _layout(self) -> Dict[str, Tuple[float, float]]:
        import math
        order = self.get_topological_order()
        R, W, H = 24, 170, 90
        pos: Dict[str, Tuple[float, float]] = {}
        if order is not None:
            level: Dict[str, int] = {}
            for v in order:
                level[v] = max((level[u] + 1 for u in self.deps[v]), default=0)
            rows: Dict[int, int] = {}
            for v in order:
                r = rows.get(level[v], 0)
                rows[level[v]] = r + 1
                pos[v] = (60 + level[v] * W, 60 + r * H + (level[v] % 2) * 70)
        else:
            n = len(self.deps)
            for i, v in enumerate(self.deps):
                a = 2 * math.pi * i / n
                pos[v] = (250 + 180 * math.cos(a), 250 + 180 * math.sin(a))
        return pos

    def to_svg(self) -> str:
        import math
        R = 24
        pos = self._layout()
        width = int(max(x for x, _ in pos.values()) + 60)
        height = int(max(y for _, y in pos.values()) + 60)
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
               f'font-family="Arial" font-size="14">',
               '<rect width="100%" height="100%" fill="white"/>',
               '<defs><marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" '
               'orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#444"/></marker></defs>']
        for v, d in self.deps.items():
            for u, w in d.items():
                (x1, y1), (x2, y2) = pos[v], pos[u]
                dist = math.hypot(x2 - x1, y2 - y1) or 1
                dx, dy = (x2 - x1) / dist, (y2 - y1) / dist
                sx, sy = x1 + dx * R, y1 + dy * R
                ex, ey = x2 - dx * (R + 2), y2 - dy * (R + 2)
                out.append(f'<line x1="{sx:.0f}" y1="{sy:.0f}" x2="{ex:.0f}" y2="{ey:.0f}" '
                           f'stroke="#444" stroke-width="1.5" marker-end="url(#a)"/>')
                out.append(f'<text x="{(sx+ex)/2:.0f}" y="{(sy+ey)/2 - 5:.0f}" fill="#b00" '
                           f'text-anchor="middle">{w:g}</text>')
        for v, (x, y) in pos.items():
            out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{R}" fill="#cfe3ff" stroke="#235"/>')
            out.append(f'<text x="{x:.0f}" y="{y + 5:.0f}" text-anchor="middle" '
                       f'font-weight="bold">{v}</text>')
        out.append("</svg>")
        return "\n".join(out)

    def visualize(self, filename: str = "graph") -> str:
        """graphviz -> PNG; нет - networkx+matplotlib -> PNG; нет - собственный SVG."""
        try:
            import graphviz
            return graphviz.Source(self.to_dot()).render(filename, format="png", cleanup=True)
        except Exception as e:
            print(f"[graphviz недоступен: {type(e).__name__}: {e}]")
        try:
            import networkx as nx
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            G = nx.DiGraph()
            for v, d in self.deps.items():
                G.add_node(v)
                for u, w in d.items():
                    G.add_edge(v, u, weight=w)
            pos = {k: (x, -y) for k, (x, y) in self._layout().items()}
            plt.figure(figsize=(8, 5))
            nx.draw(G, pos, with_labels=True, node_color="#cfe3ff",
                    node_size=1200, arrowsize=20,
                    connectionstyle="arc3,rad=0.12")
            nx.draw_networkx_edge_labels(
                G, pos, edge_labels={(a, b): f"{w:g}" for a, b, w in
                                     ((a, b, d["weight"]) for a, b, d in G.edges(data=True))})
            plt.savefig(filename + ".png", dpi=120)
            plt.close()
            return filename + ".png"
        except Exception as e:
            print(f"[networkx/matplotlib не сработали: {type(e).__name__}: {e}]")
        with open(filename + ".dot", "w", encoding="utf-8") as f:
            f.write(self.to_dot())
        with open(filename + ".svg", "w", encoding="utf-8") as f:
            f.write(self.to_svg())
        return filename + ".svg"


class DependencyAnalyzer:
    def __init__(self, graph: DependencyGraph) -> None:
        self.graph = graph
        self._cache: Dict[str, Set[str]] = {}   # кэш для DFS

    def _check(self, start: str) -> None:
        if start not in self.graph.deps:
            raise KeyError(f"Компонент {start!r} не найден")

    def find_dependencies_bfs(self, start: str, unique: bool = False) -> List[List[str]]:
        self._check(start)
        levels: List[List[str]] = []
        if unique:
            seen = {start}
            frontier = [start]
            while frontier:
                nxt = []
                for v in frontier:
                    for u in self.graph.deps[v]:
                        if u not in seen:
                            seen.add(u)
                            nxt.append(u)
                if nxt:
                    levels.append(nxt)
                frontier = nxt
            return levels

        expanded = {start}
        frontier = [start]
        while frontier:
            names, nxt = [], []
            for v in frontier:
                for u in self.graph.deps[v]:
                    names.append(u)
                    if u not in expanded:
                        expanded.add(u)
                        nxt.append(u)
            if names:
                levels.append(list(dict.fromkeys(names)))
            frontier = nxt
        return levels

    def find_dependencies_dfs(self, start: str) -> Set[str]:
        self._check(start)
        if self.graph.is_acyclic():
            return set(self._dfs_cached(start))      
        visited: Set[str] = set()                   

        def dfs(v: str) -> None:
            for u in self.graph.deps[v]:
                if u not in visited:
                    visited.add(u)
                    dfs(u)
        dfs(start)
        visited.discard(start)
        return visited

    def _dfs_cached(self, v: str) -> Set[str]:
        if v in self._cache:
            return self._cache[v]
        result: Set[str] = set()
        for u in self.graph.deps[v]:
            result.add(u)
            result |= self._dfs_cached(u)
        self._cache[v] = result
        return result


SAMPLE = """A зависит от B(2), C(1)
B зависит от D(3)
C зависит от D(1), E(2)
E зависит от B(1)
"""

def report(g: DependencyGraph, start: str = "A") -> None:
    order = g.get_topological_order()
    print("Топологическая сортировка:",
          order if order else f"Обнаружен цикл: {' -> '.join(g.find_cycle())}")
    if order is None:
        return
    an = DependencyAnalyzer(g)
    print(f"BFS для {start} (как в примере):", an.find_dependencies_bfs(start))
    print(f"BFS для {start} (unique=True):  ", an.find_dependencies_bfs(start, unique=True))
    print(f"DFS для {start}:", sorted(an.find_dependencies_dfs(start)))
    path, total = g.critical_path()
    print("Критический путь:", " -> ".join(path), f"(вес {total:g})")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path is None:
        path = "deps.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(SAMPLE)
    graph = DependencyGraph.from_file(path)
    print("=== Проект без цикла ===")
    report(graph)
    img = graph.visualize("graph")
    print("Файл визуализации:", img)
    if img.endswith(".svg"):
        import webbrowser, os
        webbrowser.open("file:///" + os.path.abspath(img).replace("\\", "/"))  

    print("\n=== Добавим D зависит от A (цикл) ===")
    graph.add_dependency("D", "A")
    report(graph)
