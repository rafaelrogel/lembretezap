# backend/logger.py
import logging
import json
import sys
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        
        # Inject trace_id if available (Zappelin/Zapista correlation)
        try:
            from zapista.utils.logging_config import get_trace_id
            log_entry["trace_id"] = get_trace_id()
        except ImportError:
            pass

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Standard logging's 'extra' dictionary keys are added to the record object.
        # We also support a dedicated 'extra' key in the record for our structured logging.
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry.update(record.extra)
        
        return json.dumps(log_entry, ensure_ascii=False)

def get_logger(name: str) -> logging.Logger:
    """Get a JSON-formatted logger for a module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
