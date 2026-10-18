"""Ejecuta trabajo bloqueante (red, decodificación) fuera del hilo de Tkinter.

Tkinter no es seguro entre hilos: los resultados se entregan mediante una cola
que el hilo principal revisa con ``after``; los callbacks siempre corren en él.
"""

from __future__ import annotations

import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

POLL_MS = 40


class BackgroundRunner:
    def __init__(self, root: tk.Misc, max_workers: int = 4) -> None:
        self._root = root
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kto")
        self._results: queue.Queue[tuple[Callable[..., None], tuple[Any, ...]]] = queue.Queue()
        self._closed = False
        self._root.after(POLL_MS, self._drain)

    def submit(
        self,
        func: Callable[..., Any],
        *args: Any,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        if self._closed:
            return

        def job() -> None:
            try:
                result = func(*args)
            except BaseException as exc:  # se reenvía al hilo principal
                if on_error is not None:
                    self._results.put((on_error, (exc,)))
            else:
                if on_success is not None:
                    self._results.put((on_success, (result,)))

        self._executor.submit(job)

    def _drain(self) -> None:
        if self._closed:
            return
        try:
            while True:
                callback, args = self._results.get_nowait()
                try:
                    callback(*args)
                except tk.TclError:
                    pass  # el widget destino ya no existe
                except Exception:  # un fallo de UI no debe detener la cola
                    import traceback
                    traceback.print_exc()
        except queue.Empty:
            pass
        finally:
            if not self._closed:
                self._root.after(POLL_MS, self._drain)

    def shutdown(self) -> None:
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
