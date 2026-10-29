"""Пример 2 урока 5: падение процесса и продолжение по файлу SQLite.

Обход стенда пишет checkpoints в файл walk.sqlite. Первый день идёт отдельным
процессом: на файле db.py узел scan_file обрывает процесс вызовом os._exit,
как при отключении питания. Второй день, это новый процесс с новым соединением и
новым графом: он читает из файла, что успело сохраниться, и продолжает обход
вызовом invoke(None, CONFIG). Если thread в файле пуст, обход начинается заново
с входа. Так повторяется для трёх режимов durability.
"""

import operator
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

HERE = Path(__file__).parent
REPO = HERE / "mini_repo"
DB_PATH = HERE / "walk.sqlite"
CONFIG = {"configurable": {"thread_id": "walk-1"}}
START_STATE = {"root": str(REPO), "queue": [], "current": "", "findings": []}

# Признак первого дня: процесс запущен с режимом durability в аргументе.
DAY_ONE = len(sys.argv) > 1


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
    """Считает строки. В первый день на db.py процесс обрывается."""
    if DAY_ONE and state["current"] == "db.py":
        print("     сбой процесса на db.py", flush=True)
        os._exit(1)
    print("     разбор", state["current"], flush=True)
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Пустое имя означает, что очередь закончилась."""
    if not state["current"]:
        return END
    return "scan_file"


def build(checkpointer: SqliteSaver):
    """Собирает обход с переданным чекпойнтером."""
    builder = StateGraph(WalkState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("pick_file", pick_file)
    builder.add_node("scan_file", scan_file)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "pick_file")
    builder.add_conditional_edges("pick_file", route_next)
    builder.add_edge("scan_file", "pick_file")
    return builder.compile(checkpointer=checkpointer)


def remove_db() -> None:
    """Удаляет файл базы вместе со служебными файлами SQLite."""
    for suffix in ("", "-wal", "-shm"):
        Path(f"{DB_PATH}{suffix}").unlink(missing_ok=True)


def day_one(durability: str) -> None:
    """Первый день: обход до сбоя на db.py."""
    with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        build(checkpointer).invoke(START_STATE, CONFIG, durability=durability)


def day_two() -> None:
    """Второй день: новый процесс читает файл и продолжает обход."""
    with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        graph = build(checkpointer)
        saved = graph.get_state(CONFIG)
        history = len(list(graph.get_state_history(CONFIG)))
        print("   в файле checkpoints:", history)
        print("   находки в файле:", saved.values.get("findings"))
        if saved.metadata is None:
            print("   в thread пусто, обход заново:")
            result = graph.invoke(START_STATE, CONFIG)
        else:
            print("   продолжение invoke(None, CONFIG):")
            result = graph.invoke(None, CONFIG)
        print("   итог, находок:", len(result["findings"]))


if DAY_ONE:
    day_one(sys.argv[1])
else:
    for number, mode in enumerate(("sync", "async", "exit"), start=1):
        remove_db()
        print(f"{number}. durability={mode}", flush=True)
        print("   первый день:", flush=True)
        subprocess.run([sys.executable, __file__, mode])
        print("   второй день:")
        day_two()
    remove_db()
