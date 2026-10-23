"""Пример 2 урока 4: предел числа шагов и GraphRecursionError.

Тот же обход стенда, что в примере 1, запускается с разными значениями
recursion_limit. Рядом стоит второй граф, у которого условие выхода забыли:
он повторяет цикл, пока предел не остановит его ошибкой. Счётчик вызовов узла
разбора показывает, сколько раз узел успел выполниться до остановки.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
SCANS: list[str] = []


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
    """Считает строки в выбранном файле и отмечается в счётчике вызовов."""
    SCANS.append(state["current"])
    if not state["current"]:
        return {"findings": ["разбирать нечего"]}
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Условие выхода на месте: пустое имя заканчивает обход."""
    if not state["current"]:
        return END
    return "scan_file"


def route_forgotten(state: WalkState) -> Literal["scan_file"]:
    """Условие выхода забыто: маршрут всегда ведёт обратно в разбор."""
    return "scan_file"


def build(router) -> StateGraph:
    """Собирает один и тот же цикл с разной функцией маршрутизации."""
    builder = StateGraph(WalkState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("pick_file", pick_file)
    builder.add_node("scan_file", scan_file)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "pick_file")
    builder.add_conditional_edges("pick_file", router)
    builder.add_edge("scan_file", "pick_file")
    return builder.compile()


def start() -> dict:
    """Входное состояние обхода."""
    return {"root": str(REPO), "queue": [], "current": "", "findings": []}


graph = build(route_next)
broken = build(route_forgotten)

# 1. Обход четырёх файлов занимает десять шагов, и предела 10 ему не хватает.
for limit in (10, 11):
    SCANS.clear()
    try:
        result = graph.invoke(start(), {"recursion_limit": limit})
        print(f"1. предел {limit}: находок {len(result['findings'])}")
    except GraphRecursionError as error:
        print(f"1. предел {limit}: {type(error).__name__}")
        print("   разборов до остановки:", len(SCANS))
        print("   текст ошибки:", str(error).splitlines()[0])

# 2. Цикл без выхода: работа закончилась, а граф идёт дальше.
SCANS.clear()
try:
    broken.invoke(start(), {"recursion_limit": 12})
except GraphRecursionError as error:
    print("2. цикл без выхода:", type(error).__name__)
    print("   разборов до остановки:", len(SCANS))
    print("   что разбирал:", SCANS)

# 3. Предел повышен, но цикл без выхода упирается в него снова.
SCANS.clear()
try:
    broken.invoke(start(), {"recursion_limit": 30})
except GraphRecursionError:
    print("3. предел 30, разборов до остановки:", len(SCANS))

# Вывод:
# 1. предел 10: GraphRecursionError
#    разборов до остановки: 4
#    текст ошибки: Recursion limit of 10 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key.
# 1. предел 11: находок 4
# 2. цикл без выхода: GraphRecursionError
#    разборов до остановки: 5
#    что разбирал: ['app.py', 'config.py', 'db.py', 'utils.py', '']
# 3. предел 30, разборов до остановки: 14
