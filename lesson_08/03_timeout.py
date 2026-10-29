"""Пример 3 урока 8: таймаут попытки, таймаут простоя и процесс файла.

Узел run_file асинхронный: файл из bad_repo выполняется процессом из
asyncio.create_subprocess_exec. После каждой строки вывода узел вызывает
runtime.heartbeat(). hang.py зависает, chatty.py работает около секунды и
печатает строку каждые 0,25 секунды. Фабрика make_run_file собирает узел в
двух вариантах: без остановки процесса файла и с остановкой в блоке finally.
PROCESSES хранит процессы, чтобы после паузы в 0,5 секунды проверить,
работают ли они.
"""

import asyncio
import sys
from pathlib import Path

from langgraph.errors import NodeTimeoutError
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy, TimeoutPolicy
from typing_extensions import TypedDict

REPO = Path(__file__).parent / "bad_repo"
PROCESSES: list[asyncio.subprocess.Process] = []


class RunState(TypedDict):
    current: str
    lines: int


def make_run_file(stop_process: bool):
    """Узел run_file. При stop_process=True процесс файла останавливается при отмене попытки."""

    async def run_file(state: RunState, runtime: Runtime) -> dict:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            state["current"],
            cwd=REPO,
            stdout=asyncio.subprocess.PIPE,
        )
        PROCESSES.append(process)
        try:
            lines = 0
            async for _ in process.stdout:
                lines += 1
                runtime.heartbeat()
            await process.wait()
            return {"lines": lines}
        finally:
            if stop_process and process.returncode is None:
                process.kill()
                await process.wait()

    return run_file


def build(node, timeout, retry_policy=None):
    """Граф из одного узла run_file с таймаутом."""
    builder = StateGraph(RunState)
    builder.add_node("run_file", node, timeout=timeout, retry_policy=retry_policy)
    builder.add_edge(START, "run_file")
    builder.add_edge("run_file", END)
    return builder.compile()


def run_file_sync(state: RunState) -> dict:
    """Синхронный узел: таймаут для него не поддерживается."""
    return {"lines": 0}


# 1. Таймаут у синхронного узла и вызов invoke у асинхронного.
try:
    build(run_file_sync, timeout=0.5)
except ValueError as error:
    print("1. компиляция синхронного узла:", error)
try:
    build(make_run_file(True), timeout=0.5).invoke({"current": "ok.py", "lines": 0})
except ValueError as error:
    print("   invoke асинхронного узла:", type(error).__name__)


async def main() -> None:
    retry = RetryPolicy(max_attempts=2, initial_interval=0.1, jitter=False)

    # 2 и 3. Зависший файл, таймаут 0,5 секунды, две попытки.
    for number, stop_process in ((2, False), (3, True)):
        PROCESSES.clear()
        graph = build(make_run_file(stop_process), timeout=0.5, retry_policy=retry)
        try:
            await graph.ainvoke({"current": "hang.py", "lines": 0})
        except NodeTimeoutError as error:
            await asyncio.sleep(0.5)
            alive = sum(process.returncode is None for process in PROCESSES)
            title = "с остановкой процесса" if stop_process else "без остановки процесса"
            print(f"{number}. hang.py {title}: {type(error).__name__}, kind={error.kind}")
            print(f"   попыток {len(PROCESSES)}, процессов файла работает {alive}")
        # Уборка: процессы, пережившие таймаут, останавливаются здесь.
        for process in PROCESSES:
            if process.returncode is None:
                process.kill()
                await process.wait()

    # 4 и 5. Файл работает дольше 0,6 секунды и печатает строку каждые 0,25 секунды.
    node = make_run_file(True)
    for number, title, policy in (
        (4, "run_timeout=0.6", TimeoutPolicy(run_timeout=0.6)),
        (5, "idle_timeout=0.6", TimeoutPolicy(idle_timeout=0.6)),
    ):
        try:
            result = await build(node, timeout=policy).ainvoke({"current": "chatty.py", "lines": 0})
            print(f"{number}. chatty.py, {title}: строк {result['lines']}")
        except NodeTimeoutError as error:
            print(f"{number}. chatty.py, {title}: {type(error).__name__}, kind={error.kind}")


asyncio.run(main())
