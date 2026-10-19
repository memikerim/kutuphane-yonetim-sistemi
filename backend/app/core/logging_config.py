import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Uygulama genelinde standart konsol loglama yapılandırması."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    
    # Kök logger yapılandırması
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Uvicorn ve SQLAlchemy gürültüsünü makul seviyede tut
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

