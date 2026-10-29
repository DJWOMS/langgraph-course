"""Пример 4 урока 7: параметр checkpointer у подграфа, None, True и False.

Подграф review_layer записывает файл в список visited, которого нет у родителя,
и ставит паузу с вопросом о файле. Скрипт запускает родителя с InMemorySaver
два раза в одном thread: для app.py и для db.py. В каждом запуске подграф,
стоящий узлом layer, встаёт на паузу, и скрипт отвечает "да".
Для каждого значения checkpointer видно, отдаёт ли get_state снимок подграфа
на паузе, какие его узлы выполняются при возобновлении и что попадает в
summary во втором запуске.
"""

import operator
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

CALLS: list[str] = []


class ReviewState(TypedDict):
    file: str
    visited: Annotated[list[str], operator.add]
    summary: str


def note_file(state: ReviewState) -> dict:
    """Записывает файл в список visited."""
    CALLS.append("note_file")
    return {"visited": [state["file"]]}


def ask_human(state: ReviewState) -> dict:
    """Ставит паузу и после ответа перечисляет все файлы из visited."""
    CALLS.append("ask_human")
    interrupt({"файл": state["file"]})
    return {"summary": ", ".join(state["visited"])}


class ParentState(TypedDict):
    file: str
    summary: str


def build(mode):
    """Подграф с заданным checkpointer, узлом layer в родителе с InMemorySaver."""
    review_builder = StateGraph(ReviewState)
    review_builder.add_node("note_file", note_file)
    review_builder.add_node("ask_human", ask_human)
    review_builder.add_edge(START, "note_file")
    review_builder.add_edge("note_file", "ask_human")
    review_builder.add_edge("ask_human", END)
    review_layer = review_builder.compile(checkpointer=mode)

    builder = StateGraph(ParentState)
    builder.add_node("layer", review_layer)
    builder.add_edge(START, "layer")
    builder.add_edge("layer", END)
    return builder.compile(checkpointer=InMemorySaver())


for number, mode in enumerate((None, True, False), start=1):
    graph = build(mode)
    config = {"configurable": {"thread_id": f"review-{number}"}}
    print(f"{number}. checkpointer={mode}")
    for name in ("app.py", "db.py"):
        graph.invoke({"file": name, "summary": ""}, config)
        task = graph.get_state(config, subgraphs=True).tasks[0]
        CALLS.clear()
        result = graph.invoke(Command(resume="да"), config)
        print(
            f"   {name}: подграф на паузе {type(task.state).__name__}, "
            f"при возобновлении {CALLS}, summary: {result['summary']}"
        )
    if mode is True:
        print("   задач в get_state после конца:", len(graph.get_state(config, subgraphs=True).tasks))
        layer_config = {"configurable": {"thread_id": "review-2", "checkpoint_ns": "layer"}}
        saved = graph.get_state(layer_config)
        print("   visited по checkpoint_ns='layer':", saved.values["visited"])
