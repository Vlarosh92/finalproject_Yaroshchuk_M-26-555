import logging
from datetime import datetime, timezone

from valutatrade_hub.core.exceptions import (
    ApiClientsError,
    ApiRequestError,
    DataBaseException,
)
from valutatrade_hub.core.utils import data_time_comprehension
from valutatrade_hub.infra.database import DataBaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import ApiStorageClass

logger = logging.getLogger(SettingsLoader().get(key='logger_name'))


class RatesUpdater:
    @classmethod
    def build(cls, source: str | None = None):
        """
        Фабричный метод создания RatesUpdater для
        заданного источника source
        """
        db = DataBaseManager()
        api_storage = ApiStorageClass(db=db)

        clients = [CoinGeckoClient(), ExchangeRateApiClient()]
        if source is not None:
            clients = [c for c in clients if c.source == source]
            if not clients:
                raise ApiClientsError(field=source)

        return cls(api_clients=clients, storage_class=api_storage)
    """Класс обновления валютных пар"""
    def __init__(self,
                 api_clients: list[BaseApiClient],
                 storage_class: ApiStorageClass
                 ) -> None:
        self._api_clients = api_clients
        self._storage_class = storage_class
        self._tmp_formats = [
            SettingsLoader().get("data_format_local"),
            SettingsLoader().get("data_format_utc")]

    def run_update(self) -> str:
        """Запуск обновления"""
        total_rates = 0
        logger.info("Starting rates update...")
        err_end = False
        new_journal_data = []
        new_rate_data = []
        currency_list = SettingsLoader().get(key = "supported_currency")
        # проходимся по списку api-клиентов
        for client in self._api_clients:
            client_name = client.source
            # начинаем запрос к внешним источникам
            try:
                client_output = client.fetch_rates()
                # так как в формате указываем Z время UTC + 0
                actual_time = (datetime.
                               now(timezone.utc).
                               strftime(self._tmp_formats[1]))
                # обрабатываем
                for k, co in client_output.items():

                    # для заполнения в журнал
                    exchange_rates_output = dict()
                    # для заполнения в текущие данные
                    rates_output = dict()

                    # формируем данные
                    rate = co[0]
                    meta = co[1]
                    time = co[2]


                    pair_name, rate = next(iter(rate.items()))
                    curr, base_curr = pair_name.split("_")
                    # валидация данных
                    if (curr not in currency_list
                        or base_curr not in currency_list):
                        raise ApiRequestError(
                            message = "Invalid currency in response")
                    try:
                        float(rate)
                    except ValueError:
                        raise ApiRequestError(
                            message="Invalid rate in response")

                    # проверяем что данные свежее записанных
                    rate_time = (DataBaseManager().
                                 get_rates(code = curr).
                                 get("updated_at"))

                    if data_time_comprehension(
                            tmp_formats = self._tmp_formats,
                            time_str_1 = time,
                            time_str_2 = rate_time)>0:
                        raise ApiRequestError(
                            message="Некорректное время обновления, "
                                    "записи из базы данных не старее "
                                    "полученных от сайта")

                    # заполняем словарь для журнала
                    exchange_rates_output["id"] = (pair_name+"_"+
                                                   actual_time)
                    exchange_rates_output["from_currency"] = curr
                    exchange_rates_output["to_currency"] = base_curr
                    exchange_rates_output["rate"] = rate
                    exchange_rates_output["timestamp"] = actual_time
                    exchange_rates_output["source"] = client_name
                    exchange_rates_output["meta"] = meta["meta"]
                    # заполняем словарь для среза в rates.json
                    rates_output[pair_name] = { "rate":
                                                    rate,
                                                "updated_at":
                                                    actual_time,
                                                "source":
                                                    client_name}
                    # заполняем данные
                    new_journal_data.append(exchange_rates_output)
                    new_rate_data.append(rates_output)
                    # считаем число обновлений
                    total_rates += 1
                # добавляем запись в логгер
                logger.info(f"Fetching from {client_name}... "
                            f"OK({len(client_output)} rates)")
            except ApiRequestError as e:
                # обрабатываем ошибку
                err_end = True
                logger.error(f"ERROR: Failed to fetch from "
                             f"{client_name}: Network error."
                             f"reason: {e}")
        # формируем данные для среза
        actual_time = (datetime.
                       now(timezone.utc).
                       strftime(self._tmp_formats[1]))
        output_rate_dict = {
            "pairs": {k: v for d in new_rate_data for k, v in d.items()},
            "last_refresh": actual_time
        }
        # так как в формате не указываем Z время местное
        refresh_time = datetime.now().strftime(self._tmp_formats[0])

        if total_rates==0:
            logger.error("ERROR: Failed all updated.")
            raise ApiRequestError(message="Обновить курсы не получилось! "
                                          "Попробуйте через некоторое время "
                                          "выполнить update-rates")
        try:
            # передаем данные в хранилище
            self._storage_class.add_rate_data(output_rate_dict)
            self._storage_class.add_journal_data(new_journal_data)
            logger.info(f"INFO: Writing {total_rates} "
                        f"rates to data/rates.json...")
        except (PermissionError, IndexError, KeyError, DataBaseException):
            logger.error("ERROR: Failed to save rates: Storage error.")


        if err_end:
            return ("Update completed with errors. "
                    "Check logs/parser.log for details.")
        else:
            return (f"Update successful. Total rates "
                    f"updated: {total_rates}. "
                    f"Last refresh: {refresh_time}")

