"""Пример 3 урока 6: одобрить, исправить или отклонить выполнение файла.

Узел plan_run предлагает выполнить db.py. Узел review_run показывает
предложение человеку, LangGraph проверяет ответ по схеме Decision, и узел по
решению возвращает Command: approve ведёт в run_file как есть, edit меняет
файл и ведёт в run_file, reject записывает причину и ведёт в skip_run. Три
решения идут в трёх разных thread. В четвёртом thread первый ответ не
проходит проверку по схеме, и человек отвечает на ту же паузу ещё раз.
"""

import subprocess
import sys
from pathlib import Path
from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ValidationError
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class RunState(TypedDict):
    root: str
    chosen: str
    note: str
    output: str


class Decision(BaseModel):
    """Ответ человека: решение и поля, которые оно использует."""

    type: Literal["approve", "edit", "reject"]
    file: str | None = None
    reason: str = "без причины"


def plan_run(state: RunState) -> dict:
    """Предлагает файл для выполнения. В проекте это решение модели."""
    return {"chosen": "db.py"}


def review_run(state: RunState) -> Command[Literal["run_file", "skip_run"]]:
    """Ставит паузу с предложением и переходит по решению человека."""
    decision = interrupt(
        {"действие": "выполнение файла", "файл": state["chosen"]},
        response_schema=Decision,
    )
    if decision.type == "approve":
        return Command(goto="run_file")
    if decision.type == "edit":
        return Command(update={"chosen": decision.file}, goto="run_file")
    return Command(update={"note": decision.reason}, goto="skip_run")


def run_file(state: RunState) -> dict:
    """Выполняет файл стенда отдельным процессом."""
    done = subprocess.run(
        [sys.executable, state["chosen"]],
        cwd=state["root"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {"output": f"код {done.returncode}, вывод: {done.stdout.strip() or '-'}"}


def skip_run(state: RunState) -> dict:
    """Записывает отказ вместо выполнения файла."""
    return {"output": f"не выполнен: {state['note']}"}


builder = StateGraph(RunState)
builder.add_node("plan_run", plan_run)
builder.add_node("review_run", review_run)
builder.add_node("run_file", run_file)
builder.add_node("skip_run", skip_run)
builder.add_edge(START, "plan_run")
builder.add_edge("plan_run", "review_run")
builder.add_edge("run_file", END)
builder.add_edge("skip_run", END)
graph = builder.compile(checkpointer=InMemorySaver())

START_STATE = {"root": str(REPO), "chosen": "", "note": "", "output": ""}
DECISIONS = {
    "review-approve": {"type": "approve"},
    "review-edit": {"type": "edit", "file": "app.py"},
    "review-reject": {"type": "reject", "reason": "db.py ходит в базу"},
}

for number, (thread_id, decision) in enumerate(DECISIONS.items(), start=1):
    config = {"configurable": {"thread_id": thread_id}}
    paused = graph.invoke(START_STATE, config)
    result = graph.invoke(Command(resume=decision), config)
    print(f"{number}. {decision['type']}")
    print("   человеку показано:", paused["__interrupt__"][0].value)
    print("   файл:", result["chosen"], "|", result["output"])

# 4. Схема ответа приходит вместе с паузой, в поле response_schema.
schema = paused["__interrupt__"][0].response_schema
print("4. решения в схеме:", schema["properties"]["type"]["enum"])
print("   обязательные поля:", schema["required"])

# 5. Ответ не по схеме: ValidationError, пауза остаётся на месте.
config = {"configurable": {"thread_id": "review-invalid"}}
graph.invoke(START_STATE, config)
try:
    graph.invoke(Command(resume={"type": "approved"}), config)
except ValidationError as error:
    problem = error.errors()[0]
    print("5. ошибка в поле", problem["loc"], "|", problem["msg"])
snapshot = graph.get_state(config)
print("   next:", snapshot.next, "| пауз:", len(snapshot.interrupts))
try:
    graph.invoke(None, config)
except ValidationError as error:
    print("   invoke(None) после неверного ответа:", type(error).__name__)
result = graph.invoke(Command(resume={"type": "approve"}), config)
print("   исправленный ответ: файл", result["chosen"], "|", result["output"])
