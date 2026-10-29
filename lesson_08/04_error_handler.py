"""Пример 4 урока 8: обработчик ошибки узла и set_node_defaults.

Обход из уроков 4 и 5, в котором scan_file заменён узлом run_file из
урока 6, выполняет файлы папки bad_repo: collect_files, pick_file, run_file
и функция маршрутизации route_next. Обработчик skip_file стоит у
run_file: записывает сбой в находки и возвращает Command с переходом в
pick_file. Обработчик mark_failed задан всем узлам методом set_node_defaults:
записывает сбой в status и перехода не задаёт. RUNS считает выполнения
файлов, CALLS отмечает выполнение pick_file.
"""

import operator
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Literal

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "bad_repo"
RUNS: list[str] = []
CALLS: list[str] = []


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]
    status: str


def collect_files(state: WalkState) -> dict:
    """Складывает имена файлов в очередь. Нет папки, значит FileNotFoundError."""
    names = sorted(path.name for path in Path(state["root"]).iterdir() if path.suffix == ".py")
    return {"queue": names, "current": ""}


def pick_file(state: WalkState) -> dict:
    """Берёт следующее имя из очереди и убирает его оттуда."""
    CALLS.append("pick_file")
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
    return Command(
        update={"findings": [f"{state['current']}: {type(error.error).__name__}"]},
        goto="pick_file",
    )


def mark_failed(state: WalkState, error: NodeError) -> dict:
    """Обработчик по умолчанию: запись о сбое в status, без перехода."""
    return {"status": f"сбой в {error.node}: {type(error.error).__name__}"}


RETRY = RetryPolicy(
    max_attempts=2,
    initial_interval=0.1,
    jitter=False,
    retry_on=subprocess.TimeoutExpired,
)


def build(with_handlers: bool):
    """Обход с обработчиками или без них. Политика повторных попыток одна."""
    builder = StateGraph(WalkState)
    if with_handlers:
        builder.set_node_defaults(error_handler=mark_failed)
    builder.add_node("collect_files", collect_files)
    builder.add_node("pick_file", pick_file)
    builder.add_node(
        "run_file",
        run_file,
        retry_policy=RETRY,
        error_handler=skip_file if with_handlers else None,
    )
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "pick_file")
    builder.add_conditional_edges("pick_file", route_next)
    builder.add_edge("run_file", "pick_file")
    return builder.compile()


def start_state(root: Path) -> dict:
    return {"root": str(root), "queue": [], "current": "", "findings": [], "status": ""}


# 1. Без обработчиков: первая ошибка заканчивает запуск.
RUNS.clear()
try:
    build(with_handlers=False).invoke(start_state(REPO))
except Exception as exc:
    print("1. без обработчиков: запуск упал,", type(exc).__name__, "| выполнения:", RUNS)

# 2. С обработчиками: сбой файла становится находкой, обход идёт дальше.
RUNS.clear()
result = build(with_handlers=True).invoke(start_state(REPO))
print("2. с обработчиками, выполнения:", RUNS)
for line in result["findings"]:
    print("   ", line)
print("   status:", repr(result["status"]))

# 3. Папки нет: collect_files падает, срабатывает обработчик по умолчанию.
CALLS.clear()
result = build(with_handlers=True).invoke(start_state(REPO / "missing"))
print("3. папки нет, status:", result["status"])
print("   pick_file выполнялся:", bool(CALLS), "| находок:", len(result["findings"]))
