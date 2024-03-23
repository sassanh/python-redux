# ruff: noqa: D100, D101, D102, D103, D104, D107
import pytest
from _pytest.outcomes import Failed
from tenacity import stop_after_delay

from redux_pytest.fixtures.event_loop import LoopThread
from redux_pytest.fixtures.wait_for import WaitFor


def test_asyncheonous(
    wait_for: WaitFor,
    event_loop: LoopThread,
) -> None:
    async def runner() -> None:
        @wait_for(run_async=True, timeout=1)
        def check() -> None:
            pytest.fail('Never')

        with pytest.raises(Failed, match=r'^Never$'):
            await check()

        event_loop.stop()

    event_loop.create_task(runner())


def test_with_stop(wait_for: WaitFor) -> None:
    @wait_for(stop=stop_after_delay(0.1))
    def check() -> None:
        pytest.fail('Never')

    with pytest.raises(Failed, match=r'^Never$'):
        check()


def test_with_timeout(wait_for: WaitFor) -> None:
    @wait_for(timeout=0.1)
    def check() -> None:
        pytest.fail('Never')

    with pytest.raises(Failed, match=r'^Never$'):
        check()
