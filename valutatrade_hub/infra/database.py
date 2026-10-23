import os
import json
import tempfile
from pathlib import Path

from valutatrade_hub.core.exceptions import FileSaveException, FileLoadException
from valutatrade_hub.core.utils import curr_code_union, str_to_datatime
from valutatrade_hub.infra.settings import SettingsLoader



class DataBaseManager:
    """
    Класс работы с базой данных
    Так как класс работает с операциями над
    хранилищами, а не свойствами объекта
    реализован через методы, а не геттеры и сеттеры
    """
    __instance = None
    __initiation = None
    DATA_FMT = "%Y-%m-%dT%H:%M:%S"
    def __new__(cls, *args, **kwargs):
        """Создаем синглтон"""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
    def __init__(self):
        """проводим разовую инициализацию, создаем кеш-словари"""
        if DataBaseManager.__initiation:
            return
        self._dict_rates = {}
        self._dict_users = {}
        self._dict_portfolios = {}
        # устанавливаем заглушку если rates.json отсутствуют
        self.ensure_rates_if_missing()
        DataBaseManager.__initiation = True

    # Методы работы с данными пользователя_____________________________________
    def get_user(self, user_id:str = None) -> dict:
        """Возращаем данные пользователя"""
        if user_id is None:

            loading_data = self._load_data_from(file_name="users")
            for user_data in loading_data:
                user_data["registration_date"] = str_to_datatime(user_data["registration_date"])
            return loading_data

        cached = self._dict_users.get(user_id)
        if cached is not None:
            return cached

        loading_user = self._load_data_from(file_name="users",
                                                       tag="user_id",
                                                       tag_name=user_id)

        loading_user["registration_date"] = str_to_datatime(loading_user["registration_date"])
        self._dict_users[str(loading_user['user_id'])] = loading_user
        return self._dict_users.get(str(user_id), [])

    def save_user(self, new_data: dict) -> None:
        """Сохраняем данные пользователей"""
        self._upsert_list(file_name='users',
                          input_data=new_data)
        # обновляем кеш при записи новых данных
        self._dict_users = {}

    # Методы работы с данными курсов валют_____________________________________
    def get_rates(self, code:str = None)-> dict:
        """Возращаем курсы валют"""
        if code is None:
            return self._load_data_from(file_name="rates")
        cached = self._dict_rates.get(code)
        if cached is not None:
            return cached
        loading_rate = self._load_data_from(file_name="rates")
        pair_code=curr_code_union(code,
            SettingsLoader().get(key="base_currency"))

        self._dict_rates[code] = loading_rate.get('pairs').get(pair_code)
        return self._dict_rates.get(code, [])

    def save_rates(self, input_rates: dict | list):
        """Сохраняем курсы валют"""
        self._overwrite_data_in(file_name="rates",
                                input_data=input_rates)
        # обновляем кеш при записи новых данных
        self._dict_rates = {}

    def save_data_in_journal(self, new_data: list) -> None:
        """Сохраняем данные в журнал exchange_rate.json"""
        self._upsert_list(file_name='exchange_rates',
                          input_data=new_data)

    def get_data_from_journal(self) -> list[dict]:
        """Получаем данные из журнала exchange_rate.json"""
        return self._load_data_from(file_name="exchange_rates")

    # Методы работы с портфелями_______________________________________________
    def get_portfolios(self, user_id:str = None)-> dict:
        """Возращаем портфели пользователя по user_id"""
        if user_id is None:
            return self._load_data_from(file_name="portfolios")

        cached = self._dict_portfolios.get(user_id)
        if cached is not None:
            return cached

        loading_portf = self._load_data_from(file_name="portfolios",
                                                        tag="user_id",
                                                        tag_name=str(user_id))
        self._dict_portfolios[user_id] = loading_portf
        return self._dict_portfolios.get(str(user_id), [])

    def save_portfolios(self, new_data: dict) -> None:
        """Сохраняем данные портфелей"""
        self._upsert_list(file_name='portfolios',
                          input_data=new_data)
        # обновляем кеш при записи новых данных
        self._dict_portfolios = {}

    # Методы работы с данными и файловой системой______________________________
    def _upsert_list(self, input_data: dict | list,
                     file_name: str) -> None:
        """Вставляем новые записи"""
        old_data = self._load_data_from(file_name=file_name)
        if isinstance(input_data, list):
            new_data = [*old_data, *input_data]
        else:
            new_data = [*old_data, input_data]
        self._overwrite_data_in(file_name=file_name,
                                input_data=new_data)

    @staticmethod
    def _root_data_path() -> str:
        """
        устанавливаем директорию хранения данных
        создаем если не существует
        """
        data_dir = SettingsLoader().get("data_path")
        data_dir = Path(__file__).resolve().parent.parent.parent / data_dir
        data_dir.mkdir(exist_ok=True)
        return data_dir

    @staticmethod
    def _load_data_from(file_name: str,
                       tag: str = None,
                       tag_name: str = None) -> dict | list:
        """
        Загружает данные из директории data
        из файла указанном в file_name.
        Допустимо сразу возвратить конкретную запись
        по тэгу и значению
        """
        file_path = os.path.join(
                DataBaseManager._root_data_path(), f"{file_name}.json")
        # Если файла нет возвращаем пустой список
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path,
                    encoding="utf-8") as json_file:
                if tag is not None and tag_name is not None:
                    load_data = json.load(json_file)
                    for ld in load_data:
                        if str(ld[tag]) == tag_name:
                            return ld
                    return []
                else:
                    return json.load(json_file)
        except Exception as e:
            raise FileLoadException(
                name = file_name,
                err = e
            ) from e



    @staticmethod
    def _overwrite_data_in(file_name: str,
                     input_data: dict | list
                     ) -> None:
        """
        Сохраняет input_data в директорию data
        в файл указанном в file_name.
        """
        #Модифицируем для записи с помощью временного файла
        root_dir = DataBaseManager._root_data_path()
        file_path = os.path.join(root_dir, f"{file_name}.json")
        fd, tmp_path = tempfile.mkstemp(suffix=".json",
                                        prefix=f"{file_name}_",
                                        dir=root_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(input_data, tmp_file, ensure_ascii=False, indent=2)
            os.replace(tmp_path, file_path)
        except Exception as e:
            raise FileSaveException(
                name = file_name,
                err = e
            ) from e

    def ensure_rates_if_missing(self) -> None:
        """Если rates.json отсутствует, создаёт заглушку"""
        path = Path(self._root_data_path()) / "rates.json"
        if not path.exists():
            stub_data = {
                    "pairs":{
                        "EUR_USD": {
                            "rate": 1.0786,
                            "updated_at": "2025-10-09T10:30:00"
                        },
                        "BTC_USD": {
                            "rate": 59337.21,
                            "updated_at": "2025-10-09T10:29:42"
                        },
                        "RUB_USD": {
                            "rate": 0.01016,
                            "updated_at": "2025-10-09T10:31:12"
                        },
                        "ETH_USD": {
                            "rate": 3720.00,
                            "updated_at": "2025-10-09T10:35:00"
                        }
                    },
                    "source": "ParserService",
                    "last_refresh": "2025-10-09T10:35:00"
                }
            self.save_rates(stub_data)