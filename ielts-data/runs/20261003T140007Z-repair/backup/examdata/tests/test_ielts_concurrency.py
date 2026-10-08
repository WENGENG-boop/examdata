"""Offline evidence for capacity, saturation, cancellation and process reaping."""
import asyncio
import json

import pytest
from fastapi import HTTPException
from examdata.api import ielts


def test_capacity_and_cancelled_waiter_do_not_leak_slot(monkeypatch):
    monkeypatch.setenv("EXAMDATA_IELTS_MAX_CONCURRENT", "2")
    monkeypatch.setenv("EXAMDATA_IELTS_QUEUE_TIMEOUT", "0.02")

    async def scenario():
        active = 0
        maximum = 0
        ready = asyncio.Event()
        release = asyncio.Event()

        async def slow(*args, **kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                ready.set()
            try:
                await release.wait()
                return {"ok": True}
            finally:
                active -= 1

        monkeypatch.setattr(ielts, "_run_process", slow)
        holders = [asyncio.create_task(ielts._run("unused")) for _ in range(2)]
        await asyncio.wait_for(ready.wait(), 1)
        waiting = asyncio.create_task(ielts._run("unused"))
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        with pytest.raises(HTTPException) as error:
            await ielts._run("unused")
        assert error.value.status_code == 503
        assert active == maximum == 2
        release.set()
        assert all(r["ok"] for r in await asyncio.gather(*holders))
        assert (await ielts._run("unused"))["ok"]
        assert active == 0 and maximum == 2

    asyncio.run(scenario())


def test_cancelled_running_request_kills_and_waits_for_child(monkeypatch, tmp_path):
    (tmp_path / "ielts-cli.mjs").write_text("", encoding="utf-8")
    monkeypatch.setenv("EXAMDATA_IELTS_DIR", str(tmp_path))
    monkeypatch.setenv("EXAMDATA_NODE", "offline-test-node")

    async def scenario():
        entered = asyncio.Event()

        class Process:
            killed = False
            reaped = False
            returncode = 0

            async def communicate(self):
                entered.set()
                await asyncio.Event().wait()
                return json.dumps({"ok": True}).encode(), b""

            def kill(self):
                self.killed = True

            async def wait(self):
                self.reaped = True

        child = Process()

        async def spawn(*args, **kwargs):
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(ielts._run("unused"))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert child.killed and child.reaped

    asyncio.run(scenario())
