"""Пример 3 урока 2: почему списку сообщений нужен add_messages.

Три узла складывают переписку про стенд mini_repo: вопрос, черновик ответа и
его исправленная версия с тем же идентификатором. Граф собран трижды: ключ без
редьюсера, ключ с operator.add и ключ с add_messages. Печатается, что каждый вариант
ключа делает с исправленным сообщением и с краткой формой записи.
"""

import operator
from pathlib import Path
from typing import Annotated

from langchain.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class PlainState(TypedDict):
    messages: list[AnyMessage]


class AddState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


class MessagesGraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def ask(state) -> dict:
    """Кладёт вопрос пользователя краткой формой записи."""
    return {"messages": [{"role": "user", "content": "Сколько файлов в репозитории?"}]}


def draft(state) -> dict:
    """Кладёт черновик ответа с явным идентификатором."""
    return {"messages": [AIMessage(content="Файлов несколько.", id="answer")]}


def fix(state) -> dict:
    """Возвращает исправленный ответ под тем же идентификатором."""
    count = len(sorted(REPO.glob("*.py")))
    return {"messages": [AIMessage(content=f"Файлов {count}.", id="answer")]}


def build(schema) -> object:
    """Собирает цепочку из трёх узлов на переданной схеме."""
    builder = StateGraph(schema)
    builder.add_node("ask", ask)
    builder.add_node("draft", draft)
    builder.add_node("fix", fix)
    builder.add_edge(START, "ask")
    builder.add_edge("ask", "draft")
    builder.add_edge("draft", "fix")
    builder.add_edge("fix", END)
    return builder.compile()


def show(title: str, schema) -> None:
    """Печатает итоговую переписку одной строкой на сообщение."""
    print(title)
    try:
        result = build(schema).invoke({"messages": []})
    except Exception as error:
        print("   упало:", type(error).__name__, error)
        return
    for message in result["messages"]:
        kind = type(message).__name__
        text = message.content if hasattr(message, "content") else message
        print(f"   {kind}(id={getattr(message, 'id', None)}): {text}")


show("1. ключ без редьюсера", PlainState)
show("2. ключ с operator.add", AddState)
show("3. ключ с add_messages", MessagesGraphState)

# Вывод:
# 1. ключ без редьюсера
#    AIMessage(id=answer): Файлов 4.
# 2. ключ с operator.add
#    dict(id=None): {'role': 'user', 'content': 'Сколько файлов в репозитории?'}
#    AIMessage(id=answer): Файлов несколько.
#    AIMessage(id=answer): Файлов 4.
# 3. ключ с add_messages
#    HumanMessage(id=d36b75fa-1ef2-418a-823a-8b47ce57379b): Сколько файлов в репозитории?
#    AIMessage(id=answer): Файлов 4.
#
# Идентификатор HumanMessage случайный, при своём запуске он будет другим.
