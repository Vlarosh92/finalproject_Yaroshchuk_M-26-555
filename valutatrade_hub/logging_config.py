import logging
import os
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

from valutatrade_hub.core.utils import root_path


def setup_logger(log_dir: str,
                 log_file_name: str = "app.log",
                 name: str = "logger_1",
                 debug_mode: bool = False) -> logging.Logger | None:
    """
    Функция для настройки логгера.
    Пишет в файл в log_dir/log_file_name
    """
    # проверим что данные для создания логгера не пусты
    if not log_dir or not log_file_name:
        return None

    full_log_dir = root_path() / log_dir

    os.makedirs(full_log_dir, exist_ok=True)
    # формат записи лога
    log_format = logging.Formatter(
        "%(levelname)-8s %(asctime)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )


    logger = logging.getLogger(name)

    logger.handlers.clear()
    logger.propagate = False

    level = logging.DEBUG if debug_mode else logging.INFO
    logger.setLevel(level)

    # проводим ротацию файлов (до 3) при достижении размера до 1 Мб
    file_handler = RotatingFileHandler(
        os.path.join(full_log_dir, log_file_name),
        maxBytes=1000000,
        backupCount=3
    )
    # обработчик для вывода в файл
    file_handler.setLevel(level)
    file_handler.setFormatter(log_format)

    # добавляем обработчика
    logger.addHandler(file_handler)

    return logger


@contextmanager
def enable_console_logging(logger_name: str = "logger_1"):
    """
    Временно добавляет вывод в консоль для указанного логгера.
    После выхода из контекста консоль отключается.
    """
    logger = logging.getLogger(logger_name)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    log_format = logging.Formatter(
        "%(levelname)-8s %(asctime)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    console_handler.setFormatter(log_format)

    logger.addHandler(console_handler)

    try:
        yield
    finally:
        logger.removeHandler(console_handler)