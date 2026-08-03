"""Tests for the progress spinner used while waiting for a machine's IP address."""

import io
import time

from machine.log import Spinner


class FakeTty(io.StringIO):
    """A StringIO that claims to be a terminal, so the spinner will draw to it."""

    def __init__(self, isatty=True):
        super().__init__()
        self._isatty = isatty

    def isatty(self):
        return self._isatty


def test_draws_frames_when_enabled_and_tty():
    stream = FakeTty()
    with Spinner("Waiting", enabled=True, stream=stream):
        time.sleep(Spinner.INTERVAL * 3)
    written = stream.getvalue()
    assert "Waiting" in written
    assert any(frame in written for frame in Spinner.FRAMES)


def test_erases_itself_on_exit():
    stream = FakeTty()
    with Spinner("Waiting", enabled=True, stream=stream):
        time.sleep(Spinner.INTERVAL * 3)
    # The last thing written must return the cursor to a cleared line, so the
    # message that follows starts on a blank line rather than on top of a frame.
    written = stream.getvalue()
    assert written.endswith("\r")
    assert written.split("\r")[-2].strip() == ""


def test_silent_when_disabled():
    stream = FakeTty()
    with Spinner("Waiting", enabled=False, stream=stream):
        time.sleep(Spinner.INTERVAL * 3)
    assert stream.getvalue() == ""


def test_silent_when_stream_is_not_a_tty():
    """Redirected output and CI logs must not collect animation frames."""
    stream = FakeTty(isatty=False)
    with Spinner("Waiting", enabled=True, stream=stream):
        time.sleep(Spinner.INTERVAL * 3)
    assert stream.getvalue() == ""


def test_stops_and_cleans_up_when_the_body_raises():
    stream = FakeTty()
    try:
        with Spinner("Waiting", enabled=True, stream=stream) as spinner:
            time.sleep(Spinner.INTERVAL * 2)
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert not spinner._thread.is_alive()
    assert stream.getvalue().endswith("\r")
