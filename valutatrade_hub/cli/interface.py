import shlex
from typing import List, Dict, Set, Any, Callable
import logging

from valutatrade_hub.core.usecases import (portfolio_fun, get_rate, buy, sell,
    register_new_account, login_account)
from valutatrade_hub.core.utils import dynamic_round, ensure_rates_if_missing

from prettytable import PrettyTable



# ==================================================================================
# Основная функция модуля
# ==================================================================================


def run() -> None:
    """
    Функция ввода данных от пользователя
    """
    ensure_rates_if_missing()
    session_manager = SessionManager()
    while True:
        user_input = input('>>> Введите команду: ')
        try:
            args = shlex.split(user_input)
        except ValueError as e:
            print(f"Ошибка ввода: {e}")
            continue
        if not args:
            continue

        command_name = args[0]
        parsing_console_data = None
        try:
            parsing_console_data = parse_input_str(command_name, args[1:])
        except Exception as e:
            print(e)
        if parsing_console_data is not None:
            cli_args = parsing_console_data
            # ключи служебных атрибутов в формате "_*"
            cli_args["_session"] = session_manager
            cli_return = get_cli_fun(command_name)(**cli_args)
            if not cli_return:
                break
            else:
                # возврат только пробелов эквивалентен continue
                if cli_return.strip() != "":
                    print(cli_return)

# ==================================================================================
# Константы, сигнатуры
# ==================================================================================

CURRENCY_CODE_SET = {
    "USD",
    "EUR",
    "BTC",
    "RUB",
    "ETH"
}

ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyz"
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    "0123456789"
                    "_.-!@#*")
# словарь сигнатуры консольных команд
COMMANDS_SIGNATURE = {
        "exit": {},
        "help": {},
        "register": {
            "--username": {"exist": True, "type": str,},
            "--password": {"exist": True, "min_len": 4, "type": str}},
        "login": {
            "--username": {"exist": True, "type": str},
            "--password": {"exist": True, "min_len": 4, "type": str}},
        "buy": {
            "--currency": {"exist": True, "type": str,
                          "currency_code_validation":CURRENCY_CODE_SET},
            "--amount":   {"exist": True, "type": float}},
        "sell": {
            "--currency": {"exist": True, "type": str,
                          "currency_code_validation":CURRENCY_CODE_SET},
            "--amount":   {"exist": True, "type": float}},
        "get-rate": {
            "--from":     {"exist": True, "type": str,
                          "currency_code_validation":CURRENCY_CODE_SET},
            "--to":       {"exist": True, "type": str,
                          "currency_code_validation": CURRENCY_CODE_SET}},
        "show-portfolio": {
            "--base":     {"exist": False, "type": str,
                          "currency_code_validation": CURRENCY_CODE_SET}},
    }
# Человекочитаемый формат команд
FIELD_NAMES = {
    "--username": "Имя пользователя",
    "--password": "Пароль",
    "--currency": "Валюта",
    "--amount": "Сумма",
    "--base": "Валюта сравнения",
    "--from": "Валюта которую конвертируем",
    "--to": "Валюта в которую конвертируем"
}
# ==================================================================================
# Классы (инструменты)
# ==================================================================================
# Класс SessionManager добавлен в модуль interface.py ввиду жесткой
# структуры модулей в рамках ТЗ. Можно было бы перенести в отдельный модуль в cli
class SessionManager:
    """Класс управления сессией"""
    def __init__(self):
        self._session_id: int = 0
        self._user_name: str = ""
    def open_session(self,
                    user_id: int,
                    user_name: str) -> str:
        """
        Открываем сессию после успешного login,
        про повторной попытке входа, уточняет, желает ли пользователь перезайти
        """
        if self._session_id:
            if self._session_id == user_id:
                return f"Вы уже зашли как '{self._user_name}'"
            else:
                user_input = input(f"Вы уже зашли как '{self._user_name}', "
                               f"вы уверены что хотите перезайти "
                               f"как '{user_name}'? [y/n]:")
                if user_input.strip() == 'y':
                    self._session_id = user_id
                    self._user_name = user_name
                    return f"Вы вошли как '{self._user_name}'"
                else:
                    return f"вход прерван"
        else:
            self._session_id = user_id
            self._user_name = user_name
            return f"Вы вошли как '{self._user_name}'"

    def exit_session(self) -> None:
        """обнулений id при выходе"""
        self._session_id = 0
        self._user_name = ""
    def check_session(self):
        """проверка активности сессии"""
        if not self._session_id:
            return False
        return True
    @property
    def user_name(self):
        """получить id сессий"""
        return self._user_name
    @property
    def session_id(self):
        """получить имя актуального пользователя"""
        return self._session_id

