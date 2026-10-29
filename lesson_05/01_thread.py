"""Пример 1 урока 5: чекпойнтер, thread и история checkpoints.

Обход стенда из урока 4 скомпилирован с InMemorySaver. Вызов без thread_id
падает. Вызов с thread_id оставляет в чекпойнтере историю: checkpoint на
каждом шаге. Второй вызов с тем же thread_id продолжает сохранённое состояние,
вызов с другим thread_id начинает с пустого.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.checkpoint.memory import InMemorySaver
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

START_STATE = {"root": str(REPO), "queue": [], "current": "", "findings": []}
WALK_1 = {"configurable": {"thread_id": "walk-1"}}
WALK_2 = {"configurable": {"thread_id": "walk-2"}}

# 1. С чекпойнтером вызов без thread_id не проходит.
try:
    graph.invoke(START_STATE)
except ValueError as error:
    print("1. без thread_id:", error)

# 2. Обход в thread walk-1 и последний checkpoint этого thread.
result = graph.invoke(START_STATE, WALK_1)
snapshot = graph.get_state(WALK_1)
print("2. находок:", len(result["findings"]))
print("   последний checkpoint: шаг", snapshot.metadata["step"], "next", snapshot.next)

# 3. Вся история thread, сверху самый свежий checkpoint.
print("3. история walk-1:")
print("   шаг  источник  next              current     находок")
for item in graph.get_state_history(WALK_1):
    following = ", ".join(item.next) or "-"
    current = item.values.get("current") or "-"
    print(
        f"   {item.metadata['step']:>3}  {item.metadata['source']:<8}  "
        f"{following:<16}  {current:<10}  {len(item.values.get('findings', []))}"
    )

# 4. Тот же вход в тот же thread и в новый thread.
again = graph.invoke(START_STATE, WALK_1)
fresh = graph.invoke(START_STATE, WALK_2)
print("4. повтор в walk-1, находок:", len(again["findings"]))
print("   первый вызов в walk-2, находок:", len(fresh["findings"]))
print("   checkpoints в walk-1:", len(list(graph.get_state_history(WALK_1))))
