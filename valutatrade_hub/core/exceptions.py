# ==================================================================================
# Обработка пользовательских ошибках
# ==================================================================================
class DomainError(Exception):
    """
    Общий предок для всех ошибок предметной области кроме
    ошибок парсера консольной строки
    """
    pass

# ==================================================================================
# Ошибки связанные с бизнес-логикой
class TradeException(DomainError):
    """Исключения ограничений валюты"""
    def __init__(self, message: str):
        super().__init__(message)
class InsufficientFundsError(TradeException):
    """Исключения при недостатке средств"""
    def __init__(self, available: float,
                       required: float,
                       code: str
                       ):
        super().__init__(f"Недостаточно средств: доступно {available} {code}, требуется {required} {code}")
class RatesExistValidationException(TradeException):
    """Исключения при неудачном получении курса"""
    def __init__(self, field_currency_1: str,
                 field_currency_2: str):
        super().__init__(f"Не удалось получить курс для "
                         f"{field_currency_1}->{field_currency_2}")
class WalletsException(TradeException):
    """Исключения при ошибках связанных с кошельками"""
    def __init__(self, message: str):
        super().__init__(f"{message}")
# ==================================================================================
# Ошибки связанные с парсингом данных из сети
class ApiError(DomainError):
    """Исключения ошибок связанных с API-клиентами"""
    def __init__(self, message: str):
        super().__init__(message)
class ApiRequestError(ApiError):
    """Исключения при обращении к API"""
    def __init__(self,
                 reason: str = "",
                 message: str = ""
                 ):
        if message:
            super().__init__(message)
        else:
            super().__init__(f"Ошибка при обращении к внешнему API: {reason}.\n "
                         f"Повторите попытку позже.")
class ApiClientsError(ApiError):
    """Исключения при некорректном источнике API"""
    def __init__(self,  field: str,):
        super().__init__(f"Такого API-клиента {field} не существует,"
                         f" проверьте допустимые имена в README.md")


# ==================================================================================
# Ошибки связанные с валютами
class CurrencyError(DomainError):
    """Исключения ограничений валюты"""
    def __init__(self, message: str):
        super().__init__(message)
class CurrencyExistError(CurrencyError):
    """Исключения на пустую строку валюты"""
    def __init__(self, field: str):
        super().__init__(f"{field}: должно быть непустой строкой")
class CurrencyTypeError(CurrencyError):
    """Исключения на тип валюты"""
    def __init__(self, field: str):
        super().__init__(f"{field}: должна быть строкой")
class CurrencyLenError(CurrencyError):
    """Исключения на длину валюты"""
    def __init__(self, field: str):
        super().__init__(f"{field}: длина должна быть от 2 до 5 символов")
class CurrencyRegisterError(CurrencyError):
    """Исключения на регистр валюты"""
    def __init__(self, field: str):
        super().__init__(f"{field}: должен быть в верхнем регистре")
class CurrencyNotFoundError(CurrencyError):
    """Исключения при неизвестной валюте"""
    def __init__(self, field: str):
        super().__init__(f"Неизвестная валюта '{field}'")

class CurrencySpaceFoundError(CurrencyError):
    """Исключения при пробелах в коде валюты"""
    def __init__(self, field: str):
        super().__init__(f"{field}: не должен содержать пробелы")

# ==================================================================================
# Ошибки базы данных
class DataBaseException(DomainError):
    """Исключения связанные с базой данных"""
    def __init__(self, message: str):
        super().__init__(message)
class FileSaveException(DataBaseException):
    """Исключения при ошибке сохранения в файл"""
    def __init__(self, name: str,
                       err: Exception):
        super().__init__(f"Ошибка при сохранении '{name}'. "
                         f"Причина: {type(err).__name__}: {err}")
class FileLoadException(DataBaseException):
    """Исключения при ошибке загрузке из файла"""
    def __init__(self, name: str,
                       err: Exception):
        super().__init__(f"Ошибка при загрузке '{name}'. "
                         f"Причина: {type(err).__name__}: {err}")
