"""Пример 3 урока 5: правки задач упавшего шага (pending writes).

Fan-out из урока 3: Send запускает по копии узла scan_file на каждый файл
стенда, все копии выполняются одним шагом. Копия для db.py падает с OSError.
Остальные три копии успевают закончить работу, и их правки чекпойнтер хранит
отдельно от checkpoint. После починки вызов invoke(None, CONFIG) выполняет
заново только упавшую копию.
"""

import operator
from pathlib import Path
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CONFIG = {"configurable": {"thread_id": "scan-1"}}
CALLS: list[str] = []
BROKEN = {"db.py"}


class ScanState(TypedDict):
    root: str
    files: list[str]
    findings: Annotated[list[str], operator.add]
    card: str


class FileState(TypedDict):
    """Состояние одной копии узла scan_file: свой файл и корень стенда."""

    root: str
    name: str


def collect_files(state: ScanState) -> dict:
    """Собирает имена файлов стенда."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def scan_file(state: FileState) -> dict:
    """Разбирает один файл. Файл из BROKEN читается с ошибкой."""
    CALLS.append(state["name"])
    if state["name"] in BROKEN:
        raise OSError(f"не удалось прочитать {state['name']}")
    path = Path(state["root"]) / state["name"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['name']}: строк {lines}"]}


def make_card(state: ScanState) -> dict:
    """Сводит находки в одну карточку."""
    return {"card": f"разобрано файлов {len(state['findings'])}"}


def fan_out(state: ScanState) -> list[Send]:
    """По одному Send на файл: имя узла и состояние для этой копии."""
    return [
        Send("scan_file", {"root": state["root"], "name": name})
        for name in state["files"]
    ]


builder = StateGraph(ScanState)
builder.add_node("collect_files", collect_files)
builder.add_node("scan_file", scan_file, input_schema=FileState)
builder.add_node("make_card", make_card)
builder.add_edge(START, "collect_files")
builder.add_conditional_edges("collect_files", fan_out, ["scan_file"])
builder.add_edge("scan_file", "make_card")
builder.add_edge("make_card", END)
graph = builder.compile(checkpointer=InMemorySaver())

# 1. Одна копия из четырёх падает, invoke бросает её исключение.
try:
    graph.invoke({"root": str(REPO)}, CONFIG)
except OSError as error:
    print("1. запуск упал:", error)
print("   выполнены копии:", sorted(CALLS))

# 2. Что сохранил чекпойнтер: задачи шага, их результат и ошибка.
snapshot = graph.get_state(CONFIG)
print("2. next:", snapshot.next)
print("   находки:", snapshot.values["findings"])
for task in snapshot.tasks:
    outcome = repr(task.error) if task.error else task.result
    print("   задача", task.name, "->", outcome)
pinned = graph.get_state(snapshot.config)
print("   находки в самом checkpoint:", pinned.values["findings"])

# 3. Файл починили, запуск продолжается тем же thread.
CALLS.clear()
BROKEN.clear()
result = graph.invoke(None, CONFIG)
print("3. после продолжения выполнены копии:", CALLS)
print("   карточка:", result["card"])
