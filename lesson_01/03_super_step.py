"""Пример 3 урока 1: один шаг графа против двух.

Четыре узла и две схемы связи. В последовательной схеме счёт строк и разбор
импортов стоят друг за другом, в параллельной, рядом. В режиме values поток
отдаёт снимок состояния на входе и после каждого шага, поэтому снимков на один
больше, чем шагов.
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class RepoState(TypedDict):
    root: str
    files: list[str]
    total_lines: int
    imports: list[str]
    card: str


def collect_files(state: RepoState) -> dict:
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def count_lines(state: RepoState) -> dict:
    root = Path(state["root"])
    total = 0
    for name in state["files"]:
        total += len((root / name).read_text(encoding="utf-8").splitlines())
    return {"total_lines": total}


def collect_imports(state: RepoState) -> dict:
    root = Path(state["root"])
    found = set()
    for name in state["files"]:
        for line in (root / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("from ") or line.startswith("import "):
                found.add(line.split()[1])
    return {"imports": sorted(found)}


def make_card(state: RepoState) -> dict:
    card = (
        f"файлов {len(state['files'])}, "
        f"строк {state['total_lines']}, "
        f"импортов {len(state['imports'])}"
    )
    return {"card": card}


def sequential() -> StateGraph:
    """Четыре узла цепочкой: каждый ждёт предыдущего."""
    builder = StateGraph(RepoState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("count_lines", count_lines)
    builder.add_node("collect_imports", collect_imports)
    builder.add_node("make_card", make_card)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "count_lines")
    builder.add_edge("count_lines", "collect_imports")
    builder.add_edge("collect_imports", "make_card")
    builder.add_edge("make_card", END)
    return builder


def parallel() -> StateGraph:
    """Те же узлы, но счёт строк и разбор импортов стоят рядом."""
    builder = StateGraph(RepoState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("count_lines", count_lines)
    builder.add_node("collect_imports", collect_imports)
    builder.add_node("make_card", make_card)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "count_lines")
    builder.add_edge("collect_files", "collect_imports")
    builder.add_edge("count_lines", "make_card")
    builder.add_edge("collect_imports", "make_card")
    builder.add_edge("make_card", END)
    return builder


def run(title: str, builder: StateGraph) -> None:
    graph = builder.compile()
    print(title)
    number = 0
    for chunk in graph.stream({"root": str(REPO)}, stream_mode="values", version="v2"):
        number += 1
        filled = sorted(key for key in chunk["data"] if key != "root")
        print(f"  снимок {number}: заполнены {filled}")
    print(f"  снимков всего: {number}")


run("ПОСЛЕДОВАТЕЛЬНАЯ СХЕМА", sequential())
print()
run("ПАРАЛЛЕЛЬНАЯ СХЕМА", parallel())

# Вывод:
# ПОСЛЕДОВАТЕЛЬНАЯ СХЕМА
#   снимок 1: заполнены []
#   снимок 2: заполнены ['files']
#   снимок 3: заполнены ['files', 'total_lines']
#   снимок 4: заполнены ['files', 'imports', 'total_lines']
#   снимок 5: заполнены ['card', 'files', 'imports', 'total_lines']
#   снимков всего: 5
#
# ПАРАЛЛЕЛЬНАЯ СХЕМА
#   снимок 1: заполнены []
#   снимок 2: заполнены ['files']
#   снимок 3: заполнены ['files', 'imports', 'total_lines']
#   снимок 4: заполнены ['card', 'files', 'imports', 'total_lines']
#   снимков всего: 4
