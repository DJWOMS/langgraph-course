"""Пример 1 урока 4: цикл из ребра назад и условного выхода на END.

Граф обходит стенд mini_repo по одному файлу за проход. Узел pick_file берёт
следующее имя из очереди, узел scan_file считает в нём строки, ребро от
scan_file ведёт назад к pick_file. Выход на END стоит в функции маршрутизации
после pick_file, то есть проверяется до разбора.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]


def collect_files(state: WalkState) -> dict:
    """Складывает имена файлов стенда в очередь обхода."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"queue": names, "current": ""}


def pick_file(state: WalkState) -> dict:
    """Берёт следующее имя из очереди и убирает его оттуда."""
    queue = list(state["queue"])
    if not queue:
        return {"current": ""}
    return {"current": queue.pop(0), "queue": queue}


def scan_file(state: WalkState) -> dict:
    """Считает строки в выбранном файле."""
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Условие выхода: пустое имя означает, что очередь закончилась."""
    if not state["current"]:
        return END
    return "scan_file"


builder = StateGraph(WalkState)
builder.add_node("collect_files", collect_files)
builder.add_node("pick_file", pick_file)
builder.add_node("scan_file", scan_file)
builder.add_edge(START, "collect_files")
builder.add_edge("collect_files", "pick_file")
builder.add_conditional_edges("pick_file", route_next)
builder.add_edge("scan_file", "pick_file")
graph = builder.compile()

# 1. Каждый шаг запуска отдельной строкой.
print("1. обход по шагам:")
for event in graph.stream(
    {"root": str(REPO), "queue": [], "current": "", "findings": []},
    stream_mode="updates",
):
    print("  ", event)

# 2. Итог обхода.
result = graph.invoke(
    {"root": str(REPO), "queue": [], "current": "", "findings": []}
)
print("2. находок:", len(result["findings"]))
for line in result["findings"]:
    print("   ", line)

# 3. Ребро назад на схеме графа.
print("3. схема графа:")
print(graph.get_graph().draw_mermaid())

# Вывод:
# 1. обход по шагам:
#    {'collect_files': {'queue': ['app.py', 'config.py', 'db.py', 'utils.py'], 'current': ''}}
#    {'pick_file': {'current': 'app.py', 'queue': ['config.py', 'db.py', 'utils.py']}}
#    {'scan_file': {'findings': ['app.py: строк 13']}}
#    {'pick_file': {'current': 'config.py', 'queue': ['db.py', 'utils.py']}}
#    {'scan_file': {'findings': ['config.py: строк 6']}}
#    {'pick_file': {'current': 'db.py', 'queue': ['utils.py']}}
#    {'scan_file': {'findings': ['db.py: строк 15']}}
#    {'pick_file': {'current': 'utils.py', 'queue': []}}
#    {'scan_file': {'findings': ['utils.py: строк 10']}}
#    {'pick_file': {'current': ''}}
# 2. находок: 4
#     app.py: строк 13
#     config.py: строк 6
#     db.py: строк 15
#     utils.py: строк 10
# 3. схема графа:
# ---
# config:
#   flowchart:
#     curve: linear
# ---
# graph TD;
# 	__start__([<p>__start__</p>]):::first
# 	collect_files(collect_files)
# 	pick_file(pick_file)
# 	scan_file(scan_file)
# 	__end__([<p>__end__</p>]):::last
# 	__start__ --> collect_files;
# 	collect_files --> pick_file;
# 	pick_file -.-> __end__;
# 	pick_file -.-> scan_file;
# 	scan_file --> pick_file;
# 	classDef default fill:#f2f0ff,line-height:1.2
# 	... (ещё две строки classDef)
