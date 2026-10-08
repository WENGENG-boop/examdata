"""Legacy Node-CLI bridge contract for ielts/toefl routes (plan 5.5, A12).

The legacy gateway (`examdata/src/examdata/api/ielts.py`, `toefl.py`) spawns a
short-lived node subprocess per request and maps the process outcome onto HTTP
itself. The staged architecture replaces that spawn with the controlled Node
runner (`runtime/runner.py`, plan 6.4). This module is the *proposal* for the
missing seam: it maps a `RunResult` back onto the legacy HTTP envelope, so a
legacy route can keep its exact client-visible behavior while the process is
raised through the controlled runner.

Verbatim details preserved from the original gateways (recorded by static
inspection, quoted from the source):

* queue wait expired        -> 503 "IELTS|TOEFL 并发已满，请稍后重试"
* aggregator dir missing    -> 503 "<DISPLAY> 聚合器未找到（缺少 <script>）；已尝试：<tried>"
* node runtime missing      -> 503 "找不到 node 可执行文件（可用 EXAMDATA_NODE 指定）"
* spawn failed              -> 503 "无法启动 node：<exc>"
* subprocess timeout        -> 504 "<DISPLAY> 聚合器超时（><limit>s）：<cmd>"
* non-zero exit             -> 502 "<cli> 退出码 <rc>：<tail>"   (tail: stderr
  stripped, newlines to spaces, 300 chars, exactly as the legacy gateway built it)
* stdout not valid JSON     -> 502 "<cli> 输出不是合法 JSON"
* ok:false business failure -> HTTP 200, payload passed through unchanged
* success                   -> HTTP 200, payload with `board` defaulted in
  (dict payloads only; a non-dict was wrapped as {"board", "ok", "data"})

Deliberate, *disclosed* staged divergences from the legacy gateway (they are
constants below and are surfaced in every A12 worksheet row that bridges a
node command; Phase B must accept or amend each one):

* stderr is redacted by the runner (rule 9) before it becomes the 502 tail;
* a stdout top-level JSON value that is not an object is classified
  `invalid_json` by the runner (plan 6.4 rule 6), where the legacy gateway
  wrapped non-dict values as {"board", "ok": true, "data": value};
* the runner adds a stdout byte budget: overflow is a staged-only 502;
* component/command whitelist rejections are staged-only 503s;
* a cancelled invocation produced no HTTP response in the legacy gateway
  (the request was gone); `decide()` marks it `cancelled` with no status.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ..runtime.classification import RunnerOutcome

#: stderr tail built exactly as the legacy gateway built it: strip, newlines to
#: spaces, first 300 characters.
TAIL_LIMIT = 300


def legacy_tail(stderr_text: str | None) -> str:
    text = (stderr_text or "").strip().replace("\n", " ")
    return text[:TAIL_LIMIT]


@dataclass(frozen=True)
class BoardProfile:
    """One board's legacy envelope strings (verbatim from its gateway module)."""

    board: str          #: payload `board` token, e.g. "ielts"
    display: str        #: "IELTS" / "TOEFL" as used in user-visible details
    cli: str            #: "ielts-cli" / "toefl-cli" as used in 502 details
    script: str         #: "ielts-cli.mjs" / "toefl-cli.mjs"
    queue_full_detail: str
    runtime_missing_detail: str
    invalid_json_detail: str

    def dir_missing_detail(self, tried: Sequence[str]) -> str:
        return (f"{self.display} 聚合器未找到（缺少 {self.script}）；"
                f"已尝试：{'、'.join(str(p) for p in tried)}")

    def start_failure_detail(self, exc_text: str) -> str:
        return f"无法启动 node：{exc_text}"

    def timeout_detail(self, limit: float, command: str) -> str:
        return f"{self.display} 聚合器超时（>{limit:g}s）：{command}"

    def nonzero_exit_detail(self, returncode: int, tail: str) -> str:
        return f"{self.cli} 退出码 {returncode}：{tail}"


BOARD_PROFILES: dict[str, BoardProfile] = {
    "ielts": BoardProfile(
        board="ielts", display="IELTS", cli="ielts-cli", script="ielts-cli.mjs",
        queue_full_detail="IELTS 并发已满，请稍后重试",
        runtime_missing_detail="找不到 node 可执行文件（可用 EXAMDATA_NODE 指定）",
        invalid_json_detail="ielts-cli 输出不是合法 JSON",
    ),
    "toefl": BoardProfile(
        board="toefl", display="TOEFL", cli="toefl-cli", script="toefl-cli.mjs",
        queue_full_detail="TOEFL 并发已满，请稍后重试",
        runtime_missing_detail="找不到 node 可执行文件（可用 EXAMDATA_NODE 指定）",
        invalid_json_detail="toefl-cli 输出不是合法 JSON",
    ),
}