# Тоже можно было бы перенести в отдельный модуль в cli
class FormattedOutput:
    """Класс для определения формата текстового вывода для разных команд"""

    @staticmethod
    def register_output_format(_password: str = "",
                               _user_name: str = "",
                               _id: str = "") -> str:
        """Формируем строку вывода для register"""
        output_str = (f"Пользователь '{_user_name}' "
                      f"зарегистрирован (id={_id}). "
                      f"Войдите: login --username {_user_name}"
                      f" --password {"".join("*" for _ in _password)}")
        return output_str + "\n"

    @staticmethod
    def show_portfolio_output_format(
            curr_code_list: list[str],
            curr_value_list: list[float],
            convertation_rate: list[float],

            username: str = "",
            base_code: str = "USD",
            total_sum: float = 0,
    ) -> str:
        """
        Формируем строку вывода для команды show-portfolio.
        В выводе используем pretty_table.
        """
        if (len(curr_code_list) != len(curr_value_list)
                or len(curr_code_list) != len(convertation_rate)):
            raise ValidationException(message = "Ошибка соответствий данных")

        output_str = (f"Портфель пользователя "
                      f"'{username}' "
                      f"(база: {base_code}):\n")

        pretty_table = PrettyTable()
        # выравниваем таблицу
        pretty_table.field_names = ["Валюта", "Баланс"," " ,"В базовой валюте"]
        pretty_table.align["Валюта"] = "l"
        pretty_table.align["Баланс"] = "l"
        pretty_table.align[" "] = "l"
        pretty_table.align["В базовой валюте"] = "r"
        for num, ccl in enumerate(curr_code_list):
            pretty_table.add_row([ccl,
                                  str(dynamic_round(
                                value = curr_value_list[num],
                                num_digits = 2)),
                                  str("-> "),
                                  str(dynamic_round(
                                value = curr_value_list[num]*
                                        convertation_rate[num],
                                num_digits = 2) + f" {base_code}")])

        output_str += pretty_table.get_string() + "\n"
        output_str += f"ИТОГО: {dynamic_round(
                                value = total_sum,
                                num_digits = 4)} {base_code}"
        return output_str

    @staticmethod
    def buy_output_format(amount: str = "",
                          currency: str = "",
                          use_cases_ret: dict = None
                          ) -> str:
        """Формируем строку вывода для команды buy"""
        output_str = (f"Покупка выполнена: "
                      f"{amount} {currency} "
                      f"по курсу {dynamic_round(
                                value = use_cases_ret.get("exchange_rate"), 
                                num_digits = 2)} "
                      f"{use_cases_ret.get('base_val_code')}/{currency}\n")
        output_str += "Изменения в портфеле:\n"
        output_str += (f"- {currency}: было {use_cases_ret.get("old_value")} → "
                       f"стало {use_cases_ret.get("new_value")}\n")
        output_str += (f"Оценочная стоимость покупки: "
                       f"{dynamic_round(value = use_cases_ret.get("base_curr_operation_value"),
                                        num_digits = 2)} "
                       f" {use_cases_ret.get('base_val_code')}")

        return output_str

    @staticmethod
    def sell_output_format(amount: str = "",
                           currency: str = "",
                           use_cases_ret: dict = None
                           ) -> str:
        """Формируем строку вывода для команды sell"""
        output_str = (f"Продажа выполнена: "
                      f"{amount} {currency} "
                      f"по курсу {dynamic_round(
                            value = use_cases_ret.get("exchange_rate"), 
                            num_digits = 2)} "
                      f"{use_cases_ret.get('base_val_code')}/{currency}\n")
        output_str += "Изменения в портфеле:\n"
        output_str += (f"- {currency}: было {use_cases_ret.get("old_value")} → "
                       f"стало {use_cases_ret.get("new_value")}\n")
        output_str += (f" Оценочная выручка: {dynamic_round(
                            value = use_cases_ret.get("base_curr_operation_value"),
                            num_digits = 2
                            )}"
                       f" {use_cases_ret.get('base_val_code')}")


        return output_str

    @staticmethod
    def get_rate_output_format(curr_from: str = "",
                               curr_to: str = "",
                               exc_rate: float = 1,
                               last_refresh: str = ""
                               ) -> str:
        """Формируем строку вывода для команды get-rate"""
        output_str = (f"Курс {curr_from}→{curr_to}: {dynamic_round(
                                                                   value = exc_rate, 
                                                                   num_digits = 2)}"
                      f" (обновлено: {last_refresh})\n")
        output_str += f"Обратный курс {curr_to}→{curr_from}: {dynamic_round(
                                                                   value = (1 / exc_rate), 
                                                                   num_digits = 2)}"
        return output_str

    @staticmethod
    def help_output_format(command_signature: dict[str, dict[Any, Any] ]) -> str:
        """Формирования строки для команды help"""
        # Находим длину самой длинной команды, чтобы выровнять колонку
        max_cmd_len = max(len(cmd) for cmd in command_signature.keys())
        output_lines = ["Список допустимых команд:"]
        # Сортируем по алфавиту
        for cmd in sorted(command_signature.keys()):
            args = " ".join(command_signature[cmd].keys())
            # Форматируем строку чтобы
            # команда выравнивалась по max_cmd_len символов
            line = f"> {cmd:<{max_cmd_len}} | вводимые данные: {args}"
            output_lines.append(line)

        return "\n".join(output_lines)

