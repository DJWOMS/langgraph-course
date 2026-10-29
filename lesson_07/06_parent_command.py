"""Пример 6 урока 7: переход из подграфа в узел родителя, Command.PARENT.

Слой проверки check_layer собирает файлы стенда узлом collect_files. Узел
check_files ищет файлы из RISKY и возвращает Command с graph=Command.PARENT:
при опасном файле переход в узел ask_human родителя, иначе в make_report.
Сборки родителя: без ребра из узла check и с ребром check -> make_report.
Ещё два пункта: вызов слоя без родителя падает, аннотация с узлом родителя не
проходит компиляцию подграфа.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.errors import ParentCommand
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
CALLS: list[str] = []
RISKY = {"db.py"}


class CheckState(TypedDict):
    root: str
    files: list[str]
    findings: Annotated[list[str], operator.add]


def collect_files(state: CheckState) -> dict:
    """Собирает имена файлов стенда и пишет их число в находки."""
    CALLS.append("collect_files")
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names, "findings": [f"файлов: {len(names)}"]}


def check_files(state: CheckState) -> Command:
    """Выбирает узел родителя: ask_human при опасном файле, иначе make_report."""
    CALLS.append("check_files")
    risky = [name for name in state["files"] if name in RISKY]
    if risky:
        return Command(
            update={"findings": [f"{name}: нужен человек" for name in risky]},
            goto="ask_human",
            graph=Command.PARENT,
        )
    return Command(
        update={"findings": ["опасных файлов нет"]},
        goto="make_report",
        graph=Command.PARENT,
    )


check_builder = StateGraph(CheckState)
check_builder.add_node("collect_files", collect_files)
check_builder.add_node("check_files", check_files)
check_builder.add_edge(START, "collect_files")
check_builder.add_edge("collect_files", "check_files")
check_layer = check_builder.compile()


class RepoState(TypedDict):
    root: str
    findings: Annotated[list[str], operator.add]


def ask_human(state: RepoState) -> dict:
    """В полном агенте здесь стоит пауза из урока 6."""
    CALLS.append("ask_human")
    return {}


def make_report(state: RepoState) -> dict:
    """Узел отчёта."""
    CALLS.append("make_report")
    return {}


def build(edge_after_check: bool):
    """Родитель со слоем check. Ребро из check добавляется по флагу."""
    builder = StateGraph(RepoState)
    builder.add_node("check", check_layer)
    builder.add_node("ask_human", ask_human)
    builder.add_node("make_report", make_report)
    builder.add_edge(START, "check")
    if edge_after_check:
        builder.add_edge("check", "make_report")
    builder.add_edge("ask_human", "make_report")
    builder.add_edge("make_report", END)
    return builder.compile()


START_STATE = {"root": str(REPO), "findings": []}

# 1. Опасный файл есть: переход в ask_human.
CALLS.clear()
result = build(edge_after_check=False).invoke(START_STATE)
print("1. выполнены:", CALLS)
print("   находки:", result["findings"])

# 2. Опасных файлов нет: переход прямо в make_report.
RISKY.clear()
CALLS.clear()
result = build(edge_after_check=False).invoke(START_STATE)
print("2. выполнены:", CALLS)
print("   находки:", result["findings"])

# 3. У узла check есть ребро в make_report, и оно тоже срабатывает.
RISKY.add("db.py")
CALLS.clear()
build(edge_after_check=True).invoke(START_STATE)
print("3. с ребром check -> make_report выполнены:", CALLS)

# 4. Слой с Command.PARENT сам по себе.
try:
    check_layer.invoke(START_STATE)
except ParentCommand as error:
    print("4. отдельный вызов слоя:", type(error).__name__)


# 5. Аннотация возврата с узлом родителя.
def check_annotated(state: CheckState) -> Command[Literal["ask_human"]]:
    """Тот же переход с аннотацией возврата."""
    return check_files(state)


annotated = StateGraph(CheckState)
annotated.add_node("check_files", check_annotated)
annotated.add_edge(START, "check_files")
try:
    annotated.compile()
except ValueError as error:
    print("5. компиляция подграфа:", error)
