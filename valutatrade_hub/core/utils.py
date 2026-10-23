import os
import json
import math
from hashlib import pbkdf2_hmac
from datetime import datetime, timezone
from pathlib import Path



def ensure_rates_if_missing() -> None:
    """Если rates.json отсутствует, создаёт заглушку"""

    path = Path(root_data_path()) / "rates.json"
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
        save_data_in(file_name="rates", input_data = stub_data)





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
# Методы _____________________________________________________
def load_data_from(file_name: str,
                   tag: str = None,
                   tag_name: str = None) -> dict | list:
    """
    Загружает данные из директории data
    из файла указанном в file_name.
    Допустимо сразу возвратить конкретную запись
    по тэгу и значению
    """
    try:
        with open(os.path.join(
                root_data_path(), f"{file_name}.json"),
                encoding="utf-8") as json_file:
            if tag is not None and tag_name is not None:
                load_data = json.load(json_file)
                for ld in load_data:
                    if str(ld[tag]) == tag_name:
                        return ld
                return []
            else:
                return json.load(json_file)
    except FileNotFoundError:
        # Если файл не найден отдаем пустой список
        # Не прокидываем исключения так как при первом
        # входе это нормальная ситуация
        return []


def save_data_in(file_name: str,
                 input_data: dict | list
                 ) -> None:
    """
    Сохраняет input_data в директорию data
    в файл указанном в file_name.
    """
    with open(os.path.join(
            root_data_path(), f"{file_name}.json"),
            "w",
            encoding="utf-8") as json_file:
        json.dump(input_data, json_file, ensure_ascii=False, indent=2)


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

