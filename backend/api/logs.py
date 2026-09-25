"""Keep stream tickets out of the server logs.

The camera feed and the live events are opened with a short-lived ticket in
the URL (?ticket=...), because browsers can't send headers on <img> and
WebSocket requests. uvicorn logs request URLs: the access log for
/video-feed and its error logger for WebSocket handshakes (/ws/events).
This filter replaces the ticket value with [redacted] in those records.
"""
import logging
import re

TICKET = re.compile(r"(ticket=)[^&\s\"']+", re.IGNORECASE)
LOGGERS = ("uvicorn.access", "uvicorn.error")


def redact(value):
    return TICKET.sub(r"\1[redacted]", value) if isinstance(value, str) else value


class RedactTickets(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact(v) for k, v in record.args.items()}
        return True


def install():
    """Attach the filter to uvicorn's loggers. Logger filters stay in place
    when uvicorn (re)configures logging, because it configures logging
    before it imports the app."""
    for name in LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTickets) for f in logger.filters):
            logger.addFilter(RedactTickets())
