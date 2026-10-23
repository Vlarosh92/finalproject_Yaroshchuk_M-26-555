from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import (
    CurrencyExistError,
    CurrencyLenError,
    CurrencyNotFoundError,
    CurrencyRegisterError,
    CurrencySpaceFoundError,
    CurrencyTypeError,
)


class Currency(ABC):
    def __init__(self, name: str, code: str):
        """
        Инициализация и валидация
        данных наследников абстрактного класса
        """
        if not isinstance(name, str) or not name.strip():
            raise CurrencyExistError(field = f"Имя валюты ({name})")
        self.name = name.strip()


        if not isinstance(code, str):
            raise CurrencyTypeError(field = f"Код валюты ({code})")
        if " " in code:
            raise CurrencySpaceFoundError(field = f"Код валюты ({code})")
        if len(code) < 2 or len(code) > 5:
            raise CurrencyLenError(field = f"Код валюты ({code})")
        if code != code.upper():
            raise CurrencyRegisterError(field = "Код валюты")
        self.code = code
    @abstractmethod
    def get_display_info(self) -> str:
        """Получить информацию о валюте"""
        pass

class FiatCurrency(Currency):
    def __init__(self, name: str,
                 code: str,
                 issuing_country: str):
        """
        Инициализация экземпляра фиатной валюты,
        с полем страны эмиссии
        """
        super().__init__(name = name, code = code)
        self.issuing_country = issuing_country
    def get_display_info(self) -> str:
        """Получить информацию о фиатной валюте"""
        return (f"[FIAT] {self.code} — {self.name} "
                f"(Issuing: {self.issuing_country})")

class CryptoCurrency(Currency):
    def __init__(self, name: str,
                 code: str,
                 algorithm: str,
                 market_cap: float):
        """
        Инициализация экземпляра крипто валюты,
        с полем алгоритма, и рыночной капитализации
        """
        super().__init__(name = name, code = code)
        self.algorithm = algorithm
        self.market_cap = market_cap
    def get_display_info(self) -> str:
        """Получить информацию о крипто валюте"""
        return (f"[CRYPTO] {self.code} — {self.name} "
                f"(Algo: {self.algorithm}, MCAP: {self.market_cap})")


currency_factory = {
        "RUB": lambda: FiatCurrency("Russian rubble", "RUB", "Russian Federation"),
        "USD": lambda: FiatCurrency("US Dollar", "USD", "United States"),
        "EUR": lambda: FiatCurrency("EURO", "EUR", "Euro Zone"),
        "BTC": lambda: CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.7 * (10 ** 12)),
        "ETH": lambda: CryptoCurrency("Ethereum", "ETH", "Ethash", 3.1 * (10 ** 11)),
    }
def get_currency(code: str) -> Currency:
    """
    Функция-фабрика лениво создающая
    экземпляр класса по словарю
    """
    factory = currency_factory.get(code)
    if factory is None:
        raise CurrencyNotFoundError(field = code)
    return factory()