"""Пример 1 урока 8: повторные попытки узла и политика RetryPolicy.

Узел check_db проверяет, что база отвечает. Базы в примере нет: первые
попытки падают по счётчику failures. Так пример воспроизводит базу, которая
поднимается не сразу. Номер попытки узел берёт из
runtime.execution_info.node_attempt и пишет в ATTEMPTS. Сообщения LangGraph
о повторных попытках печатает обработчик журнала PrintRetries.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from typing_extensions import TypedDict

ATTEMPTS: list[int] = []


class PrintRetries(logging.Handler):
    """Печатает сообщение LangGraph о повторной попытке без трассировки."""

    def emit(self, record: logging.LogRecord) -> None:
        print("   журнал:", record.getMessage())


logging.getLogger("langgraph").addHandler(PrintRetries())
logging.getLogger("langgraph").setLevel(logging.INFO)


class DbState(TypedDict):
    status: str


def make_check_db(error: Exception, failures: int):
    """Узел check_db: первые failures попыток падают с ошибкой error."""

    def check_db(state: DbState, runtime: Runtime) -> dict:
        nonlocal failures
        ATTEMPTS.append(runtime.execution_info.node_attempt)
        if failures > 0:
            failures -= 1
            raise error
        return {"status": "база отвечает"}

    return check_db


def build(error: Exception, failures: int, retry_policy: RetryPolicy | None):
    """Граф из одного узла check_db с заданной политикой."""
    builder = StateGraph(DbState)
    builder.add_node("check_db", make_check_db(error, failures), retry_policy=retry_policy)
    builder.add_edge(START, "check_db")
    builder.add_edge("check_db", END)
    return builder.compile()


POLICY = RetryPolicy(initial_interval=0.1, jitter=False)
DOWN = ConnectionError("база не отвечает")

BUILDS = [
    ("без retry_policy, база отвечает с третьей попытки", DOWN, 2, None),
    ("RetryPolicy, база отвечает с третьей попытки", DOWN, 2, POLICY),
    ("RetryPolicy, база не отвечает три раза", DOWN, 3, POLICY),
    ("RetryPolicy, ValueError в первой попытке", ValueError("неверный адрес базы"), 1, POLICY),
]

for number, (title, error, failures, policy) in enumerate(BUILDS, start=1):
    ATTEMPTS.clear()
    print(f"{number}. {title}")
    try:
        result = build(error, failures, policy).invoke({"status": ""})
        print("   попытки:", ATTEMPTS, "|", result["status"])
    except Exception as exc:
        print("   попытки:", ATTEMPTS, "| запуск упал:", type(exc).__name__)
