import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class QueueTask:
    task_id: str
    function: Callable[[], Awaitable]
    future: Optional[asyncio.Future] = None


class DownloadQueue:
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent

        self.queue: asyncio.Queue[QueueTask] = asyncio.Queue()

        self.workers: list[asyncio.Task] = []

        self.started = False

    async def start(self) -> None:
        if self.started:
            return

        self.started = True

        for index in range(self.max_concurrent):
            worker = asyncio.create_task(
                self._worker(index + 1)
            )

            self.workers.append(worker)

    async def stop(self) -> None:
        if not self.started:
            return

        self.started = False

        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(
            *self.workers,
            return_exceptions=True,
        )

        self.workers.clear()

    async def add(
        self,
        task_id: str,
        function: Callable[[], Awaitable],
    ):
        loop = asyncio.get_running_loop()

        future = loop.create_future()

        task = QueueTask(
            task_id=task_id,
            function=function,
            future=future,
        )

        await self.queue.put(task)

        return future

    async def _worker(self, worker_id: int) -> None:
        while self.started:

            task = await self.queue.get()

            try:

                result = await task.function()

                if (
                    task.future
                    and not task.future.done()
                ):
                    task.future.set_result(result)

            except Exception as error:

                if (
                    task.future
                    and not task.future.done()
                ):
                    task.future.set_exception(error)

            finally:
                self.queue.task_done()

    def size(self) -> int:
        return self.queue.qsize()

    def is_running(self) -> bool:
        return self.started