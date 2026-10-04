from __future__ import annotations

import logging

from common.config import Settings


def setup_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # asyncssh logs every channel open/close at INFO.
    logging.getLogger("asyncssh").setLevel(logging.WARNING)
