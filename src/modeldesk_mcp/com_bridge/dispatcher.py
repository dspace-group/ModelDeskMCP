"""STA dispatcher for bounded ModelDesk COM calls.

ModelDesk COM is apartment-threaded. Every COM operation therefore crosses this
dispatcher, which owns the worker thread's COM initialization, timeout wait, and
shutdown lifecycle. Callers must pass a bounded operation and handle its
structured result at the gateway boundary.
Admission and shutdown are linearized so accepted work always precedes the
worker's terminal signal.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, TimeoutError
from contextvars import copy_context
from dataclasses import dataclass
import queue
import threading
from time import monotonic
from typing import Generic, TypeVar

from anyio.from_thread import NoEventLoopError, check_cancelled


T = TypeVar("T")
MAX_QUEUED_OPERATIONS = 256
SHUTDOWN_TIMEOUT_SECONDS = 5.0
CANCELLATION_POLL_SECONDS = 0.05


class ComOperationTimeout(TimeoutError):
    def __init__(self, timeout_seconds: float, *, cancelled_before_start: bool) -> None:
        self.cancelled_before_start = cancelled_before_start
        outcome = (
            "Cancelled before execution."
            if cancelled_before_start
            else "Execution has started and its outcome is unknown. Do not retry until you verify the target state."
        )
        super().__init__(f"COM operation timed out after {timeout_seconds} seconds. {outcome}")


@dataclass(frozen=True, slots=True)
class ComWorkItem(Generic[T]):
    """Queued unit of COM work executed on the STA worker thread."""

    operation: Callable[[], T]
    future: Future[T]


class ComStaDispatcher:
    """Serialize COM operations and linearize admission with worker shutdown."""

    def __init__(self) -> None:
        self._work_items: queue.Queue[ComWorkItem[object] | None] = queue.Queue(maxsize=MAX_QUEUED_OPERATIONS)
        self._lifecycle_lock = threading.Lock()
        self._shutdown_requested = threading.Event()
        self._disposed = False
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="ModelDesk MCP COM STA Dispatcher",
            daemon=True,
        )
        self._worker_thread.start()

    def invoke(self, operation: Callable[[], T], timeout_seconds: float) -> T:
        """Run on the STA; cancel queued work on timeout, never interrupt running COM."""

        if operation is None:
            raise ValueError("operation must not be None")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        try:
            check_cancelled()
            cancellable = True
        except NoEventLoopError:
            cancellable = False
        future: Future[T] = Future()
        context = copy_context()
        work_item: ComWorkItem[T] = ComWorkItem(lambda: context.run(operation), future)
        with self._lifecycle_lock:
            if self._disposed:
                raise RuntimeError("COM dispatcher has been disposed")
            try:
                self._work_items.put(work_item, block=False)
            except queue.Full as exc:
                raise RuntimeError("COM dispatcher queue is full.") from exc

        deadline = monotonic() + timeout_seconds
        try:
            while True:
                if cancellable:
                    check_cancelled()
                remaining = max(0.0, deadline - monotonic())
                interval = min(remaining, CANCELLATION_POLL_SECONDS) if cancellable else remaining
                try:
                    return future.result(timeout=interval)
                except TimeoutError as exc:
                    if future.done():
                        return future.result()
                    if monotonic() >= deadline:
                        raise ComOperationTimeout(timeout_seconds, cancelled_before_start=future.cancel()) from exc
        except BaseException:
            future.cancel()
            raise

    def dispose(self) -> None:
        """Close admission, request worker shutdown, and wait for a bounded time.

        Already accepted operations are not cancelled. If the bounded queue is
        full, the worker drains it and exits after observing the shutdown flag;
        a blocked COM operation can outlive the bounded join.
        """

        with self._lifecycle_lock:
            if self._disposed:
                return
            self._disposed = True
            try:
                self._work_items.put(None, block=False)
            except queue.Full:
                # The worker exits after draining accepted work; none is dropped.
                self._shutdown_requested.set()
        self._worker_thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)

    def _process_queue(self) -> None:
        pythoncom = _try_import_pythoncom()
        if pythoncom is not None:
            pythoncom.CoInitialize()
        try:
            while True:
                if self._shutdown_requested.is_set() and self._work_items.empty():
                    return
                work_item = self._work_items.get()
                if work_item is None:
                    return
                if not work_item.future.set_running_or_notify_cancel():
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