# ==================================================================================
# Парсер ввода с консоли
# ==================================================================================
def parse_input_str(command_name: str,
                    command_args: List[str]) -> Dict:
    """
    Функция парсит входящую строку и разбивает на словарь
    состоящий из ключа(ключевого слова) и значения
    """
    # получаем названий команд
    commands_name_set = {k for k in COMMANDS_SIGNATURE.keys()}

    # проверяем что команда присутствует в списке допустимых
    if command_name not in commands_name_set:
        raise Exception()

    # получаем копию словаря сигнатуры команд
    key_words = {**COMMANDS_SIGNATURE}

    num_w = 0
    value_block = dict()
    k_words = set(key_words[command_name])
    args_name = ''
    while num_w < len(command_args):
        token = command_args[num_w]
        # проверяем соответствие слово на соответствие допустимым аргументам команды
        if token in k_words:
            if token in value_block:
                raise Exception()
            args_name = token
            value_block[args_name] = ''
        else:
            # проверяем на корректность ввода и записываем в значение аргумента
            if not args_name:
                raise Exception()
            if value_block[args_name]:
                if "--" in token:
                    raise Exception()
                else:
                    raise Exception()
            # проверяем на допустимые символы ввода
            if any(ch not in ALLOWED_CHARS for ch in token):
                raise Exception()
            value_block[args_name] += token
        num_w += 1
    return value_block

# ==================================================================================
# Консольные функции
# ==================================================================================

def cli_exit_fun(**k_cli) -> bool:
    """Функция выхода из программы"""
    k_cli.get('_session').exit_session()

    return False
def cli_help_fun(**k_cli) -> str:
    """Функция получения списка допустимых команд"""
    return FormattedOutput().help_output_format(COMMANDS_SIGNATURE)


def cli_register_fun(**k_cli) -> str:
    """
    Функция регистрации пользователя
    При совпадении имени вызывает ошибку регистрации.
    """
    _user_name = k_cli.get('--username')
    _password = k_cli.get('--password')
    acc_id = register_new_account(_user_name, _password).get("result")

    return FormattedOutput().register_output_format(_user_name = _user_name,
                               _password = _password,
                               _id = str(acc_id))

