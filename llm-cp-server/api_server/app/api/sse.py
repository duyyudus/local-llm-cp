from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

KEEPALIVE_SECONDS = 15.0
KEEPALIVE = ": keepalive\n\n"


def sse_event(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def sse_response(generator: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
