import json
import logging
import logging.handlers
from pathlib import Path
from app.config.settings import settings, PROJECT_ROOT


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k in ("args", "asctime", "created", "exc_info", "exc_text", "filename",
                     "funcName", "levelname", "levelno", "lineno", "message", "module",
                     "msecs", "msg", "name", "pathname", "process", "processName",
                     "relativeCreated", "stack_info", "thread", "threadName", "taskName"):
                continue
            payload[k] = v
        return json.dumps(payload, ensure_ascii=False, default=str)


_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    fh = logging.handlers.RotatingFileHandler(
        logs_dir / "bot.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(JsonFormatter())
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(sh)

    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
