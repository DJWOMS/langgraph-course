"""Пример 5 урока 1: тот же разбор стенда, но агентом.

Агент собран функцией create_agent с двумя инструментами для того же стенда
mini_repo. Печатаются класс агента, имена узлов его графа и правки узлов при
запуске в режиме updates. Порядок вызовов инструментов выбирает модель,
температура нулевая, чтобы порядок меньше менялся от запуска к запуску.
"""

from pathlib import Path

from langchain.agents import create_agent

from course_model import build_model

REPO = Path(__file__).parent / "mini_repo"


def list_files() -> str:
    """Возвращает имена файлов Python в репозитории."""
    names = sorted(path.name for path in REPO.glob("*.py"))
    return ", ".join(names)


def file_lines(name: str) -> str:
    """Возвращает число строк в файле репозитория по его имени."""
    path = REPO / name
    if not path.exists():
        return f"Файла {name} в репозитории нет."
    return f"{name}: {len(path.read_text(encoding='utf-8').splitlines())} строк"


agent = create_agent(
    model=build_model(temperature=0, max_tokens=512),
    tools=[list_files, file_lines],
    system_prompt=(
        "Вы разбираете чужой репозиторий. Отвечайте по-русски, коротко. "
        "Числа берите только из инструментов, своих догадок не добавляйте."
    ),
)

print("КЛАСС АГЕНТА:", type(agent).__name__)
print("УЗЛЫ ГРАФА АГЕНТА:", sorted(agent.get_graph().nodes))
print()

update_no = 0
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "Сколько строк в файле db.py и какие ещё файлы есть?"}]},
    stream_mode="updates",
    version="v2",
):
    if chunk["type"] != "updates":
        continue
    for node, update in chunk["data"].items():
        update_no += 1
        messages = update.get("messages", []) if isinstance(update, dict) else []
        for message in messages:
            calls = getattr(message, "tool_calls", None)
            if calls:
                print(f"правка {update_no}: узел {node}, запрошены {[call['name'] for call in calls]}")
            else:
                text = message.text.replace("\n", " ")
                print(f"правка {update_no}: узел {node}, {type(message).__name__}: {text[:70]}")

print()
print("ПРАВОК ОТ УЗЛОВ:", update_no)

# Вывод:
# КЛАСС АГЕНТА: CompiledStateGraph
# УЗЛЫ ГРАФА АГЕНТА: ['__end__', '__start__', 'model', 'tools']
#
# правка 1: узел model, запрошены ['file_lines', 'list_files']
# правка 2: узел tools, ToolMessage: db.py: 15 строк
# правка 3: узел tools, ToolMessage: app.py, config.py, db.py, utils.py
# правка 4: узел model, AIMessage: Файл **db.py** содержит **15 строк**.  В репозитории также есть файлы:
#
# ПРАВОК ОТ УЗЛОВ: 4
