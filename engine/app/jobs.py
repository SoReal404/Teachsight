"""Job state machine: steps, percent, ETA, pause, and pause-and-ask (spec section 9)."""
from __future__ import annotations
import threading, time, uuid

STEPS = ["Checking data", "Preparing images", "Choosing model", "Training", "Evaluating", "Exporting"]


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, params: dict):
        self.id = uuid.uuid4().hex[:8]
        self.params = params
        self.status = "running"          # running | paused | asking | done | failed | cancelled
        self.steps = {s: {"status": "waiting", "percent": 0, "eta_s": None} for s in STEPS}
        self.question: dict | None = None
        self.eta_s: float | None = None
        self.result: dict | None = None
        self.error: str | None = None
        self._pause = threading.Event()
        self._pause.set()
        self._answer = threading.Event()
        self._answer_value: str | None = None
        self._cancel = False
        self.started = time.time()

    def set_step(self, name: str, status: str, percent: float = 0, eta_s: float | None = None):
        self.steps[name].update(status=status, percent=round(percent, 1), eta_s=eta_s)

    def checkpoint(self):
        """Call between steps of work: honours pause and cancel."""
        if self._cancel:
            raise Cancelled()
        self._pause.wait()
        if self._cancel:
            raise Cancelled()

    def ask(self, question: str, options: list[dict]) -> str:
        """Pause the job, show a question, block until the user answers."""
        self.question = {"text": question, "options": options}
        self.status = "asking"
        self._answer.clear()
        self._answer.wait()
        if self._cancel:
            raise Cancelled()
        self.question, self.status = None, "running"
        return self._answer_value or ""

    def answer(self, value: str):
        self._answer_value = value
        self._answer.set()

    def pause(self):
        self._pause.clear(); self.status = "paused"

    def resume(self):
        self._pause.set(); self.status = "running"

    def cancel(self):
        self._cancel = True; self._pause.set(); self._answer.set()

    def view(self) -> dict:
        done = sum(1 for s in self.steps.values() if s["status"] == "done")
        cur = next((s["percent"] for s in self.steps.values() if s["status"] == "running"), 0)
        return {"id": self.id, "status": self.status, "steps": self.steps, "question": self.question,
                "overall_percent": round((done + cur / 100) / len(STEPS) * 100, 1),
                "eta_s": self.eta_s, "finish_at": (time.time() + self.eta_s) if self.eta_s else None,
                "result": self.result, "error": self.error}


JOBS: dict[str, Job] = {}