class PortfolioDontFindException(DataBaseException):
    """Исключения при отсутствии в БД портфеля"""
    def __init__(self, field: str):
        super().__init__(f"Портфель с таким id "
                      f"'{field}' не найден.")
class CacheExistException(DataBaseException):
    """Исключения при отсутствии данных из кеша"""
    def __init__(self):
        super().__init__(f"Локальный кеш курсов пуст. "
                         f"Выполните 'update-rates', чтобы загрузить данные.")
class CacheCurrException(DataBaseException):
    """Исключения при отсутствии в кеше указанной валюты"""
    def __init__(self, field: str):
        super().__init__(f"Курс для '{field}' не найден в кеше.")

# ==================================================================================
# Ошибки валидации
class ValidationException(DomainError):
    """Исключения при валидации данных"""
    def __init__(self, message: str):
        super().__init__(message)

class LenValidationException(ValidationException):
    """Исключения при длине пароля меньше допустимой"""
    def __init__(self, field: str,
                 limit_min: int = 0):
        super().__init__(f"{field} должен быть не короче {limit_min} символов")

class PositiveValidationException(ValidationException):
    """Исключения при отрицательном значении так где это недопустимо"""
    def __init__(self, field: str):
        super().__init__(f"{field} должна быть положительным числом")

class ExistValidationException(ValidationException):
    """Исключения при отсутствии обязательного значения"""
    def __init__(self, field: str):
        super().__init__(f"Пустое значения для поля {field} не допускается")

class TypeValidationException(ValidationException):
    """Исключения при не соответствии типа вводимых данных допустимым"""
    def __init__(self, field: str):
        super().__init__(f"Тип значения для поля {field} "
                         f"не соответствует допустимому")
# ==================================================================================
# Ошибки связанные с инициализацией и аутентификацией пользователя
class AuthentificationException(DomainError):
    """Исключения при аутентификации пользователя"""
    def __init__(self, message: str):
        super().__init__(message)

class UserAuthentificationException(AuthentificationException):
    """Исключения при не нахождении пользователя в базе"""
    def __init__(self, field: str):
        super().__init__(f"Пользователь '{field}' не найден")

class PasswordAuthentificationException(AuthentificationException):
    """Исключения при неправильно введенном пароле"""
    def __init__(self):
        super().__init__(f"Неверный пароль")

class UserExistAuthentificationException(AuthentificationException):
    """Исключения существования такого пользователя при регистрации"""
    def __init__(self, field: str):
        super().__init__(f"Имя пользователя '{field}' уже занято")

class LoginAuthentificationException(AuthentificationException):
    """Исключения при попытке совершить торговые операции без login"""
    def __init__(self):
        super().__init__(f"Сначала выполните login")
# ==================================================================================
# Ошибки парсера консольной строки
# ==================================================================================
class ConsoleParserException(Exception):
    """Ошибка парсинга командной строки"""
    def __init__(self, message: str):
        super().__init__(message)
class UnknownCommandConsoleParserException(ConsoleParserException):
    """Исключения при неопознанной команде"""
    def __init__(self, field: str):
        super().__init__(f"Неизвестная команда: {field}")
class RequestConsoleParserException(ConsoleParserException):
    """Исключения при некорректной форме запроса"""
    def __init__(self, command_name: str,
                 req: str):
        super().__init__(f"Для команды '{command_name}' "
                         f"формат запроса '{req}' некорректен")
class SpaceConsoleParserException(ConsoleParserException):
    """Исключения при пробеле посреди введенного значения"""
    def __init__(self, field: str):
        super().__init__(f"В поле {field} допускается ввод "
                         f"только одного значения за раз")

class SymbolConsoleParserException(ConsoleParserException):
    """Исключения при не допустимых символах ввода"""
    def __init__(self, field: str,
                 allowed: str):
        super().__init__(f"Недопустимые символы в "
                         f"поле '{field}'. Разрешены:\n "
                         f"{allowed}")

