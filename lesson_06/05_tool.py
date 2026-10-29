"""Пример 5 урока 6: пауза внутри инструмента.

Инструмент run_file сам ставит паузу вызовом interrupt() и только после
ответа "да" выполняет файл. Узел run_tools выполняет заранее заданный
список вызовов инструментов по порядку. Два вызова в одном узле дают две
паузы подряд в одной задаче. Список EXECUTED показывает, сколько раз файл
выполнялся на самом деле.
"""

import subprocess
import sys
from pathlib import Path

from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CONFIG = {"configurable": {"thread_id": "tools-1"}}
EXECUTED: list[str] = []


@tool
def run_file(name: str) -> str:
    """Выполняет файл стенда отдельным процессом после ответа "да" на паузе."""
    answer = interrupt({"инструмент": "run_file", "файл": name})
    if answer != "да":
        return f"{name}: отказ"
    EXECUTED.append(name)
    done = subprocess.run(
        [sys.executable, name],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return f"{name}: код {done.returncode}"


TOOLS = {"run_file": run_file}


class ToolState(TypedDict):
    tool_calls: list[dict]
    results: list[str]


def run_tools(state: ToolState) -> dict:
    """Выполняет вызовы инструментов по порядку."""
    results = [TOOLS[call["name"]].invoke(call["args"]) for call in state["tool_calls"]]
    return {"results": results}


builder = StateGraph(ToolState)
builder.add_node("run_tools", run_tools)
builder.add_edge(START, "run_tools")
builder.add_edge("run_tools", END)
graph = builder.compile(checkpointer=InMemorySaver())

TOOL_CALLS = [
    {"name": "run_file", "args": {"name": "app.py"}},
    {"name": "run_file", "args": {"name": "db.py"}},
]

# 1. Первый вызов инструмента останавливает узел.
result = graph.invoke({"tool_calls": TOOL_CALLS, "results": []}, CONFIG)
first = result["__interrupt__"][0]
print("1. пауза:", first.value, "| выполнены файлы:", EXECUTED)

# 2. Ответ на первую паузу: app.py выполняется, второй вызов встаёт на паузу.
result = graph.invoke(Command(resume="да"), CONFIG)
second = result["__interrupt__"][0]
print("2. пауза:", second.value, "| выполнены файлы:", EXECUTED)
print("   id пауз совпадают:", first.id == second.id)

# 3. Ответ на вторую паузу: узел снова выполняется с начала.
result = graph.invoke(Command(resume="нет"), CONFIG)
print("3. результаты:", result["results"])
print("   выполнены файлы:", EXECUTED)