#: Each entry: what the legacy gateway did, what the staged path does instead,
#: and what Phase B must review. Applied to every bridge row in the registry.
STAGED_DIVERGENCES: tuple[dict[str, str], ...] = (
    {
        "topic": "stderr_redaction",
        "legacy": "the 502 tail carried raw stderr (first 300 chars)",
        "staged": "the runner redacts configured secrets before the tail is built",
        "phase_b": "accept (safety hardening); tail content may differ from legacy "
                   "only when a configured secret appeared in stderr",
    },
    {
        "topic": "non_object_stdout",
        "legacy": "a non-object top-level JSON value was wrapped as "
                  "{\"board\": <board>, \"ok\": true, \"data\": <value>}",
        "staged": "runner rule 6 classifies non-object stdout as invalid_json -> 502",
        "phase_b": "decide: either the CLI always emits an object, or the bridge "
                   "must be extended to carry the raw value",
    },
    {
        "topic": "stdout_budget",
        "legacy": "stdout was read without a byte budget",
        "staged": "stdout over the configured budget is terminated and answered "
                  "with a staged-only 502",
        "phase_b": "accept the bound; review the budget value per component",
    },
    {
        "topic": "whitelist_rejections",
        "legacy": "no component/command whitelist existed",
        "staged": "unknown component/command is a staged-only 503",
        "phase_b": "accept; this can only trigger on a staged configuration bug",
    },
    {
        "topic": "cancellation",
        "legacy": "a cancelled request produced no HTTP response",
        "staged": "decide() returns cancelled with no status code; the Phase B "
                  "adapter re-raises as the framework requires",
        "phase_b": "verify the FastAPI adapter re-raises CancelledError",
    },
)


def decorate_success(board: str, data: Any) -> dict[str, Any]:
    """The legacy success decoration, exactly: dicts get `board` defaulted;
    anything else was wrapped as {"board", "ok": true, "data"}."""
    if isinstance(data, dict):
        data.setdefault("board", board)
        return data
    return {"board": board, "ok": True, "data": data}


def error_body(detail: str) -> dict[str, str]:
    """The FastAPI HTTPException body for any non-200 decision."""
    return {"detail": detail}


@dataclass(frozen=True)
class LegacyResponse:
    """The HTTP result the legacy gateway would have produced."""

    board: str
    status_code: int | None       # None only for `cancelled`
    payload: dict[str, Any] | None = None
    detail: str | None = None
    cancelled: bool = False
    staged_note: str | None = None

    @property
    def ok(self) -> bool:
        return self.status_code == 200

    def body(self) -> dict[str, Any]:
        """The response body: the payload, or {"detail": ...} for errors."""
        if self.status_code == 200:
            assert self.payload is not None
            return self.payload
        assert self.detail is not None
        return error_body(self.detail)


def decide(board: str, result: Any, *, command: str,
           limit: float | None = None, tried: Sequence[str] = ()) -> LegacyResponse:
    """Map one `RunResult` onto the legacy envelope for `board`.

    `result` is duck-typed on the `RunResult` fields the mapping needs
    (``outcome``, ``payload``, ``exit_code``, ``stderr_text``, ``error``).
    `limit` is the effective per-command timeout (the legacy `{limit:g}` in the
    504 detail); `tried` is the aggregator directory candidate list for the
    503 detail.
    """
    profile = BOARD_PROFILES[board]
    outcome = RunnerOutcome.coerce(result.outcome)

    if outcome is RunnerOutcome.OK or outcome is RunnerOutcome.BUSINESS_FAILURE:
        return LegacyResponse(board, 200, payload=decorate_success(board, result.payload))

    if outcome is RunnerOutcome.CANCELLED:
        return LegacyResponse(board, None, cancelled=True,
                              staged_note="legacy produced no response for a cancelled request")

    if outcome is RunnerOutcome.QUEUE_FULL:
        return LegacyResponse(board, 503, detail=profile.queue_full_detail)

    if outcome is RunnerOutcome.MISSING_COMPONENT:
        return LegacyResponse(board, 503, detail=profile.dir_missing_detail(tried))

    if outcome is RunnerOutcome.MISSING_RUNTIME:
        return LegacyResponse(board, 503, detail=profile.runtime_missing_detail)

    if outcome is RunnerOutcome.STARTUP_FAILURE:
        message = (result.error or {}).get("message") or ""
        exc_text = message
        prefix = "could not start "
        if message.startswith(prefix) and ": " in message:
            exc_text = message.split(": ", 1)[1]
        return LegacyResponse(board, 503, detail=profile.start_failure_detail(exc_text))

    if outcome is RunnerOutcome.TIMEOUT:
        if limit is None:
            return LegacyResponse(
                board, 504, detail=profile.timeout_detail(float("inf"), command),
                staged_note="effective timeout not supplied by the caller")
        return LegacyResponse(board, 504, detail=profile.timeout_detail(limit, command))

    if outcome is RunnerOutcome.NONZERO_EXIT:
        return LegacyResponse(
            board, 502,
            detail=profile.nonzero_exit_detail(int(result.exit_code),
                                               legacy_tail(result.stderr_text)))

    if outcome in (RunnerOutcome.INVALID_JSON, RunnerOutcome.MULTIPLE_JSON_VALUES):
        return LegacyResponse(
            board, 502, detail=profile.invalid_json_detail,
            staged_note=("runner rule 6 also rejects non-object stdout, which the "
                         "legacy gateway would have wrapped (see STAGED_DIVERGENCES)"))

    if outcome is RunnerOutcome.OUTPUT_OVERFLOW:
        return LegacyResponse(
            board, 502, detail=f"{profile.cli} 输出超过上限",
            staged_note="staged-only outcome; the legacy gateway had no stdout budget")

    if outcome in (RunnerOutcome.COMPONENT_NOT_ALLOWED, RunnerOutcome.COMMAND_NOT_ALLOWED):
        return LegacyResponse(
            board, 503, detail=f"{profile.display} 聚合器配置被拒绝：{outcome.value}",
            staged_note="staged-only whitelist rejection; no legacy counterpart")

    raise ValueError(f"unmapped runner outcome {outcome!r}")  # pragma: no cover


__all__ = [
    "BOARD_PROFILES",
    "BoardProfile",
    "LegacyResponse",
    "STAGED_DIVERGENCES",
    "TAIL_LIMIT",
    "decide",
    "decorate_success",
    "error_body",
    "legacy_tail",
]
