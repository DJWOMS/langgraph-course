"""Пример 3 урока 7: пауза внутри подграфа и возобновление.

Слой выполнения run_layer, это подграф из узлов plan_run, review_run и
run_file. Узел review_run ставит паузу перед выполнением файла, как в уроке 6.
У подграфа нет своего чекпойнтера, у родителя InMemorySaver. Две сборки
родителя: подграф узлом run_layer и подграф внутри узла call_run_layer.
Список CALLS показывает, какие узлы выполнялись при каждом вызове.
"""

import subprocess
import sys
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CALLS: list[str] = []


class RunState(TypedDict):
    root: str
    chosen: str
    output: str


def plan_run(state: RunState) -> dict:
    """Предлагает файл для выполнения."""
    CALLS.append("plan_run")
    return {"chosen": "db.py"}


def review_run(state: RunState) -> dict:
    """Ставит паузу с предложением. Ответ "да" оставляет файл, другой ответ убирает."""
    CALLS.append("review_run")
    answer = interrupt({"файл": state["chosen"]})
    return {"chosen": state["chosen"] if answer == "да" else ""}


def run_file(state: RunState) -> dict:
    """Выполняет файл стенда отдельным процессом."""
    CALLS.append("run_file")
    if not state["chosen"]:
        return {"output": "не выполнен"}
    done = subprocess.run(
        [sys.executable, state["chosen"]],
        cwd=state["root"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {"output": f"код {done.returncode}"}


run_builder = StateGraph(RunState)
run_builder.add_node("plan_run", plan_run)
run_builder.add_node("review_run", review_run)
run_builder.add_node("run_file", run_file)
run_builder.add_edge(START, "plan_run")
run_builder.add_edge("plan_run", "review_run")
run_builder.add_edge("review_run", "run_file")
run_builder.add_edge("run_file", END)
run_layer = run_builder.compile()


def call_run_layer(state: RunState) -> dict:
    """Вызывает подграф внутри узла. Код до invoke выполняется заново при каждом возобновлении."""
    CALLS.append("call_run_layer")
    return run_layer.invoke(state)


def build(as_node: bool):
    """Родитель: подграф узлом run_layer или внутри узла call_run_layer."""
    builder = StateGraph(RunState)
    if as_node:
        builder.add_node("run_layer", run_layer)
        name = "run_layer"
    else:
        builder.add_node("call_run_layer", call_run_layer)
        name = "call_run_layer"
    builder.add_edge(START, name)
    builder.add_edge(name, END)
    return builder.compile(checkpointer=InMemorySaver())


START_STATE = {"root": str(REPO), "chosen": "", "output": ""}
CONFIG = {"configurable": {"thread_id": "run-1"}}

for number, as_node in enumerate((True, False), start=1):
    graph = build(as_node)
    print(f"{number}. подграф {'узлом' if as_node else 'внутри узла'}")

    CALLS.clear()
    result = graph.invoke(START_STATE, CONFIG)
    print("   пауза:", result["__interrupt__"][0].value, "| выполнены:", CALLS)

    parent = graph.get_state(CONFIG)
    print("   родитель: next", parent.next, "| state задачи:", type(parent.tasks[0].state).__name__)
    task = graph.get_state(CONFIG, subgraphs=True).tasks[0]
    inner = task.state
    namespace = inner.config["configurable"]["checkpoint_ns"]
    print("   подграф: next", inner.next, "| chosen", inner.values["chosen"])
    print("   пространство имён:", namespace.split(":")[0] + ":<id задачи>")

    CALLS.clear()
    result = graph.invoke(Command(resume="да"), CONFIG)
    print("   после ответа выполнены:", CALLS, "|", result["chosen"], result["output"])
    print("   задач в get_state после конца:", len(graph.get_state(CONFIG, subgraphs=True).tasks))
