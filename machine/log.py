import itertools
import sys
import threading
import time


class Spinner:
    """A progress indicator for the waits that would otherwise look like a hang.

    Used as a context manager around a polling loop:

        with Spinner("Waiting for machine IP address", enabled=progress):
            while not ip_address:
                ...

    The frames are written to stderr (like every other status message here) and
    erased on exit, so stdout stays clean for `--output json` and for callers
    that pipe the result somewhere. It is inert unless explicitly enabled *and*
    stderr is a terminal, so redirected output and CI logs never collect
    animation frames.
    """

    FRAMES = "|/-\\"
    INTERVAL = 0.1

    def __init__(self, message: str, enabled: bool = True, stream=None):
        self._message = message
        self._stream = stream if stream is not None else sys.stderr
        self._enabled = enabled and self._stream.isatty()
        self._stop = threading.Event()
        self._thread = None
        self._width = 0

    def _run(self):
        start = time.monotonic()
        for frame in itertools.cycle(self.FRAMES):
            if self._stop.is_set():
                return
            elapsed = int(time.monotonic() - start)
            line = f"{frame} {self._message} ({elapsed}s)"
            self._width = max(self._width, len(line))
            self._stream.write("\r" + line.ljust(self._width))
            self._stream.flush()
            self._stop.wait(self.INTERVAL)

    def _erase(self):
        if self._width:
            self._stream.write("\r" + " " * self._width + "\r")
            self._stream.flush()

    def __enter__(self):
        if self._enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._thread:
            self._stop.set()
            self._thread.join()
            self._erase()
        return False


def fatal_error(s: str):
    print(s, file=sys.stderr)
    sys.exit(1)


def debug(s: str):
    print(s, file=sys.stderr)


def info(s: str):
    print(s, file=sys.stderr)


def output(s: str):
    print(s)
