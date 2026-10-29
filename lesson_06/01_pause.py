"""Пример 1 урока 6: пауза внутри узла и возобновление.

Узел choose_file останавливает запуск вызовом interrupt() и отдаёт наружу
список файлов стенда. Человек отвечает именем файла, ответ приходит вызовом
с Command(resume=...). При возобновлении узел choose_file выполняется с первой
строки, interrupt() возвращает ответ, и узел run_file выполняет выбранный файл
отдельным процессом.
"""

import subprocess
import sys
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CONFIG = {"configurable": {"thread_id": "run-1"}}
CALLS: list[str] = []


class RunState(TypedDict):
    root: str
    files: list[str]
    chosen: str
    output: str


def collect_files(state: RunState) -> dict:
    """Собирает имена файлов стенда."""
    CALLS.append("collect_files")
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def choose_file(state: RunState) -> dict:
    """Ставит запуск на паузу с вопросом, какой файл выполнить."""
    CALLS.append("choose_file")
    chosen = interrupt({"вопрос": "Какой файл выполнить?", "файлы": state["files"]})
    return {"chosen": chosen}


def run_file(state: RunState) -> dict:
    """Выполняет выбранный файл стенда отдельным процессом."""
    CALLS.append("run_file")
    done = subprocess.run(
        [sys.executable, state["chosen"]],
        cwd=state["root"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {"output": f"код {done.returncode}, вывод: {done.stdout.strip() or '-'}"}


builder = StateGraph(RunState)
builder.add_node("collect_files", collect_files)
builder.add_node("choose_file", choose_file)
builder.add_node("run_file", run_file)
builder.add_edge(START, "collect_files")
builder.add_edge("collect_files", "choose_file")
builder.add_edge("choose_file", "run_file")
builder.add_edge("run_file", END)
graph = builder.compile(checkpointer=InMemorySaver())

START_STATE = {"root": str(REPO), "files": [], "chosen": "", "output": ""}

# 1. Первый вызов останавливается на interrupt() в узле choose_file.
result = graph.invoke(START_STATE, CONFIG)
pause = result["__interrupt__"][0]
print("1. ключи результата:", sorted(result))
print("   значение паузы:", pause.value)
print("   выполнены узлы:", CALLS)

# 2. Что сохранил чекпойнтер на паузе.
snapshot = graph.get_state(CONFIG)
print("2. next:", snapshot.next)
print("   задача на паузе:", snapshot.tasks[0].name)
print("   то же значение в get_state:", snapshot.interrupts[0].value == pause.value)

# 3. Ответ человека: возобновление тем же thread_id.
CALLS.clear()
result = graph.invoke(Command(resume="app.py"), CONFIG)
print("3. выполнены узлы:", CALLS)
print("   выбран:", result["chosen"])
print("   выполнение файла:", result["output"])
print("   пауза в результате:", "__interrupt__" in result)
