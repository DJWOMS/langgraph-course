"""Пример 4 урока 2: обход редьюсера типом Overwrite.

Ключ errors копит сообщения об ошибках обхода стенда. Показаны три попытки
очистить его перед новым заходом: пустым списком, типом Overwrite и его же
записью словарём. В конце показаны две правки Overwrite в одном шаге.
"""

import operator
from typing import Annotated

from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite
from typing_extensions import TypedDict


class State(TypedDict):
    errors: Annotated[list[str], operator.add]


def record_error(state: State) -> dict:
    """Записывает находку в общий буфер ошибок."""
    return {"errors": ["в utils.py функции без докстрингов"]}


def clear_with_empty(state: State) -> dict:
    """Пробует очистить буфер пустым списком."""
    return {"errors": []}


def clear_with_overwrite(state: State) -> dict:
    """Очищает буфер в обход редьюсера."""
    return {"errors": Overwrite([])}


def clear_with_dict(state: State) -> dict:
    """То же самое записью словарём."""
    return {"errors": {"__overwrite__": []}}


def chain(second) -> object:
    """Собирает цепочку: запись ошибки, затем переданный узел очистки."""
    builder = StateGraph(State)
    builder.add_node("record_error", record_error)
    builder.add_node("clear", second)
    builder.add_edge(START, "record_error")
    builder.add_edge("record_error", "clear")
    builder.add_edge("clear", END)
    return builder.compile()


print("1. очистка пустым списком:", chain(clear_with_empty).invoke({"errors": []}))
print("2. очистка типом Overwrite:", chain(clear_with_overwrite).invoke({"errors": []}))
print("3. очистка словарём:", chain(clear_with_dict).invoke({"errors": []}))

# 4. Два узла одного шага пишут Overwrite в один ключ.
builder = StateGraph(State)
builder.add_node("clear_a", clear_with_overwrite)
builder.add_node("clear_b", clear_with_dict)
builder.add_edge(START, "clear_a")
builder.add_edge(START, "clear_b")
builder.add_edge("clear_a", END)
builder.add_edge("clear_b", END)

try:
    builder.compile().invoke({"errors": ["старая находка"]})
except InvalidUpdateError as error:
    print("4. два Overwrite в одном шаге:", str(error).splitlines()[0])

# Вывод:
# 1. очистка пустым списком: {'errors': ['в utils.py функции без докстрингов']}
# 2. очистка типом Overwrite: {'errors': []}
# 3. очистка словарём: {'errors': []}
# 4. два Overwrite в одном шаге: Can receive only one Overwrite value per super-step.
