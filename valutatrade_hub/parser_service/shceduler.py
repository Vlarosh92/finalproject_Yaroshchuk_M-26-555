import logging
import threading

from typing import Callable, Any

from valutatrade_hub.infra.settings import SettingsLoader

logger = logging.getLogger(SettingsLoader().get(key='logger_name'))
class Scheduler:
    """Класс для фонового обновления курсов валют"""
    def __init__(self, interval_seconds: float = None,
                 updater: Callable[[], Any] = None):
        self.interval_seconds = interval_seconds
        self._updater = updater
        self._timer = None
        self._running = False
    def start(self):
        """Старт планировщика"""
        if self._running:
            return
        self._running = True
        logger.info("Start scheduler")
        self._schedule_next()
    def _schedule_next(self):
        """Вызов по таймеру"""
        if not self._running:
            return

        self._timer = threading.Timer(self.interval_seconds, self._run)
        self._timer.start()

    def _run(self):
        """Обновление по функции"""
        if self.updater is None:
            logger.error("Scheduler: updater не задан, "
                                            "пропускаем цикл")
        try:
            self._updater()
        except (TypeError, ValueError) as e:
            logger.error("Scheduler: ошибка вызова updater")
        except Exception as e:
            logger.error(f"Scheduler: ошибка при "
                                     f"выполнении updater: {e}")
        finally:
            if self._running:
                self._schedule_next()

    def stop(self):
        """Остановка работы"""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
            logger.info("Stop scheduler")
    @property
    def running(self):
        """Возвращает статус работы"""
        return self._running
    @property
    def updater(self) -> Callable:
        """Возращает фоновую функцию"""
        return self._updater
    @updater.setter
    def updater(self, fun: Callable):
        """Принимает фоновую функцию"""
        self._updater = fun