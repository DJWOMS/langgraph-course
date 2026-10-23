"""Пример 5 урока 4: кеш узла и его ключ.

Узел разбора помечен CachePolicy, граф скомпилирован с InMemoryCache. Первый
вариант узла принимает узкую схему входа (корень и текущий файл), второй читает
всё состояние целиком. Три запуска подряд показывают, когда кеш срабатывает, а
когда ключ расходится и узел выполняется заново.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.cache.memory import InMemoryCache
from langgraph.graph import END, START, StateGraph
from langgraph.types import CachePolicy
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CALLS: list[str] = []


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]


class ScanIn(TypedDict):
    root: str
    current: str


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


def scan_narrow(state: ScanIn) -> dict:
    """Считает строки. Из состояния получает только корень и текущий файл."""
    CALLS.append(state["current"])
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def scan_wide(state: WalkState) -> dict:
    """Тот же разбор, но на входе всё состояние, включая накопленные находки."""
    CALLS.append(state["current"])
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Выход по пустой очереди."""
    if not state["current"]:
        return END
    return "scan_file"


def build(scanner) -> StateGraph:
    """Собирает обход с кешируемым узлом разбора и своим кешем в памяти."""
    builder = StateGraph(WalkState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("pick_file", pick_file)
    builder.add_node("scan_file", scanner, cache_policy=CachePolicy(ttl=60))
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "pick_file")
    builder.add_conditional_edges("pick_file", route_next)
    builder.add_edge("scan_file", "pick_file")
    return builder.compile(cache=InMemoryCache())


def run(graph, note: str) -> None:
    """Запускает обход и считает, сколько разборов пришло из кеша."""
    CALLS.clear()
    cached = 0
    start = {"root": str(REPO), "queue": [], "current": "", "findings": []}
    if note:
        start["findings"] = [note]
    for event in graph.stream(start, stream_mode="updates"):
        if event.get("__metadata__", {}).get("cached"):
            cached += 1
    print(f"   из кеша {cached}, выполнений тела узла {len(CALLS)}")


PASSES = (
    ("первый запуск", ""),
    ("тот же вход", ""),
    ("лишняя строка на входе", "начато вручную"),
)

narrow = build(scan_narrow)
wide = build(scan_wide)

print("1. узкая схема входа:")
for label, note in PASSES:
    print(f"   {label}:")
    run(narrow, note)

print("2. на входе всё состояние:")
for label, note in PASSES:
    print(f"   {label}:")
    run(wide, note)

# 3. Пометка о кеше приходит только в режиме updates.
print("3. где видна пометка:")
clean = {"root": str(REPO), "queue": [], "current": "", "findings": []}
events = list(narrow.stream(clean, stream_mode="updates"))
print("   updates, третье событие:", events[2])
print("   invoke, ключи итога:", sorted(narrow.invoke(clean)))

# Вывод:
# 1. узкая схема входа:
#    первый запуск:
#    из кеша 0, выполнений тела узла 4
#    тот же вход:
#    из кеша 4, выполнений тела узла 0
#    лишняя строка на входе:
#    из кеша 4, выполнений тела узла 0
# 2. на входе всё состояние:
#    первый запуск:
#    из кеша 0, выполнений тела узла 4
#    тот же вход:
#    из кеша 4, выполнений тела узла 0
#    лишняя строка на входе:
#    из кеша 0, выполнений тела узла 4
# 3. где видна пометка:
#    updates, третье событие: {'scan_file': {'findings': ['app.py: строк 13']}, '__metadata__': {'cached': True}}
#    invoke, ключи итога: ['current', 'findings', 'queue', 'root']
