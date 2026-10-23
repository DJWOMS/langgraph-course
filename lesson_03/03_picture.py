"""Пример 3 урока 3: что попадает на схему графа.

Одна и та же развилка собрана на условном ребре, на Command и с параметром
destinations, с подсказкой о переходах и без неё. Для каждой сборки печатаются
рёбра схемы графа. В конце показан переход на узел, которого в графе нет.
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict


class ScanState(TypedDict):
    files: list[str]
    report: str


def quick_scan(state: ScanState) -> dict:
    """Короткий разбор."""
    return {"report": "быстрый разбор"}


def deep_scan(state: ScanState) -> dict:
    """Подробный разбор."""
    return {"report": "подробный разбор"}


def edges(builder: StateGraph) -> list[str]:
    """Возвращает рёбра собранного графа в том виде, в каком их строит схема."""
    graph = builder.compile().get_graph()
    return [
        f"{edge.source} -> {edge.target}"
        + (" (условное)" if edge.conditional else "")
        for edge in graph.edges
    ]


def base(collect) -> StateGraph:
    """Каркас из трёх узлов, общий для всех вариантов."""
    builder = StateGraph(ScanState)
    builder.add_node("collect_files", collect)
    builder.add_node("quick_scan", quick_scan)
    builder.add_node("deep_scan", deep_scan)
    builder.add_edge(START, "collect_files")
    builder.add_edge("quick_scan", END)
    builder.add_edge("deep_scan", END)
    return builder


def collect_plain(state: ScanState) -> dict:
    """Обычный узел без Command, переход задаёт условное ребро."""
    return {"files": ["app.py"]}


def route_typed(state: ScanState) -> Literal["quick_scan", "deep_scan"]:
    """Маршрут с аннотацией возврата."""
    return "quick_scan"


def route_bare(state):
    """Тот же маршрут, но без аннотации возврата."""
    return "quick_scan"


def collect_cmd_typed(state: ScanState) -> Command[Literal["quick_scan", "deep_scan"]]:
    """Command с аннотацией возврата."""
    return Command(update={"files": ["app.py"]}, goto="quick_scan")


def collect_cmd_bare(state):
    """Тот же Command, но без аннотации возврата."""
    return Command(update={"files": ["app.py"]}, goto="quick_scan")


# 1. Условное ребро, у функции маршрутизации есть аннотация.
typed = base(collect_plain)
typed.add_conditional_edges("collect_files", route_typed)
print("1. условное ребро с аннотацией:", edges(typed))

# 2. То же самое без аннотации и без словаря соответствия.
bare = base(collect_plain)
bare.add_conditional_edges("collect_files", route_bare)
print("2. условное ребро без аннотации:", edges(bare))

# 3. Словарь соответствия возвращает переходы на схему.
mapped = base(collect_plain)
mapped.add_conditional_edges(
    "collect_files",
    route_bare,
    {"quick_scan": "quick_scan", "deep_scan": "deep_scan"},
)
print("3. условное ребро со словарём:", edges(mapped))

# 4. Command с аннотацией и без неё.
cmd_typed = base(collect_cmd_typed)
print("4. Command с аннотацией:", edges(cmd_typed))

cmd_bare = base(collect_cmd_bare)
print("   Command без аннотации:", edges(cmd_bare))

# 5. Тот же Command без аннотации, но с destinations при регистрации узла.
named = StateGraph(ScanState)
named.add_node(
    "collect_files",
    collect_cmd_bare,
    destinations={"quick_scan": "файлов много", "deep_scan": "файлов мало"},
)
named.add_node("quick_scan", quick_scan)
named.add_node("deep_scan", deep_scan)
named.add_edge(START, "collect_files")
named.add_edge("quick_scan", END)
named.add_edge("deep_scan", END)
print("5. Command с destinations:", edges(named))
print()
print(named.compile().get_graph().draw_mermaid())


# 6. Переход на узел, которого в графе нет.
def goto_nowhere_typed(state: ScanState) -> Command[Literal["nowhere"]]:
    """Аннотация называет узел, которого в графе нет."""
    return Command(goto="nowhere")


def goto_nowhere_bare(state):
    """То же самое, но без аннотации."""
    return Command(goto="nowhere")


broken = StateGraph(ScanState)
broken.add_node("collect_files", goto_nowhere_typed)
broken.add_edge(START, "collect_files")
try:
    broken.compile()
except ValueError as error:
    print("6. переход в никуда с аннотацией:", type(error).__name__, error)

silent = StateGraph(ScanState)
silent.add_node("collect_files", goto_nowhere_bare)
silent.add_node("quick_scan", quick_scan)
silent.add_edge(START, "collect_files")
silent.add_edge("quick_scan", END)
print("   переход в никуда без аннотации:", silent.compile().invoke({"files": []}))

# Вывод:
# 1. условное ребро с аннотацией: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
# 2. условное ребро без аннотации: ['__start__ -> collect_files', 'collect_files -> __end__']
# 3. условное ребро со словарём: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
# 4. Command с аннотацией: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
#    Command без аннотации: ['__start__ -> collect_files', 'collect_files -> __end__']
# 5. Command с destinations: ['__start__ -> collect_files', 'collect_files -> deep_scan (условное)', 'collect_files -> quick_scan (условное)', 'deep_scan -> __end__', 'quick_scan -> __end__']
#
# ---
# config:
#   flowchart:
#     curve: linear
# ---
# graph TD;
# 	__start__([<p>__start__</p>]):::first
# 	collect_files(collect_files)
# 	quick_scan(quick_scan)
# 	deep_scan(deep_scan)
# 	__end__([<p>__end__</p>]):::last
# 	__start__ --> collect_files;
# 	collect_files -. &nbsp;файлов мало&nbsp; .-> deep_scan;
# 	collect_files -. &nbsp;файлов много&nbsp; .-> quick_scan;
# 	deep_scan --> __end__;
# 	quick_scan --> __end__;
# 	classDef default fill:#f2f0ff,line-height:1.2
# 	... (ещё две строки classDef)
#
# 6. переход в никуда с аннотацией: ValueError Found edge ending at unknown node `nowhere`
#    переход в никуда без аннотации: {'files': []}
#
# В пункте 6 без аннотации LangGraph пишет в журнал (stderr, модуль logging):
# Task collect_files with path ('__pregel_pull', 'collect_files') wrote to
# unknown channel branch:to:nowhere, ignoring it.
