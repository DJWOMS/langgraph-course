"""Пример 6 урока 2: каналы, в которые превращается схема состояния.

Схема из четырёх ключей собрана в граф, и у собранного графа печатается тип
канала для каждого ключа. Дальше два узла цепочки пишут в ключ с редьюсером
и в ключ с Topic. В ключ messages не пишет никто, он показывает начальное
значение канала с редьюсером.
"""

import operator
from typing import Annotated

from langchain.messages import AnyMessage
from langgraph.channels import Topic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class State(TypedDict):
    root: str
    findings: Annotated[list[str], operator.add]
    messages: Annotated[list[AnyMessage], add_messages]
    events: Annotated[list[str], Topic(str, accumulate=True)]


def first(state: State) -> dict:
    """Пишет по одной записи в ключ с редьюсером и в ключ с Topic."""
    return {"findings": ["первая находка"], "events": ["узел first"]}


def second(state: State) -> dict:
    """То же самое из второго узла цепочки."""
    return {"findings": ["вторая находка"], "events": ["узел second"]}


builder = StateGraph(State)
builder.add_node("first", first)
builder.add_node("second", second)
builder.add_edge(START, "first")
builder.add_edge("first", "second")
builder.add_edge("second", END)

graph = builder.compile()

print("ТИПЫ КАНАЛОВ:")
for key in ("root", "findings", "messages", "events"):
    channel = graph.channels[key]
    print(f"   {key}: {type(channel).__name__}")

print()
result = graph.invoke({"root": "mini_repo"})
print("НА ВЫХОДЕ:")
for key in ("root", "findings", "messages", "events"):
    print(f"   {key}: {result.get(key)}")

# Вывод:
# ТИПЫ КАНАЛОВ:
#    root: LastValue
#    findings: BinaryOperatorAggregate
#    messages: BinaryOperatorAggregate
#    events: Topic
#
# НА ВЫХОДЕ:
#    root: mini_repo
#    findings: ['первая находка', 'вторая находка']
#    messages: []
#    events: ['узел first', 'узел second']
