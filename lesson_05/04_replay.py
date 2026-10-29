"""Пример 4 урока 5: повтор запуска от прошлого checkpoint (replay).

Обход стенда проходит целиком. По истории находится checkpoint перед разбором
db.py, и граф вызывается с его config. Узлы до этой точки не выполняются, узлы
после неё выполняются заново. Старые checkpoints остаются в истории, новые
идут от выбранной точки отдельной цепочкой.
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


def checkpoint_id(config: dict) -> str:
    """Достаёт checkpoint_id из config снимка."""
    return config["configurable"]["checkpoint_id"]


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
history = list(graph.get_state_history(CONFIG))
print("1. первый запуск: разборов", len(CALLS), "checkpoints", len(history))

# 2. Поиск точки: следующим идёт разбор, текущий файл db.py.
before_db = next(
    item
    for item in history
    if item.next == ("scan_file",) and item.values["current"] == "db.py"
)
print("2. точка повтора: шаг", before_db.metadata["step"], "next", before_db.next)
print("   находки в точке:", before_db.values["findings"])

# 3. Повтор от этой точки: вход None, config выбранного checkpoint.
CALLS.clear()
result = graph.invoke(None, before_db.config)
print("3. повтор выполнил разборы:", CALLS)
print("   находок в итоге:", len(result["findings"]))

# 4. Новые записи истории идут от точки повтора.
fresh = list(graph.get_state_history(CONFIG))
print("4. checkpoints в thread:", len(fresh), "из них новых:", len(fresh) - len(history))
for item in fresh[: len(fresh) - len(history)]:
    following = ", ".join(item.next) or "-"
    print(f"   шаг {item.metadata['step']:>2}  {item.metadata['source']:<5}  next {following}")
fork = fresh[len(fresh) - len(history) - 1]
print(
    "   родитель записи fork, это точка повтора:",
    checkpoint_id(fork.parent_config) == checkpoint_id(before_db.config),
)

# 5. Старая точка не изменилась, повтор от последнего checkpoint не выполняет узлов.
print("5. находки в точке повтора:", graph.get_state(before_db.config).values["findings"])
CALLS.clear()
graph.invoke(None, history[0].config)
print("   повтор от конца первого запуска, разборов:", len(CALLS))
