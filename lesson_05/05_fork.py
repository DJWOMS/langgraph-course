"""Пример 5 урока 5: правка состояния и развилка (fork).

Обход стенда проходит целиком. От checkpoint перед разбором db.py делаются две
правки методом update_state: одна от имени узла scan_file, другая без
as_node. Редьюсер сводит правку со значением ключа, update_state записывает
её новым checkpoint, а старый не меняется. От правки с as_node="scan_file"
обход продолжается без разбора db.py.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CONFIG = {"configurable": {"thread_id": "walk-1"}}
CALLS: list[str] = []
SKIPPED = {"findings": ["db.py: пропущен вручную"]}


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
    CALLS.append(state["current"])
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Пустое имя означает, что очередь закончилась."""
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
graph = builder.compile(checkpointer=InMemorySaver())

graph.invoke({"root": str(REPO), "queue": [], "current": "", "findings": []}, CONFIG)
before_db = next(
    item
    for item in graph.get_state_history(CONFIG)
    if item.next == ("scan_file",) and item.values["current"] == "db.py"
)

# 1. Правка от имени scan_file: граф считает, что разбор db.py уже был.
as_scan = graph.update_state(before_db.config, SKIPPED, as_node="scan_file")
state = graph.get_state(as_scan)
print("1. as_node='scan_file': next", state.next, "источник", state.metadata["source"])
print("   находки:", state.values["findings"])

# 2. Та же правка без as_node: узел выводится из истории, это pick_file.
inferred = graph.update_state(before_db.config, SKIPPED)
state = graph.get_state(inferred)
print("2. без as_node: next", state.next)

# 3. Правка не трогает checkpoint, от которого сделана.
print("3. находки в исходной точке:", graph.get_state(before_db.config).values["findings"])

# 4. Развилка: продолжение от правки с as_node="scan_file".
CALLS.clear()
result = graph.invoke(None, as_scan)
print("4. разборы после развилки:", CALLS)
for line in result["findings"]:
    print("   ", line)
