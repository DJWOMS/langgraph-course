"""Пример 2 урока 7: вызов подграфа внутри узла, функция-обёртка между схемами.

У родительского графа своя схема: repo и notes, общих ключей со слоем карты
scan_layer у неё нет. Узел run_scan вызывает scan_layer.invoke. Узел
start_note пишет в notes строку о начале обхода, как в примере 1.
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


class ProjectState(TypedDict):
    repo: str
    notes: Annotated[list[str], operator.add]


def start_note(state: ProjectState) -> dict:
    """Пишет в заметки строку о начале обхода."""
    return {"notes": ["обход начат"]}


def run_scan(state: ProjectState) -> dict:
    """Функция-обёртка: вход подграфа из состояния родителя и результат обратно."""
    scan_input = {"root": state["repo"], "files": [], "findings": []}
    scan_result = scan_layer.invoke(scan_input)
    return {"notes": [f"карта: {line}" for line in scan_result["findings"]]}


builder = StateGraph(ProjectState)
builder.add_node("start_note", start_note)
builder.add_node("run_scan", run_scan)
builder.add_edge(START, "start_note")
builder.add_edge("start_note", "run_scan")
builder.add_edge("run_scan", END)
graph = builder.compile()

result = graph.invoke({"repo": str(REPO), "notes": []})
print("ключи результата:", sorted(result))
for line in result["notes"]:
    print("   ", line)
