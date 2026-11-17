"""Watches small cameras on behalf of the dashboards.

An ESP32 can only feed one viewer, so the server makes that one connection and passes the
pictures and sound on to every dashboard watching. Nothing is fetched while nobody watches:
the connection is dropped a few seconds after the last viewer leaves.
"""
import asyncio
import contextlib
import logging
import re
import struct
from typing import Callable

import httpx

log = logging.getLogger("jarvis.relay")

LINGER_S = 10         # keep the camera connection this long after the last viewer leaves
RETRY_S = 3           # wait between attempts to reach a camera
MAX_HEADER = 4096
MAX_FRAME = 2_000_000
_LENGTH = re.compile(rb"content-length:\s*(\d+)", re.I)


def wav_header(rate: int, channels: int, bits: int) -> bytes:
    """The start of a WAV file that never ends, so a browser plays it as it arrives."""
    data_size = 0x7FFF0000
    block = channels * bits // 8
    return (b"RIFF" + struct.pack("<I", data_size + 36) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * block, block, bits)
            + b"data" + struct.pack("<I", data_size))


class Feed:
    """One stream from one camera, shared by everyone watching it."""

    def __init__(self, label: str, url: Callable[[], str | None], http: httpx.AsyncClient):
        self.label = label
        self.url = url
        self.http = http
        self.viewers = 0
        self.task: asyncio.Task | None = None
        self.connected = False

    @contextlib.asynccontextmanager
    async def watching(self):
        self.viewers += 1
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run())
        try:
            yield self
        finally:
            self.viewers -= 1

    def _unwatched_for(self, since: list) -> float:
        """Seconds nobody has been watching (since is a one-item list holding the start time)."""
        loop = asyncio.get_running_loop()
        if self.viewers > 0:
            since[0] = None
            return 0.0
        if since[0] is None:
            since[0] = loop.time()
        return loop.time() - since[0]

    async def _run(self) -> None:
        since = [None]
        while self._unwatched_for(since) < LINGER_S:
            url = self.url()
            if url:
                try:
                    async with self.http.stream("GET", url) as r:
                        if r.status_code != 200:
                            log.warning("%s: camera answered %s", self.label, r.status_code)
                        else:
                            self.connected = True
                            log.info("%s: connected", self.label)
                            await self._read(r.aiter_bytes(), since)
                except (httpx.HTTPError, OSError) as e:
                    log.warning("%s: %s", self.label, e.__class__.__name__)
                finally:
                    self.connected = False
                if self._unwatched_for(since) >= LINGER_S:
                    break
            await asyncio.sleep(RETRY_S)
        log.info("%s: nobody watching, disconnected", self.label)

    async def _read(self, chunks, since: list) -> None:
        raise NotImplementedError


class VideoFeed(Feed):
    """An MJPEG stream: keeps the newest picture; each viewer always gets the latest one."""

    def __init__(self, *args):
        super().__init__(*args)
        self.frame: bytes | None = None
        self.seq = 0
        self.changed = asyncio.Condition()

    async def _read(self, chunks, since: list) -> None:
        buf = bytearray()
        async for chunk in chunks:
            buf += chunk
            while True:
                head_end = buf.find(b"\r\n\r\n")
                if head_end < 0:
                    if len(buf) > MAX_HEADER:
                        del buf[:-4]                  # junk: keep looking for the next part
                    break
                m = _LENGTH.search(bytes(buf[:head_end]))
                if not m or int(m.group(1)) > MAX_FRAME:
                    del buf[:head_end + 4]            # not a picture part: skip it
                    continue
                start, size = head_end + 4, int(m.group(1))
                if len(buf) < start + size:
                    break
                frame = bytes(buf[start:start + size])
                del buf[:start + size]
                async with self.changed:
                    self.frame, self.seq = frame, self.seq + 1
                    self.changed.notify_all()
            if self._unwatched_for(since) >= LINGER_S:
                return

    async def frames(self):
        """Pictures for one viewer, newest first, skipping any it was too slow to take."""
        seen = 0
        while True:
            async with self.changed:
                await self.changed.wait_for(lambda: self.seq != seen and self.frame is not None)
                seen, frame = self.seq, self.frame
            yield frame


class AudioFeed(Feed):
    """A WAV stream: passes the sound on to each listener, starting with its own WAV header."""

    def __init__(self, *args):
        super().__init__(*args)
        self.format = (16000, 1, 16)                  # rate, channels, bits until the camera says
        self.ready = asyncio.Event()
        self.listeners: set[asyncio.Queue] = set()

    async def _read(self, chunks, since: list) -> None:
        header = b""
        spare = b""
        async for chunk in chunks:
            if len(header) < 44:
                need = 44 - len(header)
                header, chunk = header + chunk[:need], chunk[need:]
                if len(header) < 44:
                    continue
                if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                    channels, rate = struct.unpack_from("<HI", header, 22)
                    (bits,) = struct.unpack_from("<H", header, 34)
                    self.format = (rate, channels, bits)
                self.ready.set()
            data = spare + chunk
            block = self.format[1] * self.format[2] // 8
            whole = len(data) - len(data) % block         # never split a sample between listeners
            data, spare = data[:whole], data[whole:]
            if data:
                for q in list(self.listeners):
                    if q.full():
                        q.get_nowait()                    # a slow listener skips ahead, not behind
                    q.put_nowait(data)
            if self._unwatched_for(since) >= LINGER_S:
                return

    async def chunks(self):
        """A complete never-ending WAV file for one listener."""
        q: asyncio.Queue = asyncio.Queue(maxsize=48)
        self.listeners.add(q)
        try:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.ready.wait(), 8)
            yield wav_header(*self.format)
            while True:
                yield await q.get()
        finally:
            self.listeners.discard(q)


class Relays:
    """The feeds for every relayed camera, created when first watched."""

    def __init__(self, house):
        self.house = house
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(10, read=20))
        self.feeds: dict[tuple[str, str], Feed] = {}

    def _source(self, node: str, kind: str) -> Callable[[], str | None]:
        def url() -> str | None:
            cam = self.house.cameras.get(node)
            return cam.get(kind) if cam and cam["relay"] else None
        return url

    def feed(self, node: str, kind: str) -> Feed:
        """kind is "video" or "audio". KeyError if that camera has no such relayed stream."""
        if not self._source(node, kind)():
            raise KeyError(node)
        key = (node, kind)
        if key not in self.feeds:
            cls = VideoFeed if kind == "video" else AudioFeed
            self.feeds[key] = cls(f"{node} {kind}", self._source(node, kind), self.http)
        return self.feeds[key]

    def snapshot_url(self, node: str) -> str | None:
        cam = self.house.cameras.get(node)
        return cam["video"].replace("/stream.mjpg", "/snapshot.jpg", 1) if cam else None
