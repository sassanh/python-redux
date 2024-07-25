# ruff: noqa: D100, D101, D102, D103, D104, D107
import pytest
from _pytest.outcomes import Failed
from tenacity import RetryError, stop_after_delay
from tenacity.wait import wait_fixed

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


def test_arguments(wait_for: WaitFor) -> None:
    @wait_for(timeout=0.1, wait=wait_fixed(0.05))
    def check(min_value: int) -> None:
        nonlocal counter
        counter += 1
        assert counter >= min_value

    counter = 0
    check(1)

    counter = 0
    with pytest.raises(RetryError):
        check(4)

    counter = 0
    check(min_value=1)

    counter = 0
    with pytest.raises(RetryError):
        check(min_value=4)


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
