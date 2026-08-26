"""STA dispatcher for bounded ModelDesk COM calls.

ModelDesk COM is apartment-threaded. Every COM operation therefore crosses this
dispatcher, which owns the worker thread's COM initialization, timeout wait, and
shutdown lifecycle. Callers must pass a bounded operation and handle its
structured result at the gateway boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, TimeoutError
from dataclasses import dataclass
import queue
import threading
from typing import Generic, TypeVar


T = TypeVar("T")
MAX_QUEUED_OPERATIONS = 256
SHUTDOWN_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class ComWorkItem(Generic[T]):
    """Queued unit of COM work executed on the STA worker thread."""

    operation: Callable[[], T]
    future: Future[T]


class ComStaDispatcher:
    """Dispatches COM operations to a dedicated STA worker thread."""

    def __init__(self) -> None:
        self._work_items: queue.Queue[ComWorkItem[object] | None] = queue.Queue(maxsize=MAX_QUEUED_OPERATIONS)
        self._disposed = False
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="ModelDesk MCP COM STA Dispatcher",
            daemon=True,
        )
        self._worker_thread.start()

    def invoke(self, operation: Callable[[], T], timeout_seconds: int) -> T:
        """Execute an operation on the COM STA thread with a bounded timeout."""

        if operation is None:
            raise ValueError("operation must not be None")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self._disposed:
            raise RuntimeError("COM dispatcher has been disposed")

        future: Future[T] = Future()
        work_item: ComWorkItem[T] = ComWorkItem(operation, future)
        try:
            self._work_items.put(work_item, block=False)
        except queue.Full as exc:
            raise RuntimeError("COM dispatcher queue is full.") from exc

        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise TimeoutError(f"COM operation timed out after {timeout_seconds} seconds.") from exc

    def dispose(self) -> None:
        """Complete the queue and release dispatcher resources."""

        if self._disposed:
            return
        self._disposed = True
        try:
            self._work_items.put(None, block=False)
        except queue.Full:
            pass
        self._worker_thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)

    def _process_queue(self) -> None:
        pythoncom = _try_import_pythoncom()
        if pythoncom is not None:
            pythoncom.CoInitialize()
        try:
            while True:
                work_item = self._work_items.get()
                if work_item is None:
                    return
                if work_item.future.cancelled():
                    continue
                try:
                    result = work_item.operation()
                    work_item.future.set_result(result)
                except Exception as exception:  # noqa: BLE001 - propagated to tool boundary.
                    work_item.future.set_exception(exception)
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()


def _try_import_pythoncom() -> object | None:
    try:
        import pythoncom
    except ImportError:
        return None
    return pythoncom
