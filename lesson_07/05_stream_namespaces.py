"""Пример 5 урока 7: поток из подграфа и пространство имён в событиях.

Родительский граф из примера 1 без start_note: узел scan, это слой карты
scan_layer, после него make_report. Поток в режиме updates вызывается два
раза: без subgraphs и с subgraphs=True. У каждого события печатается поле ns.
"""

import operator
from pathlib import Path
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class ScanState(TypedDict):
    root: str
    files: list[str]
    findings: Annotated[list[str], operator.add]


def collect_files(state: ScanState) -> dict:
    """Собирает имена файлов стенда."""
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def scan_files(state: ScanState) -> dict:
    """Считает строки в каждом файле."""
    findings = []
    for name in state["files"]:
        lines = len((Path(state["root"]) / name).read_text(encoding="utf-8").splitlines())
        findings.append(f"{name}: строк {lines}")
    return {"findings": findings}


scan_builder = StateGraph(ScanState)
scan_builder.add_node("collect_files", collect_files)
scan_builder.add_node("scan_files", scan_files)
scan_builder.add_edge(START, "collect_files")
scan_builder.add_edge("collect_files", "scan_files")
scan_builder.add_edge("scan_files", END)
scan_layer = scan_builder.compile()


class RepoState(TypedDict):
    root: str
    findings: Annotated[list[str], operator.add]
    report: str


def make_report(state: RepoState) -> dict:
    """Сводит находки в одну строку отчёта."""
    return {"report": f"находок {len(state['findings'])}"}


builder = StateGraph(RepoState)
builder.add_node("scan", scan_layer)
builder.add_node("make_report", make_report)
builder.add_edge(START, "scan")
builder.add_edge("scan", "make_report")
builder.add_edge("make_report", END)
graph = builder.compile()


def short(namespace: tuple[str, ...]) -> list[str]:
    """Заменяет id задачи в пространстве имён меткой: id меняется от запуска к запуску."""
    return [part.split(":")[0] + ":<id>" for part in namespace]


for number, subgraphs in enumerate((False, True), start=1):
    print(f"{number}. subgraphs={subgraphs}")
    for chunk in graph.stream(
        {"root": str(REPO)},
        stream_mode="updates",
        subgraphs=subgraphs,
        version="v2",
    ):
        for node, update in chunk["data"].items():
            print(f"   ns {short(chunk['ns'])}  узел {node}  ключи {sorted(update)}")
