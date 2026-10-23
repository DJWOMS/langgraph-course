"""Пример 1 урока 2: три способа задать схему состояния.

Граф из одного узла над стендом mini_repo собран трижды: на TypedDict, на
dataclass со значением по умолчанию и на модели Pydantic с проверкой входа.
Печатается, чем три схемы отличаются при запуске.
"""

from dataclasses import dataclass, field
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class DictState(TypedDict):
    root: str
    suffix: str
    files: list[str]


def collect_dict(state: DictState) -> dict:
    """Собирает имена файлов и приписывает к ним пометку из состояния."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": [name + state["suffix"] for name in names]}


@dataclass
class DataState:
    root: str
    suffix: str = " [py]"
    files: list[str] = field(default_factory=list)


def collect_data(state: DataState) -> dict:
    """То же самое, но состояние приходит объектом dataclass."""
    names = sorted(path.name for path in Path(state.root).glob("*.py"))
    return {"files": [name + state.suffix for name in names]}


class ModelState(BaseModel):
    root: str
    suffix: str = " [py]"
    files: list[str] = []


def collect_model(state: ModelState) -> dict:
    """То же самое, но состояние приходит моделью Pydantic."""
    names = sorted(path.name for path in Path(state.root).glob("*.py"))
    return {"files": [name + state.suffix for name in names]}


def build(schema, node) -> object:
    """Собирает граф из одного узла на переданной схеме состояния."""
    builder = StateGraph(schema)
    builder.add_node("collect", node)
    builder.add_edge(START, "collect")
    builder.add_edge("collect", END)
    return builder.compile()


# 1. TypedDict: ключа suffix на входе нет, значения по умолчанию тоже нет.
try:
    build(DictState, collect_dict).invoke({"root": str(REPO)})
except KeyError as error:
    print("1. TypedDict без suffix:", type(error).__name__, error)

# 2. TypedDict: ключ передан явно.
result = build(DictState, collect_dict).invoke({"root": str(REPO), "suffix": " [py]"})
print("2. TypedDict с suffix:", result["files"][:2])

# 3. dataclass: тот же вход без suffix, значение берётся из схемы.
result = build(DataState, collect_data).invoke({"root": str(REPO)})
print("3. dataclass без suffix:", result["files"][:2])
print("   тип результата:", type(result).__name__)

# 4. Pydantic: неверный тип на входе.
try:
    build(ModelState, collect_model).invoke({"root": 42})
except ValidationError as error:
    print("4. Pydantic, неверный тип:", str(error).splitlines()[0])

# 5. Pydantic: верный вход и тип результата.
result = build(ModelState, collect_model).invoke({"root": str(REPO)})
print("5. Pydantic, верный вход:", result["files"][:2])
print("   тип результата:", type(result).__name__)

# Вывод:
# 1. TypedDict без suffix: KeyError 'suffix'
# 2. TypedDict с suffix: ['app.py [py]', 'config.py [py]']
# 3. dataclass без suffix: ['app.py [py]', 'config.py [py]']
#    тип результата: dict
# 4. Pydantic, неверный тип: 1 validation error for ModelState
# 5. Pydantic, верный вход: ['app.py [py]', 'config.py [py]']
#    тип результата: dict
