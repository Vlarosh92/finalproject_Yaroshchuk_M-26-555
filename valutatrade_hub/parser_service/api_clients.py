from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import curr_code_union, status_code_api_err
from valutatrade_hub.parser_service.config import ParserConfig as Con


class BaseApiClient(ABC):
    source = ""
    @abstractmethod
    def fetch_rates(self) -> dict:
        pass

class CoinGeckoClient(BaseApiClient):
    """Клиент для парсинга курса из CoinGecko"""
    source = "CoinGecko"
    def fetch_rates(self) -> dict:
        """Класс получения курса криптовалют"""
        # формируем url
        url = Con.COINGECKO_URL

        params = {
            "ids": ",".join(Con.CRYPTO_ID_MAP[crc] for crc in Con.CRYPTO_CURRENCIES),
            "vs_currencies": Con.BASE_CURRENCY
        }
        try:
            # делаем запрос
            response = requests.get(url, params=params, timeout=Con.REQUEST_TIMEOUT)
            # проверяем статус
            status_code = response.status_code
            if not (200 <= status_code < 300):
                message = status_code_api_err(status_code=status_code)
                raise ApiRequestError(message=message)
            response.raise_for_status()
            # получаем мета-данные
            request_ms = int(response.elapsed.total_seconds() * 1000)
            status_code = response.status_code
            etag = response.headers.get("ETag")
            json_data = response.json()
            input_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            # собираем ответ в список, делаем базовое форматирование
            output_dict = dict()
            for k,v in json_data.items():
                response_rate_data = {
                    (Con.REVERSE_CRYPTO_ID_MAP[k] +
                     "_" + Con.BASE_CURRENCY) : v[Con.BASE_CURRENCY.lower()]
                }
                response_meta_data = {"meta":
                    {
                    "raw_id": k,
                    "request_ms": request_ms,
                    "status_code": status_code,
                    "etag": etag
                    }
                }
                output_dict[k] = (response_rate_data,
                                    response_meta_data,
                                    input_time)

            return output_dict
        except (Timeout, ConnectionError, HTTPError, RequestException) as e:
            raise ApiRequestError(reason=f"{e}")

class ExchangeRateApiClient(BaseApiClient):
    """Клиент для парсинга курса из ExchangeRateApi"""
    source = "ExchangeRateApi"
    def fetch_rates(self) -> dict:
        """Класс получения курса фиатных валют"""
        if not Con.EXCHANGERATE_API_KEY:
            raise ApiRequestError(reason="Не задан API-ключ EXCHANGERATE_API_KEY")
        # формируем url

        url = (f"{Con.EXCHANGERATE_API_URL}"
               f"/{Con.EXCHANGERATE_API_KEY}"
               f"/latest/{Con.BASE_CURRENCY}")
        try:
            # делаем запрос
            response = requests.get(url, timeout=Con.REQUEST_TIMEOUT)
            # проверяем статус
            status_code = response.status_code

            if not (200 <= status_code < 300):
                message = status_code_api_err(status_code = status_code)
                raise ApiRequestError(message = message)

            response.raise_for_status()
            # получаем мета-данные
            request_ms = int(response.elapsed.total_seconds() * 1000)
            status_code = response.status_code
            etag = response.headers.get("ETag")
            json_data = response.json()
            input_data = json_data['conversion_rates']
            input_time = parsedate_to_datetime(json_data['time_last_update_utc'])
            input_time = input_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            output_dict = dict()
            # собираем ответ в список, делаем базовое форматирование
            for fiat in Con.FIAT_CURRENCIES:
                response_rate_data = {
                    curr_code_union(fiat, Con.BASE_CURRENCY): 1 / input_data[fiat]
                }
                response_meta_data = {"meta":
                    {
                        "raw_id": fiat,
                        "request_ms": request_ms,
                        "status_code": status_code,
                        "etag": etag
                    }
                }
                output_dict[fiat] = (response_rate_data,
                                    response_meta_data,
                                    input_time)

            return output_dict
        except (Timeout, ConnectionError, HTTPError, RequestException) as e:
            raise ApiRequestError(reason=f"{e}")