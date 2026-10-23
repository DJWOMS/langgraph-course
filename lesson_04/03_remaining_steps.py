"""Пример 3 урока 4: счётчик шага и RemainingSteps.

Тот же обход стенда. Узел разбора печатает номер текущего шага из
config["metadata"]["langgraph_step"] и остаток шагов из состояния. Второй граф
использует остаток как условие мягкого выхода: обход сворачивается сам и
возвращает то, что успел собрать, вместо GraphRecursionError.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.managed import RemainingSteps
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class WalkState(TypedDict):
    root: str
    queue: list[str]
    current: str
    findings: Annotated[list[str], operator.add]
    remaining_steps: RemainingSteps


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


def scan_file(state: WalkState, config: RunnableConfig) -> dict:
    """Считает строки и печатает номер шага и остаток шагов."""
    step = config["metadata"]["langgraph_step"]
    remaining = state["remaining_steps"]
    print(f"   шаг {step}, остаток {remaining}, сумма {step + remaining}")
    path = Path(state["root"]) / state["current"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['current']}: строк {lines}"]}


def route_next(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Выход только по пустой очереди."""
    if not state["current"]:
        return END
    return "scan_file"


def route_soft(state: WalkState) -> Literal["scan_file", "__end__"]:
    """Тот же выход плюс мягкая остановка за два шага до предела."""
    if state["remaining_steps"] <= 2:
        return END
    if not state["current"]:
        return END
    return "scan_file"


def build(router) -> StateGraph:
    """Собирает один и тот же цикл с разной функцией маршрутизации."""
    builder = StateGraph(WalkState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("pick_file", pick_file)
    builder.add_node("scan_file", scan_file)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "pick_file")
    builder.add_conditional_edges("pick_file", router)
    builder.add_edge("scan_file", "pick_file")
    return builder.compile()


def start() -> dict:
    """Входное состояние обхода."""
    return {"root": str(REPO), "queue": [], "current": "", "findings": []}


graph = build(route_next)
soft = build(route_soft)

# 1. Предел задан, и остаток считается от него.
print("1. предел 11:")
result = graph.invoke(start(), {"recursion_limit": 11})
print("   ключи итога:", sorted(result))

# 2. Предел не задан, работает значение по умолчанию.
print("2. без предела:")
graph.invoke(start())

# 3. Жёсткая остановка: работа не доделана, ошибка вместо результата.
print("3. предел 7, жёсткое условие:")
try:
    graph.invoke(start(), {"recursion_limit": 7})
except GraphRecursionError as error:
    print("   ", type(error).__name__)

# 4. Мягкая остановка на том же пределе: результат неполный, но он есть.
print("4. предел 7, мягкое условие:")
partial = soft.invoke(start(), {"recursion_limit": 7})
print("   находок:", len(partial["findings"]), "осталось в очереди:", partial["queue"])

# Вывод:
# 1. предел 11:
#    шаг 3, остаток 8, сумма 11
#    шаг 5, остаток 6, сумма 11
#    шаг 7, остаток 4, сумма 11
#    шаг 9, остаток 2, сумма 11
#    ключи итога: ['current', 'findings', 'queue', 'root']
# 2. без предела:
#    шаг 3, остаток 10004, сумма 10007
#    шаг 5, остаток 10002, сумма 10007
#    шаг 7, остаток 10000, сумма 10007
#    шаг 9, остаток 9998, сумма 10007
# 3. предел 7, жёсткое условие:
#    шаг 3, остаток 4, сумма 7
#    шаг 5, остаток 2, сумма 7
#    шаг 7, остаток 0, сумма 7
#     GraphRecursionError
# 4. предел 7, мягкое условие:
#    шаг 3, остаток 4, сумма 7
#    шаг 5, остаток 2, сумма 7
#    находок: 2 осталось в очереди: ['utils.py']
