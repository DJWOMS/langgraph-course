"""Пример 1 урока 3: условное ребро и функция маршрутизации.

Граф обходит стенд mini_repo и после сбора файлов выбирает, каким разбором идти
дальше: быстрым или подробным. Выбор делает функция маршрутизации. Варианты в
примере: имя узла прямо из функции, словарь соответствия, условная точка
входа и маршрут сразу в два узла.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class ScanState(TypedDict):
    root: str
    limit: int
    files: list[str]
    report: Annotated[list[str], operator.add]


def collect_files(state: ScanState) -> dict:
    """Собирает имена файлов стенда."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def quick_scan(state: ScanState) -> dict:
    """Короткий разбор: только число файлов."""
    return {"report": [f"быстрый разбор: файлов {len(state['files'])}"]}


def deep_scan(state: ScanState) -> dict:
    """Подробный разбор: считает строки в каждом файле."""
    root = Path(state["root"])
    total = sum(
        len((root / name).read_text(encoding="utf-8").splitlines())
        for name in state["files"]
    )
    return {"report": [f"подробный разбор: строк {total}"]}


def route_by_size(state: ScanState) -> Literal["quick_scan", "deep_scan"]:
    """Файлов больше предела, значит хватит быстрого разбора."""
    if len(state["files"]) > state["limit"]:
        return "quick_scan"
    return "deep_scan"


def is_big(state: ScanState) -> bool:
    """Та же проверка, но возвращает признак."""
    return len(state["files"]) > state["limit"]


def route_both(state: ScanState) -> list[str]:
    """Маршрут сразу в два узла: оба пойдут одним шагом."""
    return ["quick_scan", "deep_scan"]


def build(route, path_map=None) -> object:
    """Собирает граф, где после сбора файлов стоит условное ребро."""
    builder = StateGraph(ScanState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("quick_scan", quick_scan)
    builder.add_node("deep_scan", deep_scan)
    builder.add_edge(START, "collect_files")
    builder.add_conditional_edges("collect_files", route, path_map)
    builder.add_edge("quick_scan", END)
    builder.add_edge("deep_scan", END)
    return builder.compile()


# 1. Функция маршрутизации вернула имя узла.
graph = build(route_by_size)
print("1. предел 2:", graph.invoke({"root": str(REPO), "limit": 2})["report"])
print("   предел 10:", graph.invoke({"root": str(REPO), "limit": 10})["report"])

# 2. Функция вернула признак, имя узла нашлось в словаре соответствия.
mapped = build(is_big, {True: "quick_scan", False: "deep_scan"})
print("2. предел 2, словарь соответствия:", mapped.invoke({"root": str(REPO), "limit": 2})["report"])


# 3. Условная точка входа: развилка стоит сразу после START.
def choose_start(state: ScanState) -> Literal["collect_files", "quick_scan"]:
    """Список файлов пришёл на входе, значит собирать его заново незачем."""
    if state.get("files"):
        return "quick_scan"
    return "collect_files"


entry = StateGraph(ScanState)
entry.add_node("collect_files", collect_files)
entry.add_node("quick_scan", quick_scan)
entry.add_node("deep_scan", deep_scan)
entry.add_conditional_edges(START, choose_start)
entry.add_conditional_edges("collect_files", route_by_size)
entry.add_edge("quick_scan", END)
entry.add_edge("deep_scan", END)
entry_graph = entry.compile()

print("3. вход без списка:", entry_graph.invoke({"root": str(REPO), "limit": 10})["report"])
print(
    "   вход со списком:",
    entry_graph.invoke({"root": str(REPO), "limit": 2, "files": ["app.py"]})["report"],
)

# 4. Маршрут в два узла сразу: обе правки приходят в одном шаге.
both = build(route_both, ["quick_scan", "deep_scan"])
print("4. маршрут в два узла:", both.invoke({"root": str(REPO), "limit": 2})["report"])

# Вывод:
# 1. предел 2: ['быстрый разбор: файлов 4']
#    предел 10: ['подробный разбор: строк 44']
# 2. предел 2, словарь соответствия: ['быстрый разбор: файлов 4']
# 3. вход без списка: ['подробный разбор: строк 44']
#    вход со списком: ['быстрый разбор: файлов 1']
# 4. маршрут в два узла: ['подробный разбор: строк 44', 'быстрый разбор: файлов 4']