def cli_login_fun(**k_cli) -> str:
    """
    Функция входа пользователя в систему, вызывает проверку пароля,
    при успешной проверке активирует сессионный менеджер,
    """
    session_manager = k_cli.get('_session')
    if not session_manager.check_session:
        return ""
    _user_name = k_cli.get('--username')
    _password = k_cli.get('--password')
    user_id = login_account(_user_name, _password).get("result")
    return session_manager.open_session(user_id=user_id,
                                       user_name=_user_name)

def cli_show_portfolio_fun(**k_cli) -> str:
    """
    Функция вывода портфеля всех кошельков,
    опционально переводит в выбранную валюту
    """
    session_manager = k_cli.get('_session')
    if not session_manager.check_session:
        return ""
    base_code = k_cli.get('--base') or "USD"
    base_code = get_currency(code = base_code)
    portfolio_fun_data = portfolio_fun(
                                user_id= session_manager.session_id,
                                curr_base_code = base_code.code
                                )
    return FormattedOutput().show_portfolio_output_format(*portfolio_fun_data)

def cli_buy_fun(**k_cli) -> str:
    """Функция обработки команды на покупку"""
    session_manager = k_cli.get('_session')
    if not session_manager.check_session:
        return ""
    _currency = k_cli['--currency']
    _amount = k_cli['--amount']
    use_case_ret = buy(user_id = session_manager.session_id,
                       curr_code = _currency,
                       amount = _amount)
    return FormattedOutput().buy_output_format(
                      amount = _amount,
                      currency = _currency,
                      use_cases_ret = use_case_ret
                      )

def cli_sell_fun(**k_cli) ->str:
    """Функция обработки команды на продажу"""
    session_manager = k_cli.get('_session')

    if not session_manager.check_session:
        return ""

    _currency = k_cli['--currency']
    _amount = k_cli['--amount']
    use_case_ret = sell(user_id=session_manager.session_id,
                       curr_code=_currency,
                       amount=_amount)
    return FormattedOutput().sell_output_format(
        amount=_amount,
        currency=_currency,
        use_cases_ret=use_case_ret
    )


def cli_get_rates(**k_cli) -> str:
    """Функция обработки команды на показ курса валют"""

    curr_from = k_cli['--from']
    curr_to = k_cli['--to']
    exc_rate, last_refresh = get_rate(
             curr_from = curr_from.code,
             curr_to = curr_to.code)
    return FormattedOutput().get_rate_output_format(
             curr_from = curr_from.code,
             curr_to = curr_to.code,
             exc_rate = exc_rate,
             last_refresh = last_refresh)

def cli_show_rates(**k_cli) -> str:
    """
    Обрабатываем запрос на показ курса валют
    по фильтру, либо топ криптовалют, либо
    указанную в --currency, опционально показываем
    в валюте указанной в --base
    """
    converted_code = get_currency(code = sl.get(key="base_currency"))
    if k_cli.get("--base"):
        converted_code = get_currency(code = k_cli["--base"])
    if k_cli.get("--currency"):
        _curr_code = get_currency(code = k_cli["--currency"])
        result = show_rates_fun(filtered_key = "currency",
                                curr_code = _curr_code.code,
                                convert_code = converted_code.code)
    elif '--top' in k_cli:

        result = show_rates_fun(filtered_key="top",
                                top_n = k_cli["--top"],
                                convert_code=converted_code.code)
    else:
        result = show_rates_fun(convert_code=converted_code.code)


    return FormattedOutput().show_rates_output_format(result)






# ==================================================================================
# Словарь консольных функции
# ==================================================================================
CLI_FUN = {
    "exit" : cli_exit_fun,
    "register" : cli_register_fun,
    "login" : cli_login_fun,
    "show-portfolio" : cli_show_portfolio_fun,
    "buy" : cli_buy_fun,
    "sell" : cli_sell_fun,
    "get-rate" : cli_get_rates,
    "help": cli_help_fun
}

def get_cli_fun(command_name:str) -> Callable:
    """Передача cli_функций в run() по словарю CLI_FUN"""
    return CLI_FUN[command_name]