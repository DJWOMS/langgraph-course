"""Пример 4 урока 1: два режима потока и схема графа.

Тот же параллельный граф, что в примере 3, запущен потоком сразу в двух режимах.
Режим updates отдаёт правку и имя узла, режим values отдаёт состояние целиком.
Дальше пример печатает схему графа на языке mermaid и сохраняет её картинкой.
Картинку рисует внешний сервис, поэтому вызов обёрнут в try.
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
PICTURE = Path(__file__).parent / "graph.png"


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

graph = builder.compile()

for chunk in graph.stream(
    {"root": str(REPO)},
    stream_mode=["updates", "values"],
    version="v2",
):
    if chunk["type"] == "updates":
        for node, update in chunk["data"].items():
            print(f"updates: узел {node} прислал ключи {sorted(update)}")
    elif chunk["type"] == "values":
        print(f"values:  состояние целиком, ключей {len(chunk['data'])}")

print()
print(graph.get_graph().draw_mermaid())

try:
    graph.get_graph().draw_mermaid_png(output_file_path=str(PICTURE))
    print("картинка сохранена:", PICTURE.name)
except Exception as error:
    print("картинку получить не вышло:", type(error).__name__, error)

# Вывод:
# values:  состояние целиком, ключей 1
# updates: узел collect_files прислал ключи ['files']
# values:  состояние целиком, ключей 2
# updates: узел collect_imports прислал ключи ['imports']
# updates: узел count_lines прислал ключи ['total_lines']
# values:  состояние целиком, ключей 4
# updates: узел make_card прислал ключи ['card']
# values:  состояние целиком, ключей 5
#
# ---
# config:
#   flowchart:
#     curve: linear
# ---
# graph TD;
# 	__start__([<p>__start__</p>]):::first
# 	collect_files(collect_files)
# 	count_lines(count_lines)
# 	collect_imports(collect_imports)
# 	make_card(make_card)
# 	__end__([<p>__end__</p>]):::last
# 	__start__ --> collect_files;
# 	collect_files --> collect_imports;
# 	collect_files --> count_lines;
# 	collect_imports --> make_card;
# 	count_lines --> make_card;
# 	make_card --> __end__;
# 	classDef default fill:#f2f0ff,line-height:1.2
# 	... (подрезано: ещё две строки classDef)
#
# картинка сохранена: graph.png
