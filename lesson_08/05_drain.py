"""Пример 5 урока 8: остановка запуска по запросу и продолжение после неё.

Обход стенда mini_repo с чекпойнтером InMemorySaver. Узел run_file выполняет
файл отдельным процессом. Перед выполнением config.py узел сам вызывает
control.request_drain("sigterm"), поэтому остановка каждый раз приходится на
один и тот же файл. В рабочем приложении request_drain вызывает обработчик сигнала.
RUNS отмечает выполнения файлов.
"""

import operator
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphDrained
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import RunControl
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CONFIG = {"configurable": {"thread_id": "walk-1"}}
RUNS: list[str] = []
control = RunControl()


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


def route_next(state: WalkState) -> Literal["run_file", "__end__"]:
    """Пустое имя означает, что очередь закончилась."""
    if not state["current"]:
        return END
    return "run_file"


def run_file(state: WalkState) -> dict:
    """Выполняет файл стенда. Перед выполнением config.py запрашивает остановку."""
    RUNS.append(state["current"])
    if state["current"] == "config.py":
        control.request_drain("sigterm")
    done = subprocess.run(
        [sys.executable, state["current"]],
        cwd=state["root"],
        capture_output=True,
        timeout=1.5,
    )
    return {"findings": [f"{state['current']}: код {done.returncode}"]}


builder = StateGraph(WalkState)
builder.add_node("collect_files", collect_files)
builder.add_node("pick_file", pick_file)
builder.add_node("run_file", run_file)
builder.add_edge(START, "collect_files")
builder.add_edge("collect_files", "pick_file")
builder.add_conditional_edges("pick_file", route_next)
builder.add_edge("run_file", "pick_file")
graph = builder.compile(checkpointer=InMemorySaver())

START_STATE = {"root": str(REPO), "queue": [], "current": "", "findings": []}

# 1. Запуск с RunControl: остановка на границе шага после config.py.
try:
    graph.invoke(START_STATE, CONFIG, control=control)
except GraphDrained as error:
    print("1. GraphDrained, reason:", error.reason, "| выполнения:", RUNS)

# 2. Что сохранил чекпойнтер.
snapshot = graph.get_state(CONFIG)
print("2. next:", snapshot.next, "| находки:", snapshot.values["findings"])

# 3. Отработавший RunControl остаётся в состоянии остановки.
print("3. control.drain_requested:", control.drain_requested)

# 4. Продолжение тем же thread_id, без control.
RUNS.clear()
result = graph.invoke(None, CONFIG)
print("4. продолжение, выполнения:", RUNS)
print("   находки:", result["findings"])
