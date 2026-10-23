"""Пример 5 урока 2: раздельные схемы входа и выхода, приватный ключ и контекст.

Граф строит карточку стенда mini_repo. На входе принимается один ключ, наружу
отдаётся тоже один, а промежуточные размеры файлов идут приватным ключом от
первого узла ко второму. Настройки запуска передаются контекстом.
"""

from dataclasses import dataclass
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "mini_repo"


class InputState(TypedDict):
    root: str


class OutputState(TypedDict):
    card: str


class OverallState(TypedDict):
    root: str
    card: str
    files: list[str]


class PrivateState(TypedDict):
    sizes: dict[str, int]


@dataclass
class RunContext:
    label: str = "обзор"
    max_files: int = 2


def scan(state: InputState, runtime: Runtime[RunContext]) -> PrivateState:
    """Считает строки в первых файлах стенда, число файлов задаёт контекст запуска."""
    print("   узел scan получил runtime.context =", runtime.context)
    context = runtime.context or RunContext()
    paths = sorted(Path(state["root"]).glob("*.py"))[: context.max_files]
    sizes = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in paths
    }
    return {"sizes": sizes}


def make_card(state: PrivateState, runtime: Runtime[RunContext]) -> OverallState:
    """Собирает карточку из приватных размеров и подписи из контекста."""
    context = runtime.context or RunContext()
    parts = [f"{name}: {lines}" for name, lines in state["sizes"].items()]
    return {
        "card": f"{context.label}, " + "; ".join(parts),
        "files": list(state["sizes"]),
    }


builder = StateGraph(
    OverallState,
    context_schema=RunContext,
    input_schema=InputState,
    output_schema=OutputState,
)
builder.add_node("scan", scan)
builder.add_node("make_card", make_card)
builder.add_edge(START, "scan")
builder.add_edge("scan", "make_card")
builder.add_edge("make_card", END)

graph = builder.compile()

print("1. без контекста вовсе:", graph.invoke({"root": str(REPO)}))
print("2. пустой контекст:", graph.invoke({"root": str(REPO)}, context={}))
print(
    "3. свой контекст:",
    graph.invoke({"root": str(REPO)}, context={"label": "полный обход", "max_files": 4}),
)

print("4. снимки состояния потоком:")
for chunk in graph.stream({"root": str(REPO)}, stream_mode="values", version="v2"):
    print("   ключи снимка:", sorted(chunk["data"]))

# Вывод:
#    узел scan получил runtime.context = None
# 1. без контекста вовсе: {'card': 'обзор, app.py: 13; config.py: 6'}
#    узел scan получил runtime.context = RunContext(label='обзор', max_files=2)
# 2. пустой контекст: {'card': 'обзор, app.py: 13; config.py: 6'}
#    узел scan получил runtime.context = RunContext(label='полный обход', max_files=4)
# 3. свой контекст: {'card': 'полный обход, app.py: 13; config.py: 6; db.py: 15; utils.py: 10'}
# 4. снимки состояния потоком:
#    ключи снимка: ['root']
#    узел scan получил runtime.context = None
#    ключи снимка: ['root', 'sizes']
#    ключи снимка: ['card', 'files', 'root', 'sizes']
