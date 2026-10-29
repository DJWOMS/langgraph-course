"""Пример 1 урока 7: подграф как узел родительского графа.

Слой карты, это граф из узлов collect_files и scan_files. Его можно вызвать
отдельно, как обычный граф. Родительский граф добавляет скомпилированный слой
узлом scan. Подграф и родитель делят ключи root и findings, ключ files
есть только у подграфа. Перед подграфом узел start_note пишет в findings
строку о начале обхода. Слой собирается в двух вариантах: без схем входа и
выхода и со схемами ScanInput и ScanOutput.
"""

import operator
from pathlib import Path
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"
INPUT_FINDINGS: list[list[str]] = []


class ScanState(TypedDict):
    root: str
    files: list[str]
    findings: Annotated[list[str], operator.add]


class ScanInput(TypedDict):
    root: str


class ScanOutput(TypedDict):
    findings: list[str]


def collect_files(state: ScanState) -> dict:
    """Собирает имена файлов стенда и запоминает findings на входе подграфа."""
    INPUT_FINDINGS.append(list(state["findings"]))
    names = sorted(path.name for path in Path(state["root"]).glob("*.py"))
    return {"files": names}


def scan_files(state: ScanState) -> dict:
    """Считает строки в каждом файле."""
    findings = []
    for name in state["files"]:
        lines = len((Path(state["root"]) / name).read_text(encoding="utf-8").splitlines())
        findings.append(f"{name}: строк {lines}")
    return {"findings": findings}


def build_layer(with_io: bool):
    """Слой карты: без схем входа и выхода или со схемами ScanInput и ScanOutput."""
    if with_io:
        builder = StateGraph(ScanState, input_schema=ScanInput, output_schema=ScanOutput)
    else:
        builder = StateGraph(ScanState)
    builder.add_node("collect_files", collect_files)
    builder.add_node("scan_files", scan_files)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "scan_files")
    builder.add_edge("scan_files", END)
    return builder.compile()


class RepoState(TypedDict):
    root: str
    findings: Annotated[list[str], operator.add]
    report: str


def start_note(state: RepoState) -> dict:
    """Пишет в находки строку о начале обхода."""
    return {"findings": ["обход начат"]}


def make_report(state: RepoState) -> dict:
    """Сводит находки в одну строку отчёта."""
    return {"report": f"находок {len(state['findings'])}"}


def build_parent(layer):
    """Родительский граф: start_note, слой узлом scan, make_report."""
    builder = StateGraph(RepoState)
    builder.add_node("start_note", start_note)
    builder.add_node("scan", layer)
    builder.add_node("make_report", make_report)
    builder.add_edge(START, "start_note")
    builder.add_edge("start_note", "scan")
    builder.add_edge("scan", "make_report")
    builder.add_edge("make_report", END)
    return builder.compile()


# 1. Слой карты вызывается сам по себе, как обычный граф.
scan_layer = build_layer(with_io=False)
alone = scan_layer.invoke({"root": str(REPO)})
print("1. подграф отдельно, ключи результата:", sorted(alone))
print("   находки:", alone["findings"])

# 2 и 3. Тот же слой узлом родительского графа, без схем и со схемами.
for number, with_io in ((2, False), (3, True)):
    INPUT_FINDINGS.clear()
    graph = build_parent(build_layer(with_io))
    result = graph.invoke({"root": str(REPO)})
    title = "со схемами входа и выхода" if with_io else "без схем входа и выхода"
    print(f"{number}. слой {title}")
    print("   findings на входе подграфа:", INPUT_FINDINGS[0])
    print("   ключи результата родителя:", sorted(result))
    print("   находки родителя:", result["findings"][:3], "...")
    print("   отчёт:", result["report"])
