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


def get_currency(code: str,
                 curr_data: dict) -> Currency:
    """
    Функция-фабрика лениво создающая
    экземпляр класса по словарю из config.json
    """

    if curr_data.get("type") == "fiat":
        return FiatCurrency(name = curr_data.get("name"),
                            code = code,
                            issuing_country = curr_data
                            .get("issuing_country"))
    elif curr_data.get("type") == "crypto":
        return CryptoCurrency(name = curr_data.get("name"),
                            code = code,
                            algorithm = curr_data
                                .get("algorithm"),
                            market_cap = curr_data
                                .get("market_cap"))
    else:
        raise CurrencyNotFoundError(field = code)
