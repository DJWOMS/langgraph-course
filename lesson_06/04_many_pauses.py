"""Пример 4 урока 6: несколько пауз в одном шаге.

Send запускает по копии узла ask_and_run на каждый файл стенда, все копии
выполняются одним шагом, и каждая останавливается на своей паузе. Одно
значение в Command(resume=...) на четыре паузы не подходит. Ответ даётся
словарём: id паузы и ответ на неё. Сначала человек отвечает на две паузы,
потом на оставшиеся.
"""

import operator
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CONFIG = {"configurable": {"thread_id": "many-1"}}
CALLS: list[str] = []


class RunState(TypedDict):
    root: str
    files: list[str]
    runs: Annotated[list[str], operator.add]


class FileState(TypedDict):
    """Состояние одной копии узла ask_and_run: свой файл и корень стенда."""

    root: str
    name: str


def collect_files(state: RunState) -> dict:
    """Собирает имена файлов стенда."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def fan_out(state: RunState) -> list[Send]:
    """По одному Send на файл."""
    return [Send("ask_and_run", {"root": state["root"], "name": name}) for name in state["files"]]


def ask_and_run(state: FileState) -> dict:
    """Ставит паузу с вопросом о своём файле и выполняет файл при ответе "да"."""
    CALLS.append(state["name"])
    answer = interrupt({"вопрос": "Выполнить файл?", "файл": state["name"]})
    if answer != "да":
        return {"runs": [f"{state['name']}: пропущен"]}
    done = subprocess.run(
        [sys.executable, state["name"]],
        cwd=state["root"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {"runs": [f"{state['name']}: код {done.returncode}"]}


builder = StateGraph(RunState)
builder.add_node("collect_files", collect_files)
builder.add_node("ask_and_run", ask_and_run, input_schema=FileState)
builder.add_edge(START, "collect_files")
builder.add_conditional_edges("collect_files", fan_out, ["ask_and_run"])
builder.add_edge("ask_and_run", END)
graph = builder.compile(checkpointer=InMemorySaver())

# 1. Четыре копии, четыре паузы.
result = graph.invoke({"root": str(REPO), "files": [], "runs": []}, CONFIG)
pauses = result["__interrupt__"]
print("1. пауз:", len(pauses), [pause.value["файл"] for pause in pauses])

# 2. Одно значение на несколько пауз не принимается.
try:
    graph.invoke(Command(resume="да"), CONFIG)
except RuntimeError as error:
    print("2.", str(error).split(".")[0])

# 3. Ответ на две паузы из четырёх: словарь id паузы -> ответ.
by_file = {pause.value["файл"]: pause.id for pause in pauses}
CALLS.clear()
result = graph.invoke(Command(resume={by_file["app.py"]: "да", by_file["config.py"]: "нет"}), CONFIG)
print("3. выполнены копии:", sorted(CALLS))
print("   готово:", result["runs"])
print("   пауз в результате:", len(result["__interrupt__"]))
print("   пауз в get_state:", len(graph.get_state(CONFIG).interrupts))

# 4. Ответ на оставшиеся паузы по id из последнего результата.
CALLS.clear()
rest = {pause.id: "нет" for pause in result["__interrupt__"]}
result = graph.invoke(Command(resume=rest), CONFIG)
print("4. выполнены копии:", sorted(CALLS))
print("   готово:", result["runs"])
