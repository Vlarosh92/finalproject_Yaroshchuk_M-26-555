import json
import os


class SettingsLoader:
    __instance = None
    __initialized = False
    def __new__(cls, *args, **kwargs):
        """
        Создание синглтона, выбран вариант через __new__
        потому что создавать метакласс имеет смысл для
        применения к многим классам сразу, что
        избыточно для данного задания.
        """
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        """
        Разовая инициализация для сохранения результатов
        конфигурации до следующего вызова reload()
        """
        if self.__initialized:
            return

        self._config = {}
        self._config_load()

        self.__initialized = True

    def _config_load(self) -> None:
        """
        Загружает конфигурацию из
        config.json
        в self._config
        """
        current_file = __file__
        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(current_file))))

        config_path = os.path.join(project_root, "config.json")

        try:
            with open(config_path, encoding="utf-8") as json_file:
                self._config = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
            self._config = {}
    def get(self, key: str, default = None):
        """
        Возвращает данные по ключу key из конфигурации self._config
        """
        return self._config.get(key, default)

    def reload(self) -> None:
        """
        Перезагружает конфигурацию
        """
        self._config = {}
        self._config_load()