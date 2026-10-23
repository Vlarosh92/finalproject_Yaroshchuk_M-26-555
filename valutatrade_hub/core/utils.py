import os
import json
import math
from hashlib import pbkdf2_hmac
from datetime import datetime, timezone
from pathlib import Path


def status_code_api_err(status_code: int) -> str:
    """
    Функция для возврата сообщений об
    ошибках подключения к API-клиентам
    """
    mess = "код ошибки: " + str(status_code)
    if status_code == 429:
        mess = ("Слишком "
                "много запросов к API. "
                "Пожалуйста подождите")
    if status_code == 401:
        mess = ("Неверный API-ключ, проверьте "
                "корректность и наличие "
                "EXCHANGERATE_API_KEY")
    if 400 <= status_code < 500:
        mess = f"Ошибка запроса (код {status_code})"
    if 500 <= status_code < 600:
        mess = f"Сервер временно недоступен (код {status_code})"
    return mess

def dynamic_round(value: float,
                  num_digits: int = 2) -> str:
    """
    Динамическое форматирование числа для
    перевода валютного курса к корректному
    для вывода виду.
    """
    if value == 0:
        return str(value)
    # Работаем с модулем числа только для определения формата
    abs_val = abs(value)
    # Для обычного варианта
    if abs_val >= 0.1:
        return f"{value:.{num_digits}f}"
    # Для маленьких чисел.
    # Находим порядок числа.
    order = math.floor(math.log10(abs_val))
    # Добавляем к порядку num_digits
    total_decimals = -order + num_digits
    # Форматируем с нужным количеством знаков
    formatted = f"{value:.{total_decimals}f}"
    cleaned = formatted.rstrip('0')
    return cleaned


def str_to_datatime(ts: str) -> datetime:
    """Перевод строки в формат datatime"""
    time_fmt = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    ts = ts.strip()
    for t_fmt in time_fmt:
        try:
            return datetime.strptime(ts, t_fmt)
        except (ValueError, TypeError):
            continue
    raise Exception()

def data_time_comprehension(time_str_1: str,
                            time_str_2: str = None) -> int:
    """Функция сравнения дат по времени. Возвращает разницу в секундах"""
    # Если второй аргумент не передан, берем текущее время по utc
    if time_str_2 is None:
        time_str_2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dt1 = str_to_datatime(time_str_1)
    dt2 = str_to_datatime(time_str_2)

    delta = dt2 - dt1
    return int(delta.total_seconds())

def apply_rate(input_value: float,
                          exchange_rate: float) -> float:
    return input_value * exchange_rate
def curr_code_union(curr_1: str,
                    curr_2: str
                    ) -> str:
    """
    Функция для форматирования отдельных кодов в валютную пару.
    """
    return f"{curr_1}_{curr_2}"

def root_path() -> Path:
    """
    получаем корневую директорию
    """
    return Path(__file__).resolve().parent.parent.parent

def root_data_path() -> Path:
    """
    устанавливаем директорию хранения данных
    создаем если не существует
    """
    data_dir = "data"
    data_dir = root_path() / data_dir
    data_dir.mkdir(exist_ok=True)
    return data_dir


def password_creator(password: str) -> tuple:
    """
    Функция создания хешированного пароля и 'соли'
    """
    salt = os.urandom(16)
    hash_pass = pbkdf2_hmac(
          'sha256',
                    password.encode(),
                    salt,
                    10000
                    )
    return hash_pass.hex(), salt.hex()

def password_changer(password: str,
                     salt_hex: str) -> str:
    """
    Функция изменения пароля с заданной 'солью'
    """
    salt = bytes.fromhex(salt_hex)
    hash_pass = pbkdf2_hmac(
          'sha256',
                    password.encode(),
                    salt,
                    10000
                    )
    return hash_pass.hex()

def password_check(password_hash: str,
                   password: str,
                   salt_hex: str) -> bool:
    """
    функция проверки пароля
    """
    salt = bytes.fromhex(salt_hex)
    hash_pass = pbkdf2_hmac(
        'sha256',
        password.encode(),
        salt,
        10000
    )
    if password_hash == hash_pass.hex():
        return True
    else:
        return False

