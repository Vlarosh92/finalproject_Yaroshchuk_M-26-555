import logging
from functools import wraps
from typing import Callable

from valutatrade_hub.core.exceptions import (
    ApiError,
    AuthentificationException,
    CurrencyError,
    CurrencyNotFoundError,
    DataBaseException,
    ExistValidationException,
    LenValidationException,
    LoginAuthentificationException,
    PositiveValidationException,
    TradeException,
    TypeValidationException,
    ValidationException,
)
from valutatrade_hub.infra.settings import SettingsLoader


def log_action(action: str, verbose: bool = False):
    """
    Декоратор для логирования операций принимает из
    функции словарь и забирает данные по ключу log_info
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(SettingsLoader().get(key='logger_name'))
            message = action+" "
            try:
                result = func(*args, **kwargs)
                log_info = result.pop("log_info", False)
                verbose_info = result.pop("log_info_verbose", False)
                if not log_info:
                    log_info = ""
                if verbose and verbose_info:
                    logger.info(message + log_info + verbose_info + "result=OK")
                else:
                    logger.info(message + log_info + "result=OK")
                return result

            except Exception as e:
                logger.exception(
                    message + f"result=NeOK, "
                              f"error_type={type(e).__name__}, "
                              f"error_message={e}"
                )
                raise e
        return wrapper

    return decorator

def check_len(field_name: str,
              meth_name: str,
              min_len: int = 0,
              ):
    """
    Декоратор для строковых сеттеров и методов.
    Проверяет длину строкового аргумента функции.
    """
    # Данный декоратор сделан для гарантирования
    # целостности объекта класса даже при прямом вызове из другого кода
    # несмотря на то, что есть валидация на уровне входящих данных
    def real_decorator(func): # объявляем декоратор
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if field_name in kwargs:
                value = kwargs[field_name]
            else:
                value = list(args)[0]
            if isinstance(value, str):
                if len(value) >= min_len:
                    return func(self, *args, **kwargs)
                else:
                    raise LenValidationException(
                        field=meth_name,
                        limit_min = min_len
                    )
            else:
                raise TypeValidationException
        return wrapper
    return real_decorator

def positive_check(field_name: str,
                   meth_name: str):
    """
    Декоратор для числовых методов класса.
    Проверяет что значение положительно
    """
    def real_decorator(func): # объявляем декоратор
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if field_name in kwargs:
                value = kwargs[field_name]
            else:
                value = list(args)[0]
            if value is None:
                ExistValidationException(field=field_name)
            if isinstance(value, float):
                if value > 0:
                    return func(self, *args, **kwargs)
                else:
                    raise PositiveValidationException(
                        field = meth_name)
            else:
                raise TypeValidationException
        return wrapper
    return real_decorator


def memoize(func):
    """Кеш функция для show-portfolio и show-rates"""
    cache = {}
    def wrapper(*args, **kwargs):
        key = args + tuple(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    def clear():
        cache.clear()
    wrapper.clear = clear
    return wrapper


def session_check(func: Callable):
    """Декоратор проверки активности сессии"""
    @wraps(func)
    def wrapper(*args, **kwargs):

        session_manager = kwargs.get("_session")
        if session_manager is not None:
            if not session_manager.check_session():
                raise LoginAuthentificationException()
        return func(*args, **kwargs)

    return wrapper


def validate_command(command_name: str) -> Callable:
    """
    Декоратор валидации.
    Проверяет команды на корректность
    значений указанных в command_signature
    """
    # Карта строк из JSON в реальные типы Python
    TYPE_MAP = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool
    }
    # Карта человекочитаемого формата команд
    EXCEPTION_MESSAGE = {
      "--username" : "имя пользователя",
      "--password" : "пароль",
      "--currency": "валюта",
      "--amount": "сумма операции",
      "--from": "исходная валюта",
      "--to": "целевая валюта",
      "--base": "валюта конвертации",
      "--source": "источник данных",
      "--top": "топ криптовалют"
    }
    command_signature = SettingsLoader().get(key="commands_signature")
    def decorator(func: Callable):


        @wraps(func)
        def wrapper(*a, **kw):
            # Получаем конфигурацию данных
            rules_config = command_signature
            rules = rules_config.get(command_name)
            if not rules:
                return func(*a, **kw)
            clean_kwargs = {}
            # Проверяем что поле со значением exist вообще существует
            for field, rule in rules.items():
                if rule.get("exist") and field not in kw:
                    raise ExistValidationException(
                        field=EXCEPTION_MESSAGE.get(field))
            # Процесс валидации данных
            for field, value in kw.items():
                if field.startswith("_"):
                    clean_kwargs[field] = value
                    continue

                field_rules = rules.get(field, {})

                # Проверка существования
                if field_rules.get("exist") and not value:
                    raise ExistValidationException(
                        field = EXCEPTION_MESSAGE.get(field))

                # Приведение типа
                expected_type_name = field_rules.get("type")
                expected_type = TYPE_MAP.get(expected_type_name)
                final_value = value
                if expected_type is not None:
                    try:
                        final_value = expected_type(value)
                    except (ValueError, TypeError):
                        raise TypeValidationException(
                            field = EXCEPTION_MESSAGE.get(field)
                        )

                # Проверка длины для паролей
                min_len = field_rules.get("min_len")
                if min_len is not None and len(str(final_value)) < min_len:
                    raise LenValidationException(
                        field = EXCEPTION_MESSAGE.get(field),
                        limit_min=min_len
                    )

                # Проверка на допустимые значения
                allowed_set = field_rules.get("currency_code_validation")
                if allowed_set is not None and final_value not in allowed_set:
                    raise CurrencyNotFoundError(
                        field = final_value
                    )

                clean_kwargs[field] = final_value

            return func(*a, **clean_kwargs)

        return wrapper
    return decorator

def handle_errors(func):
    """
    Декоратор для ловли исключений
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(SettingsLoader().get(key='logger_name'))
        try:
            return func(*args, **kwargs)
        # Ошибки ограничений программы
        except ValidationException as e:
            return str(e)
        except CurrencyNotFoundError as e:
            user_input = input(f"{e}\n"
                               f"вывести список валют?[y/n]:")
            if user_input.strip() == 'y':
                return str(SettingsLoader().get(key="supported_currency"))
            else:
                return " "
        except CurrencyError as e:
            return str(e)
        except DataBaseException as e:
            return str(e)
        except AuthentificationException as e:
            return str(e)
        except TradeException as e:
            return str(e)
        except ApiError as e:
            return str(e)

        # Системные ошибки
        except FileNotFoundError:
            logger.error(f"Файл данных не найден "
                         f" в {func.__name__}",
                         exc_info=True)
            return ("Ошибка: Файл данных не найден, "
                    "для подробной информации смотрите в logs/parser.log")
        except TypeError:
            logger.error(f"Неверный тип данных "
                         f" в {func.__name__}",
                         exc_info=True)
            return ("Ошибка: Неверный тип данных, "
                    "для подробной информации смотрите в logs/parser.log")
        except KeyError as e:
            logger.error(f"Не хватает ключа: {e} "
                         f" в {func.__name__}",
                         exc_info=True)
            return (f"Ошибка: Не хватает ключа: {e}, "
                    f"для подробной информации смотрите в logs/parser.log")
        except ValueError as e:
            logger.error(f"Неверное значение {e} "
                         f" в {func.__name__}",
                         exc_info=True)
            return (f"Ошибка: Неверное значение {e}, "
                    f"для подробной информации смотрите в logs/parser.log")
        except AttributeError:
            logger.error(f"Объект не имеет такого свойства или метода "
                         f" в {func.__name__}",
                         exc_info=True)
            return ("Ошибка: Объект не имеет такого свойства или метода, "
                    "для подробной информации смотрите в logs/parser.log")
        except IndexError:
            logger.error(f"Запрос к несуществующему элементу "
                         f" в {func.__name__}",
                         exc_info=True)
            return ("Ошибка: Запрос к несуществующему элементу, "
                    "для подробной информации смотрите в logs/parser.log")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в {func.__name__}",
                         exc_info=True)
            return (f"Произошла непредвиденная ошибка: {e}, "
                    f"для подробной информации смотрите в logs/parser.log")
    return wrapper

