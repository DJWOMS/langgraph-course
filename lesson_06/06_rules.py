"""Пример 6 урока 6: четыре нарушения правил паузы.

Каждое нарушение стоит в своём узле, узел собирается в граф из одного узла
и запускается в своём thread:
1) interrupt() внутри try/except Exception;
2) первая пауза задаётся по условию, которое меняется между вызовами;
3) в значении паузы лежит функция;
4) запись в журнал стоит до паузы.
"""

import operator
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

ASK_FILE = {"value": True}
JOURNAL: list[str] = []


class AskState(TypedDict):
    answers: Annotated[list[str], operator.add]


def build(node):
    """Граф из одного узла с чекпойнтером."""
    builder = StateGraph(AskState)
    builder.add_node(node.__name__, node)
    builder.add_edge(START, node.__name__)
    builder.add_edge(node.__name__, END)
    return builder.compile(checkpointer=InMemorySaver())


def ask_inside_try(state: AskState) -> dict:
    """Нарушение 1: except Exception перехватывает остановку."""
    try:
        answer = interrupt("Выполнить app.py?")
    except Exception as error:
        answer = f"перехвачено {type(error).__name__}"
    return {"answers": [answer]}


def ask_by_condition(state: AskState) -> dict:
    """Нарушение 2: число пауз зависит от флага, который меняется между вызовами."""
    answers = []
    if ASK_FILE["value"]:
        answers.append("файл: " + interrupt("Какой файл выполнить?"))
    answers.append("аргументы: " + interrupt("С какими аргументами?"))
    return {"answers": answers}


def ask_with_function(state: AskState) -> dict:
    """Нарушение 3: в значении паузы функция."""
    answer = interrupt({"вопрос": "Выполнить app.py?", "проверка": str.isdigit})
    return {"answers": [answer]}


def journal_then_ask(state: AskState) -> dict:
    """Нарушение 4: запись в журнал до паузы."""
    JOURNAL.append("запрошено выполнение app.py")
    answer = interrupt("Выполнить app.py?")
    return {"answers": [answer]}


START_STATE = {"answers": []}

# 1. Остановка перехвачена: паузы нет, запуск закончился без ответа человека.
graph = build(ask_inside_try)
config = {"configurable": {"thread_id": "rule-1"}}
result = graph.invoke(START_STATE, config)
print("1. пауза:", "__interrupt__" in result, "| ответы:", result["answers"])

# 2. Между ответами флаг сменился, и ответ ушёл не в тот вопрос.
graph = build(ask_by_condition)
config = {"configurable": {"thread_id": "rule-2"}}
graph.invoke(START_STATE, config)
graph.invoke(Command(resume="app.py"), config)
ASK_FILE["value"] = False
result = graph.invoke(Command(resume="--verbose"), config)
print("2. ответы:", result["answers"])

# 3. Функцию в значении паузы чекпойнтер не сохраняет.
graph = build(ask_with_function)
config = {"configurable": {"thread_id": "rule-3"}}
try:
    graph.invoke(START_STATE, config)
except TypeError as error:
    print("3.", type(error).__name__, error)

# 4. Узел выполнился дважды, запись в журнале задвоилась.
graph = build(journal_then_ask)
config = {"configurable": {"thread_id": "rule-4"}}
graph.invoke(START_STATE, config)
graph.invoke(Command(resume="да"), config)
print("4. журнал:", JOURNAL)
