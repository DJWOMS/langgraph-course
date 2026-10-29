"""Пример 2 урока 6: что нужно возобновлению и как пауза ждёт ответа.

Граф из примера 1. Без чекпойнтера запуск останавливается, но возобновить
его нельзя. С SqliteSaver пауза лежит в файле: первый день заканчивается на
паузе и закрывает соединение. Второй день открывает файл новым соединением и
собирает граф заново. Вызов invoke(None, CONFIG) вместо ответа снова
останавливается на той же паузе, ответ даёт вызов с Command(resume=...).
Повтор от checkpoint с паузой ставит паузу заново, и новый ответ возобновляет
уже повтор.
"""

import subprocess
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

HERE = Path(__file__).parent
REPO = HERE / "mini_repo"
DB_PATH = HERE / "pause.sqlite"
CONFIG = {"configurable": {"thread_id": "run-1"}}
START_STATE = {"root": str(REPO), "files": [], "chosen": "", "output": ""}
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


def build(checkpointer=None):
    """Собирает граф примера 1 с переданным чекпойнтером или без него."""
    builder = StateGraph(RunState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("choose_file", choose_file)
    builder.add_node("run_file", run_file)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "choose_file")
    builder.add_edge("choose_file", "run_file")
    builder.add_edge("run_file", END)
    return builder.compile(checkpointer=checkpointer)


def remove_db() -> None:
    """Удаляет файл базы вместе со служебными файлами SQLite."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)


# 1. Без чекпойнтера пауза случается, а возобновить запуск нечем.
plain = build()
result = plain.invoke(START_STATE)
print("1. без чекпойнтера, пауза в результате:", "__interrupt__" in result)
try:
    plain.invoke(Command(resume="app.py"))
except RuntimeError as error:
    print("   возобновление:", error)

# 2. Первый день: пауза записана в файл, соединение закрыто.
remove_db()
with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
    result = build(checkpointer).invoke(START_STATE, CONFIG)
    print("2. первый день, пауза:", result["__interrupt__"][0].value["вопрос"])

# 3. Второй день: новое соединение, граф собран заново.
with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
    graph = build(checkpointer)
    snapshot = graph.get_state(CONFIG)
    print("3. второй день, next:", snapshot.next)
    print("   пауза из файла:", snapshot.interrupts[0].value["вопрос"])

    # 4. invoke(None, CONFIG) не отвечает на паузу, узел снова встаёт на неё.
    CALLS.clear()
    result = graph.invoke(None, CONFIG)
    print("4. invoke(None): выполнены узлы", CALLS, "пауза:", "__interrupt__" in result)

    # 5. Ответ человека.
    CALLS.clear()
    result = graph.invoke(Command(resume="app.py"), CONFIG)
    print("5. Command(resume='app.py'): выполнены узлы", CALLS)
    print("   выполнение файла:", result["output"])

    # 6. Второй ответ законченному запуску узлов не выполняет.
    CALLS.clear()
    result = graph.invoke(Command(resume="utils.py"), CONFIG)
    print("6. повторный ответ: выполнены узлы", CALLS, "выбран", result["chosen"])

    # 7. Повтор от checkpoint с паузой (урок 5): прежний ответ не используется.
    paused = next(
        item
        for item in graph.get_state_history(CONFIG)
        if any(task.interrupts for task in item.tasks)
    )
    CALLS.clear()
    result = graph.invoke(None, paused.config)
    print("7. повтор: выполнены узлы", CALLS, "пауза:", "__interrupt__" in result)
    result = graph.invoke(Command(resume="utils.py"), CONFIG)
    print("   новый ответ: выбран", result["chosen"], "|", result["output"])
remove_db()
