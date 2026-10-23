"""Пример 2 урока 2: редьюсер сводит значение ключа с правкой узла.

Два узла над стендом mini_repo пишут находки в один ключ состояния. Граф
собран трижды: без редьюсера, с редьюсером на цепочке узлов и с редьюсером на
параллельной паре. Редьюсер печатает свои аргументы. В конце показана
ошибка StateGraph на редьюсер неверной формы.
"""

from pathlib import Path
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


def append_findings(left: list[str], right: list[str]) -> list[str]:
    """Складывает накопленное значение ключа (left) с правкой узла (right)."""
    print(f"   редьюсер: left={left}, right={right}")
    return left + right


class PlainState(TypedDict):
    root: str
    findings: list[str]


class ReducedState(TypedDict):
    root: str
    findings: Annotated[list[str], append_findings]


def count_lines(state) -> dict:
    """Считает строки во всех файлах стенда."""
    root = Path(state["root"])
    total = sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in sorted(root.glob("*.py"))
    )
    return {"findings": [f"строк {total}"]}


def count_imports(state) -> dict:
    """Считает строки импорта во всех файлах стенда."""
    root = Path(state["root"])
    total = 0
    for path in sorted(root.glob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("import ") or line.startswith("from "):
                total += 1
    return {"findings": [f"импортов {total}"]}


def chain(schema) -> object:
    """Два узла цепочкой: count_lines, затем count_imports."""
    builder = StateGraph(schema)
    builder.add_node("count_lines", count_lines)
    builder.add_node("count_imports", count_imports)
    builder.add_edge(START, "count_lines")
    builder.add_edge("count_lines", "count_imports")
    builder.add_edge("count_imports", END)
    return builder.compile()


def pair(schema) -> object:
    """Те же два узла параллельно: обе правки приходят в одном шаге."""
    builder = StateGraph(schema)
    builder.add_node("count_lines", count_lines)
    builder.add_node("count_imports", count_imports)
    builder.add_edge(START, "count_lines")
    builder.add_edge(START, "count_imports")
    builder.add_edge("count_lines", END)
    builder.add_edge("count_imports", END)
    return builder.compile()


# 1. Цепочка без редьюсера: вторая правка затирает первую.
print("1. цепочка, ключ без редьюсера")
result = chain(PlainState).invoke({"root": str(REPO), "findings": []})
print("   итог:", result["findings"])

# 2. Та же цепочка с редьюсером: правки копятся.
print("2. цепочка, ключ с редьюсером")
result = chain(ReducedState).invoke({"root": str(REPO)})
print("   итог:", result["findings"])

# 3. Параллельная пара с редьюсером: обе правки в одном шаге.
print("3. параллельная пара, ключ с редьюсером")
result = pair(ReducedState).invoke({"root": str(REPO)})
print("   итог:", result["findings"])


# 4. Редьюсер неверной формы: один аргумент вместо двух.
def only_one(right: list[str]) -> list[str]:
    return right


class BrokenState(TypedDict):
    findings: Annotated[list[str], only_one]


try:
    StateGraph(BrokenState)
except ValueError as error:
    print("4. редьюсер с одним аргументом:", error)

# Вывод:
# 1. цепочка, ключ без редьюсера
#    итог: ['импортов 3']
# 2. цепочка, ключ с редьюсером
#    редьюсер: left=[], right=['строк 44']
#    редьюсер: left=['строк 44'], right=['импортов 3']
#    итог: ['строк 44', 'импортов 3']
# 3. параллельная пара, ключ с редьюсером
#    редьюсер: left=[], right=['импортов 3']
#    редьюсер: left=['импортов 3'], right=['строк 44']
#    итог: ['импортов 3', 'строк 44']
# 4. редьюсер с одним аргументом: Invalid reducer signature. Expected (a, b) -> c. Got (right: list[str]) -> list[str]
#
# В пункте 3 правки шага применены по алфавиту имён узлов,
# поэтому count_imports идёт раньше count_lines.
