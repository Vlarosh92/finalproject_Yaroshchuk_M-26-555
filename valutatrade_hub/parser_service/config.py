import os
from dataclasses import dataclass

from valutatrade_hub.core.utils import root_path
from valutatrade_hub.infra.settings import SettingsLoader


@dataclass
class ParserConfig:
    """
    Файл конфигурации интернет парсера.
    """
    # читаем ключ из переменной окружения
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY")
    if EXCHANGERATE_API_KEY is None:
        # как альтернатива читаем ключ из файла .env
        # добавленного в .gitignore
        key_path = os.path.join(str(root_path()), ".env")
        EXCHANGERATE_API_KEY = ""
        if os.path.exists(key_path):
            with open(key_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        EXCHANGERATE_API_KEY = value.strip()

    COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL = "https://v6.exchangerate-api.com/v6"

    # Списки валют
    sl = SettingsLoader()
    BASE_CURRENCY = sl.get(key = "base_currency")
    DATA_FORMATS = [
            sl.get("data_format_local"),
            sl.get("data_format_utc")]
    FIAT_CURRENCIES = ("EUR", "RUB")
    CRYPTO_CURRENCIES = ("BTC", "ETH")
    CRYPTO_ID_MAP = {
        "BTC": "bitcoin",
        "ETH": "ethereum"
    }
    REVERSE_CRYPTO_ID_MAP = {
        "bitcoin": "BTC",
        "ethereum": "ETH"
    }

    # Пути
    RATES_FILE_PATH = "data/rates.json"
    HISTORY_FILE_PATH = "data/exchange_rates.json"

    # Сетевые параметры
    REQUEST_TIMEOUT = 10