from collections import deque
from datetime import datetime, timezone
import logging
import sys
import uuid
from typing import Any

# Son 200 log kaydını hafızada tutan dairesel arabellek (ring buffer)
_audit_logs: deque[dict[str, Any]] = deque(maxlen=200)


class InMemoryAuditLogHandler(logging.Handler):
    """Sistemde gerçekleşen işlemleri hafızada tutarak Admin Paneli'ne servis eden handler."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Yalnızca uygulama içi logları yakala (üçüncü parti kütüphanelerin gürültüsünü filtrele)
            if not record.name.startswith("app."):
                return

            category = "SYSTEM"
            msg = record.getMessage()
            msg_lower = msg.lower()

            if record.name.startswith("app.modules.auth"):
                category = "AUTH"
            elif record.name.startswith("app.modules.borrowing"):
                if "rezervasyon" in msg_lower or "reservation" in msg_lower:
                    category = "RESERVATION"
                elif "ceza" in msg_lower or "penalty" in msg_lower or "overdue" in msg_lower:
                    category = "PENALTY"
                else:
                    category = "BORROWING"
            elif record.name.startswith("app.modules.review"):
                category = "REVIEW"
            elif record.name.startswith("app.modules.catalog"):
                category = "CATALOG"

            log_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "level": record.levelname,
                "message": msg,
            }
            _audit_logs.append(log_entry)
        except Exception:
            self.handleError(record)


_audit_handler = InMemoryAuditLogHandler()


def setup_logging(level: int = logging.INFO) -> None:
    """Uygulama genelinde standart konsol ve hafıza-içi loglama yapılandırması."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"

    # Kök logger yapılandırması
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            _audit_handler,
        ],
        force=True,
    )

    # Uvicorn ve SQLAlchemy gürültüsünü makul seviyede tut
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Başlangıç log kaydı
    if not _audit_logs:
        add_system_log("SYSTEM", "INFO", "Kütüphane Yönetim Sistemi servisleri başlatıldı.")


def get_system_logs(
    limit: int = 100,
    category: str | None = None,
    level: str | None = None,
) -> list[dict[str, Any]]:
    """Son işlemleri en yeniden eskiye doğru filtreleyerek listeler."""
    logs = list(reversed(_audit_logs))
    if category and category.upper() not in ("ALL", "TÜMÜ", "TUMU"):
        logs = [log for log in logs if log["category"].upper() == category.upper()]
    if level and level.upper() not in ("ALL", "TÜMÜ", "TUMU"):
        logs = [log for log in logs if log["level"].upper() == level.upper()]
    return logs[:limit]


def add_system_log(category: str, level: str, message: str) -> None:
    """Doğrudan audit log ekleme yardımcısı."""
    _audit_logs.append({
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category.upper(),
        "level": level.upper(),
        "message": message,
    })
