from valutatrade_hub.infra.database import DataBaseManager


class ApiStorageClass:
    """Класс записи и чтения журнала курса валют"""
    def __init__(self,
                 db: DataBaseManager) -> None:
        self._db = db

    def add_rate_data(self, input_rate_data:dict) -> None:
        """Записываем актуальные данные в rates.json"""
        data_rate = self._db.get_rates()
        for k, v in input_rate_data["pairs"].items():
            data_rate["pairs"][k] = v
        data_rate["last_refresh"] = input_rate_data["last_refresh"]
        # добавляем запись через временный файл через _db.save_rates
        self._db.save_rates(data_rate)

    def add_journal_data(self, input_journal_data:list[dict]) -> None:
        """Записываем актуальные данные в журнал exchanges_rates.json"""
        self._db.save_data_in_journal(input_journal_data)

    def read_data_from_journal(self, num_req: int = 1,
                               last: bool = True)-> list[dict]:
        """Читаем последние num_req записей из журнала exchanges_rates.json"""
        load_data = self._db.get_data_from_journal()

        if last:
            return load_data[-num_req:]
        else:
            return load_data[:num_req]
