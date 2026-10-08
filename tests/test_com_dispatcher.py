from __future__ import annotations

from concurrent.futures import Future, TimeoutError
import queue
import threading
from types import SimpleNamespace

import modeldesk_mcp.com_bridge.dispatcher as dispatcher_module
from modeldesk_mcp.com_bridge.dispatcher import ComStaDispatcher, ComWorkItem


def test_dispose_stops_worker_after_queue_saturation(monkeypatch) -> None:
    shutdown_put_modes: queue.Queue[str] = queue.Queue()
    worker_started = threading.Event()
    worker_release = threading.Event()
    pending_operation_ran = threading.Event()
    invocation_errors: list[Exception] = []

    class ObservedQueue(queue.Queue):
        def put(self, item, block=True, timeout=None):
            if item is None:
                if block:
                    shutdown_put_modes.put("blocking")
                    return super().put(item, block=block, timeout=timeout)
                try:
                    super().put(item, block=block, timeout=timeout)
                except queue.Full:
                    shutdown_put_modes.put("full")
                    raise
                shutdown_put_modes.put("enqueued")
                return
            return super().put(item, block=block, timeout=timeout)

    monkeypatch.setattr(
        dispatcher_module,
        "queue",
        SimpleNamespace(Queue=lambda maxsize: ObservedQueue(maxsize=1), Full=queue.Full),
    )
    monkeypatch.setattr(dispatcher_module, "SHUTDOWN_TIMEOUT_SECONDS", 0.01)
    dispatcher = ComStaDispatcher()

    def blocking_operation() -> str:
        worker_started.set()
        if not worker_release.wait(timeout=2):
            raise RuntimeError("test worker release timed out")
        return "finished"

    def invoke_blocking_operation() -> None:
        try:
            dispatcher.invoke(blocking_operation, timeout_seconds=5)
        except Exception as exception:
            invocation_errors.append(exception)

    caller = threading.Thread(target=invoke_blocking_operation)
    disposer: threading.Thread | None = None
    caller.start()

    try:
        assert worker_started.wait(timeout=1)
        dispatcher._work_items.put_nowait(ComWorkItem(lambda: pending_operation_ran.set(), Future()))

        disposer = threading.Thread(target=dispatcher.dispose)
        disposer.start()
        shutdown_put_modes.get(timeout=1)
        worker_release.set()

        assert pending_operation_ran.wait(timeout=1)
        caller.join(timeout=1)
        disposer.join(timeout=1)
        dispatcher._worker_thread.join(timeout=1)

        assert not caller.is_alive()
        assert not disposer.is_alive()
        assert not dispatcher._worker_thread.is_alive()
        assert invocation_errors == []
    finally:
        worker_release.set()
        if dispatcher._worker_thread.is_alive():
            try:
                dispatcher._work_items.put(None, block=True, timeout=1)
            except queue.Full:
                pass
        caller.join(timeout=2)
        if disposer is not None:
            disposer.join(timeout=2)
        dispatcher._worker_thread.join(timeout=2)


def test_invoke_racing_dispose_is_not_left_behind_shutdown_sentinel(monkeypatch) -> None:
    work_put_entered = threading.Event()
    allow_work_put = threading.Event()
    dispose_started = threading.Event()
    work_ran = threading.Event()
    invocation_errors: list[Exception] = []
    first_work_put = True

    class PausingQueue(queue.Queue):
        def put(self, item, block=True, timeout=None):
            nonlocal first_work_put
            if item is not None and first_work_put:
                first_work_put = False
                work_put_entered.set()
                if not allow_work_put.wait(timeout=2):
                    raise RuntimeError("test enqueue release timed out")
            return super().put(item, block=block, timeout=timeout)

    monkeypatch.setattr(
        dispatcher_module,
        "queue",
        SimpleNamespace(Queue=lambda maxsize: PausingQueue(maxsize=2), Full=queue.Full),
    )
    monkeypatch.setattr(dispatcher_module, "SHUTDOWN_TIMEOUT_SECONDS", 0.01)
    dispatcher = ComStaDispatcher()

    def invoke_operation() -> None:
        try:
            dispatcher.invoke(lambda: work_ran.set(), timeout_seconds=1)
        except Exception as exception:
            invocation_errors.append(exception)

    caller = threading.Thread(target=invoke_operation)
    caller.start()
    disposer: threading.Thread | None = None

    try:
        assert work_put_entered.wait(timeout=1)

        def dispose_dispatcher() -> None:
            dispose_started.set()
            dispatcher.dispose()

        disposer = threading.Thread(target=dispose_dispatcher)
        disposer.start()
        assert dispose_started.wait(timeout=1)

        allow_work_put.set()
        caller.join(timeout=2)
        disposer.join(timeout=2)
        dispatcher._worker_thread.join(timeout=1)

        assert not caller.is_alive()
        assert disposer is not None and not disposer.is_alive()
        assert invocation_errors == []
        assert not dispatcher._worker_thread.is_alive()
        assert work_ran.is_set()
    finally:
        allow_work_put.set()
        caller.join(timeout=2)
        if disposer is not None:
            disposer.join(timeout=2)
        dispatcher._worker_thread.join(timeout=2)
        try:
            queued_item = dispatcher._work_items.get_nowait()
        except queue.Empty:
            pass
        else:
            if isinstance(queued_item, ComWorkItem):
                queued_item.future.cancel()
