"""Пример 2 урока 8: какие ошибки выполнения файла стоит повторять.

Пункт 1 печатает ответ default_retry_on для ошибок разных типов. Дальше
узел run_file выполняет файл из папки bad_repo отдельным процессом. Параметр
check=True превращает ненулевой код возврата в CalledProcessError, timeout
останавливает процесс и бросает TimeoutExpired. broken.py падает при каждом
выполнении, hang.py зависает. RUNS считает выполнения файла.
"""

import subprocess
import sys
from pathlib import Path

import requests
from langgraph.errors import NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, default_retry_on
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "bad_repo"
RUNS: list[str] = []
NOT_FOUND = requests.Response()
NOT_FOUND.status_code = 404


class RunState(TypedDict):
    root: str
    current: str
    output: str


def run_file(state: RunState) -> dict:
    """Выполняет файл стенда, ошибка выполнения выходит из узла исключением."""
    RUNS.append(state["current"])
    subprocess.run(
        [sys.executable, state["current"]],
        cwd=state["root"],
        capture_output=True,
        check=True,
        timeout=1.5,
    )
    return {"output": "код 0"}


def is_transient(error: Exception) -> bool:
    """Повторять только зависание: ошибка в коде файла повторится и в следующий раз."""
    return isinstance(error, subprocess.TimeoutExpired)


def build(retry_policy: RetryPolicy):
    """Граф из одного узла run_file."""
    builder = StateGraph(RunState)
    builder.add_node("run_file", run_file, retry_policy=retry_policy)
    builder.add_edge(START, "run_file")
    builder.add_edge("run_file", END)
    return builder.compile()


# 1. Решение default_retry_on по типу ошибки.
print("1. default_retry_on:")
for error in (
    ValueError(),
    KeyError(),
    OSError(),
    TimeoutError(),
    ConnectionError(),
    requests.ConnectionError(),
    requests.HTTPError(response=NOT_FOUND),
    subprocess.CalledProcessError(1, "broken.py"),
    subprocess.TimeoutExpired("hang.py", 1.5),
    NodeTimeoutError("run_file", 1.5, kind="run", run_timeout=1.5),
):
    name = f"{type(error).__module__.split('.')[0]}.{type(error).__name__}"
    if getattr(error, "response", None) is not None:
        name += f" {error.response.status_code}"
    print(f"   {name.removeprefix('builtins.'):<30} {default_retry_on(error)}")

BUILDS = [
    ("retry_on по умолчанию", "broken.py", RetryPolicy(initial_interval=0.1, jitter=False)),
    (
        "retry_on=is_transient",
        "broken.py",
        RetryPolicy(initial_interval=0.1, jitter=False, retry_on=is_transient),
    ),
    (
        "retry_on=is_transient, max_attempts=2",
        "hang.py",
        RetryPolicy(max_attempts=2, initial_interval=0.1, jitter=False, retry_on=is_transient),
    ),
]

for number, (title, name, policy) in enumerate(BUILDS, start=2):
    RUNS.clear()
    try:
        build(policy).invoke({"root": str(REPO), "current": name, "output": ""})
    except Exception as exc:
        print(f"{number}. {title}, {name}: выполнений {len(RUNS)}, ошибка {type(exc).__name__}")
