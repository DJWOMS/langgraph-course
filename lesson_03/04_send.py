"""Пример 4 урока 3: Send и раскладка работы по числу файлов.

Сколько файлов в репозитории, известно только при запуске, поэтому рёбер под
них при сборке нет. Узел разбора запускается по разу на файл объектами Send,
каждая копия получает своё состояние, а находки собираются редьюсером. Дальше
fan-out на ноль элементов и тот же fan-out, собранный на Command.
"""

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class ScanState(TypedDict):
    root: str
    files: list[str]
    findings: Annotated[list[str], operator.add]
    card: str


class FileState(TypedDict):
    """Состояние одной копии узла разбора: свой файл и корень стенда."""

    root: str
    name: str


def collect_files(state: ScanState) -> dict:
    """Собирает имена файлов стенда."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def scan_file(state: FileState) -> dict:
    """Разбирает один файл. Состояние здесь своё, отдельное от общего."""
    path = Path(state["root"]) / state["name"]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    return {"findings": [f"{state['name']}: строк {lines}"]}


def make_card(state: ScanState) -> dict:
    """Сводит находки в одну карточку."""
    return {"card": f"разобрано файлов {len(state['findings'])}"}


def fan_out(state: ScanState) -> list[Send]:
    """По одному Send на файл: имя узла и состояние для этой копии."""
    return [
        Send("scan_file", {"root": state["root"], "name": name})
        for name in state["files"]
    ]


builder = StateGraph(ScanState)
builder.add_node("collect_files", collect_files)
builder.add_node("scan_file", scan_file, input_schema=FileState)
builder.add_node("make_card", make_card)
builder.add_edge(START, "collect_files")
builder.add_conditional_edges("collect_files", fan_out, ["scan_file"])
builder.add_edge("scan_file", "make_card")
builder.add_edge("make_card", END)
graph = builder.compile()

# 1. Четыре файла стенда, значит четыре копии узла разбора.
result = graph.invoke({"root": str(REPO)})
print("1. находок:", len(result["findings"]))
for finding in sorted(result["findings"]):
    print("   ", finding)
print("   карточка:", result["card"])

# 2. Схема графа: fan-out рисуется одной пунктирной стрелкой.
print()
print(graph.get_graph().draw_mermaid())

# 3. Пустой fan-out: папки docs в стенде нет, список файлов пустой.
empty = graph.invoke({"root": str(REPO / "docs")})
print("3. пустой fan-out, ключи итога:", sorted(empty))


# 4. Тот же fan-out, но собранный на Command вместо условного ребра.
def collect_and_fan(state: ScanState) -> Command[Literal["scan_file"]]:
    """Собирает файлы и тут же раскладывает их по копиям узла разбора."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    sends = [Send("scan_file", {"root": state["root"], "name": n}) for n in names]
    return Command(update={"files": names}, goto=sends)


by_command = StateGraph(ScanState)
by_command.add_node("collect_files", collect_and_fan)
by_command.add_node("scan_file", scan_file, input_schema=FileState)
by_command.add_node("make_card", make_card)
by_command.add_edge(START, "collect_files")
by_command.add_edge("scan_file", "make_card")
by_command.add_edge("make_card", END)
print("4. fan-out на Command:", by_command.compile().invoke({"root": str(REPO)})["card"])

# Вывод:
# 1. находок: 4
#     app.py: строк 13
#     config.py: строк 6
#     db.py: строк 15
#     utils.py: строк 10
#    карточка: разобрано файлов 4
#
# ---
# config:
#   flowchart:
#     curve: linear
# ---
# graph TD;
# 	__start__([<p>__start__</p>]):::first
# 	collect_files(collect_files)
# 	scan_file(scan_file)
# 	make_card(make_card)
# 	__end__([<p>__end__</p>]):::last
# 	__start__ --> collect_files;
# 	collect_files -.-> scan_file;
# 	scan_file --> make_card;
# 	make_card --> __end__;
# 	classDef default fill:#f2f0ff,line-height:1.2
# 	... (ещё две строки classDef)
#
# 3. пустой fan-out, ключи итога: ['files', 'findings', 'root']
# 4. fan-out на Command: разобрано файлов 4
