"""Пример 6 урока 8: отладка графа без внешнего сервиса.

Обход папки bad_repo без узла collect_files: очередь из broken.py и ok.py
приходит во входе. У run_file RetryPolicy с max_attempts=2 и retry_on по
умолчанию, и обработчик skip_file из примера 4. Пункты: поток tasks,
события потоков debug и checkpoints, поиск упавшей задачи в истории,
вызов узла из graph.nodes и частичный запуск. RUNS считает выполнения
файлов, HANDLED считает вызовы обработчика.
"""

import operator
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "bad_repo"
RUNS: list[str] = []
HANDLED: list[str] = []


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]


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
    """Выполняет файл отдельным процессом, ошибка выходит из узла исключением."""
    RUNS.append(state["current"])
    subprocess.run(
        [sys.executable, state["current"]],
        cwd=state["root"],
        capture_output=True,
        check=True,
        timeout=1.5,
    )
    return {"findings": [f"{state['current']}: код 0"]}


def skip_file(state: WalkState, error: NodeError) -> Command:
    """Обработчик ошибки run_file: запись о сбое и переход к следующему файлу."""
    HANDLED.append(state["current"])
    return Command(
        update={"findings": [f"{state['current']}: {type(error.error).__name__}"]},
        goto="pick_file",
    )


def build(checkpointer):
    builder = StateGraph(WalkState)
    builder.add_node("pick_file", pick_file)
    builder.add_node(
        "run_file",
        run_file,
        retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.1, jitter=False),
        error_handler=skip_file,
    )
    builder.add_edge(START, "pick_file")
    builder.add_conditional_edges("pick_file", route_next)
    builder.add_edge("run_file", "pick_file")
    return builder.compile(checkpointer=checkpointer)


def start_state(queue: list[str]) -> dict:
    return {"root": str(REPO), "queue": queue, "current": "", "findings": []}


graph = build(InMemorySaver())
QUEUE = ["broken.py", "ok.py"]

# 1. Поток tasks: начало и конец каждой задачи.
print("1. поток tasks:")
for chunk in graph.stream(
    start_state(QUEUE),
    {"configurable": {"thread_id": "walk-1"}},
    stream_mode="tasks",
    version="v2",
):
    task = chunk["data"]
    if "result" not in task:
        print(f"   начало {task['name']}")
    else:
        error = type(task["error"]).__name__ if task["error"] else "-"
        print(f"   конец  {task['name']:<26} ошибка {error:<18} правка {task['result']}")
print("   выполнения файлов:", RUNS)

# 2. Сколько событий каждого типа отдают потоки debug и checkpoints.
print("2. события потоков:")
for title, checkpointer in (("с чекпойнтером", InMemorySaver()), ("без чекпойнтера", None)):
    for mode in ("debug", "checkpoints"):
        events = Counter(
            chunk["data"]["type"] if mode == "debug" else chunk["type"]
            for chunk in build(checkpointer).stream(
                start_state(QUEUE),
                {"configurable": {"thread_id": "walk-2"}},
                stream_mode=mode,
                version="v2",
            )
        )
        print(f"   {mode:<11} {title}: {dict(events)}")

# 3. Шаг с упавшей задачей в истории thread walk-1.
print("3. история walk-1, задачи с ошибкой:")
for snapshot in graph.get_state_history({"configurable": {"thread_id": "walk-1"}}):
    for task in snapshot.tasks:
        if task.error:
            print(f"   шаг {snapshot.metadata['step']}, {task.name}, current={snapshot.values['current']}")
            print(f"   ошибка: {task.error.split('(')[0]}")

# 4. Узел напрямую: без повторных попыток и без обработчика.
RUNS.clear()
HANDLED.clear()
try:
    graph.nodes["run_file"].invoke({**start_state([]), "current": "broken.py"})
except subprocess.CalledProcessError as error:
    print(
        "4. graph.nodes['run_file']:", type(error).__name__,
        "| выполнений:", len(RUNS), "| вызовов обработчика:", len(HANDLED),
    )

# 5. Частичный запуск: состояние как после pick_file, остановка после run_file.
RUNS.clear()
config = {"configurable": {"thread_id": "test-1"}}
graph.update_state(config, start_state(["broken.py"]) | {"current": "ok.py"}, as_node="pick_file")
result = graph.invoke(None, config, interrupt_after="run_file")
print("5. частичный запуск, выполнения:", RUNS, "| находки:", result["findings"])
print("   next:", graph.get_state(config).next)
