import shlex
from typing import Callable

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ConsoleParserException,
    RequestConsoleParserException,
    SpaceConsoleParserException,
    SymbolConsoleParserException,
    UnknownCommandConsoleParserException,
)
from valutatrade_hub.core.usecases import (
    buy,
    change_password,
    get_rate,
    login_account,
    portfolio_fun,
    register_new_account,
    sell,
    show_rates_fun,
)
from valutatrade_hub.core.utils import format_rate_for_output
from valutatrade_hub.decorators import handle_errors, session_check, validate_command
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import enable_console_logging, setup_logger
from valutatrade_hub.parser_service.shceduler import Scheduler
from valutatrade_hub.parser_service.updater import RatesUpdater

# ==================================================================================
# Основная функция модуля
# ==================================================================================
sl = SettingsLoader()

def run() -> None:
    """
    Функция ввода данных от пользователя
    """
    # проверка загрузки данных из config.json
    if not commands_signature:
        print("config.json не найден или повреждён.")
        return None
    scheduler = Scheduler(interval_seconds=sl.get(key = "rates_ttl_seconds"))
    # настройка логгера
    session_manager = SessionManager()
    setup_logger(log_dir = sl.get(key = 'log_path'),
                 log_file_name = sl.get(key = 'log_file_name'),
                 time_config = sl.get(key = 'data_format_local'),
                 name = sl.get(key = 'logger_name'))
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
        except ConsoleParserException as e:
            print(e)
        if parsing_console_data is not None:
            cli_args = parsing_console_data
            # ключи служебных атрибутов в формате "_*"
            cli_args["_session"] = session_manager
            cli_args["_scheduler"] = scheduler
            cli_return = get_cli_fun(command_name)(**cli_args)
            if not cli_return:
                break
            else:
                # возврат только пробелов эквивалентен continue
                if cli_return.strip() != "":
                    print(cli_return)

# ==================================================================================
# данные конфигурации. Так как они присваиваются то не написаны в верхнем регистре
# как константы
currency_code_set = sl.get("supported_currency")
allowed_chars = set(sl.get("allowed_chars"))
commands_signature = sl.get("commands_signature")

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
        при повторном входе предупреждает о перезаходе
        """
        if self._session_id:
            if self._session_id == user_id:
                return f"Вы уже зашли как '{self._user_name}'"
            else:
                old_name = self._user_name
                self._session_id = user_id
                self._user_name = user_name
                return f"Вы перезашли с {old_name} на {user_name}"
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
    def show_rates_output_format(input_data: list[dict]) -> str:
        """
        Формируем строку вывода для команды show-rates.
        В выводе используем pretty_table.
        """
        pretty_table = PrettyTable()
        # выравниваем таблицу
        pretty_table.field_names = ["Валюта",
                                    "Курс",
                                    "updated at"]
        pretty_table.align["Валюта"] = "l"
        pretty_table.align["Курс"] = "l"
        pretty_table.align["updated at"] = "l"
        output_str = "Rates from cache:\n"

        for idata in input_data:
            pretty_table.add_row([
                ("- " + idata.get("code_pairs")),
                format_rate_for_output(value = idata.get("rates"),
                              num_digits = 2),
                f"{idata.get("updated_at")}"
                ])
        output_str += pretty_table.get_string()
        return output_str

    @staticmethod
    def register_output_format(input_data: dict) -> str:
        """Формируем строку вывода для register"""
        output_str = (f"Пользователь '{input_data.get("user_name")}' "
                      f"зарегистрирован (id={input_data.get("id")}). "
                      f"Войдите: login --username {input_data.get("user_name")}"
                      f" --password {"".join("*" for _ in 
                                             input_data.get("password"))}")
        return output_str + "\n"

    @staticmethod
    def show_portfolio_output_format(input_data: dict) -> str:
        """
        Формируем строку вывода для команды show-portfolio.
        В выводе используем pretty_table.
        """

        output_str = (f"Портфель пользователя "
                      f"'{input_data.get("username")}' "
                      f"(база: {input_data.get("code")}):\n")

        pretty_table = PrettyTable()
        # выравниваем таблицу
        pretty_table.field_names = ["Валюта", "Баланс"," " ,"В базовой валюте"]
        pretty_table.align["Валюта"] = "l"
        pretty_table.align["Баланс"] = "l"
        pretty_table.align[" "] = "l"
        pretty_table.align["В базовой валюте"] = "r"
        for ccl in input_data.get("portfolio_info"):
            pretty_table.add_row([ccl.get("code"),
                                  str(format_rate_for_output(
                                value = ccl.get("value"),
                                num_digits = 2)),
                                  str("-> "),
                                  str(format_rate_for_output(
                                value = ccl.get("convert"),
                                num_digits = 2) + f" {input_data.get("code")}")])

        output_str += pretty_table.get_string() + "\n"
        output_str += f"ИТОГО: {format_rate_for_output(
                                value = input_data.get("total_sum"),
                                num_digits = 4)} {input_data.get("code")}"
        return output_str

    @staticmethod
    def buy_output_format(input_data: dict) -> str:
        """Формируем строку вывода для команды buy"""
        uc_ret = input_data.get("use_cases_ret") or {}

        amount = input_data.get("amount", 0)
        currency = input_data.get("currency", "")
        base_val_code = uc_ret.get("base_val_code", "")

        exchange_rate = uc_ret.get("exchange_rate", 0.0)
        old_value = uc_ret.get("old_value", 0.0)
        new_value = uc_ret.get("new_value", 0.0)
        base_curr_operation_value = uc_ret.get("base_curr_operation_value", 0.0)

        output_str = (
            f"Покупка выполнена: {amount} {currency} "
            f"по курсу {
            format_rate_for_output(value=exchange_rate, num_digits=2)} "
            f"{base_val_code}/{currency}\n"
        )
        output_str += "Изменения в портфеле:\n"
        output_str += (
            f"- {currency}: было {
            format_rate_for_output(value=old_value, num_digits=2)} → "
            f"стало {
            format_rate_for_output(value=new_value, num_digits=2)}\n"
        )
        output_str += (
            f"Оценочная стоимость покупки: "
            f"{format_rate_for_output(value=base_curr_operation_value, num_digits=2)} "
            f"{base_val_code}"
        )
        return output_str

    @staticmethod
    def sell_output_format(input_data: dict) -> str:
        """Формируем строку вывода для команды sell"""

        uc_ret = input_data.get("use_cases_ret") or {}

        amount = input_data.get("amount", 0)
        currency = input_data.get("currency", "")
        base_val_code = uc_ret.get("base_val_code", "")

        exchange_rate = uc_ret.get("exchange_rate", 0.0)
        old_value = uc_ret.get("old_value", 0.0)
        new_value = uc_ret.get("new_value", 0.0)
        base_curr_operation_value = uc_ret.get("base_curr_operation_value", 0.0)

        output_str = (
            f"Продажа выполнена: {amount} {currency} "
            f"по курсу {
            format_rate_for_output(value=exchange_rate, num_digits=2)} "
            f"{base_val_code}/{currency}\n"
        )
        output_str += "Изменения в портфеле:\n"
        output_str += (
            f"- {currency}: было {
            format_rate_for_output(value=old_value, num_digits=2)} → "
            f"стало {
            format_rate_for_output(value=new_value, num_digits=2)}\n"
        )
        output_str += (
            f"Оценочная выручка: "
            f"{format_rate_for_output(value=base_curr_operation_value, num_digits=2)} "
            f"{base_val_code}"
        )

        return output_str

    @staticmethod
    def get_rate_output_format(input_data: dict) -> str:
        """Формируем строку вывода для команды get-rate"""
        curr_from = input_data["curr_from"]
        curr_to = input_data["curr_to"]
        exc_rate = input_data.get("convert_rate", 0.0)
        reverse_rate = input_data.get("reverse_rate", 0.0)
        last_refresh = input_data.get("last_refresh", "-")

        output_str = (
            f"Курс {curr_from}→{curr_to}: "
            f"{format_rate_for_output(value=exc_rate, num_digits=2)} "
            f"(обновлено: {last_refresh})\n"
        )
        output_str += (
            f"Обратный курс {curr_to}→{curr_from}: "
            f"{format_rate_for_output(value=reverse_rate, num_digits=2)}"
        )
        return output_str

    @staticmethod
    def help_output_format(command_signature: dict) -> str:
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
                    command_args: list[str]) -> dict:
    """
    Функция парсит входящую строку и разбивает на словарь
    состоящий из ключа(ключевого слова) и значения
    """
    # получаем названий команд
    commands_name_set = {k for k in commands_signature.keys()}

    # проверяем что команда присутствует в списке допустимых
    if command_name not in commands_name_set:
        raise UnknownCommandConsoleParserException(field = command_name)

    # получаем копию словаря сигнатуры команд
    key_words = {**commands_signature}

    num_w = 0
    value_block = dict()
    k_words = set(key_words[command_name])
    args_name = ''
    while num_w < len(command_args):
        token = command_args[num_w]
        # проверяем соответствие слово на соответствие допустимым аргументам команды
        if token in k_words:
            if token in value_block:
                raise RequestConsoleParserException(command_name=command_name,
                                                 req=" ".join(command_args))
            args_name = token
            value_block[args_name] = ''
        else:
            # проверяем на корректность ввода и записываем в значение аргумента
            if not args_name:
                raise RequestConsoleParserException(command_name=command_name,
                                           req = " ".join(command_args))
            if value_block[args_name]:
                if "--" in token:
                    raise RequestConsoleParserException(command_name=command_name,
                                                     req=" ".join(command_args))
                else:
                    raise SpaceConsoleParserException(field = args_name)
            # проверяем на допустимые символы ввода
            if any(ch not in allowed_chars for ch in token):
                raise SymbolConsoleParserException(
                    field = args_name,
                    allowed = str(sorted(allowed_chars)))
            value_block[args_name] += token
        num_w += 1
    return value_block

# ==================================================================================
# Консольные функции
# ==================================================================================
@handle_errors
def cli_exit_fun(**k_cli) -> bool:
    """Функция выхода из программы"""
    k_cli.get('_session').exit_session()
    scheduler = k_cli["_scheduler"]
    if scheduler.running:
        scheduler.stop()
    return False
@handle_errors
def cli_help_fun(**k_cli) -> str:
    """Функция получения списка допустимых команд"""
    return FormattedOutput().help_output_format(commands_signature)

@handle_errors
@validate_command( "register")
def cli_register_fun(**k_cli) -> str:
    """
    Функция регистрации пользователя
    При совпадении имени вызывает ошибку регистрации.
    """
    _user_name = k_cli.get('--username')
    _password = k_cli.get('--password')
    acc_id = register_new_account(_user_name, _password).get("result")

    return FormattedOutput().register_output_format({"user_name": _user_name,
                               "password": _password,
                               "id": str(acc_id)})

@handle_errors
@validate_command("login")
def cli_login_fun(**k_cli) -> str:
    """
    Функция входа пользователя в систему, вызывает проверку пароля,
    при успешной проверке активирует сессионный менеджер,
    """
    session_manager = k_cli.get('_session')
    _user_name = k_cli.get('--username')
    _password = k_cli.get('--password')
    user_id = login_account(_user_name, _password).get("result")

    return session_manager.open_session(user_id=user_id,
                                       user_name=_user_name)


@handle_errors
@session_check
@validate_command("show-portfolio")
def cli_show_portfolio_fun(**k_cli) -> str:
    """
    Функция вывода портфеля всех кошельков,
    опционально переводит в выбранную валюту
    """
    session_manager = k_cli.get('_session')
    b_code = k_cli.get('--base') or sl.get(key = "base_currency")
    base_code = get_currency(code = b_code,
                             curr_data = sl
                                .get(key = "currencies")
                                .get(b_code))
    portfolio_fun_data = portfolio_fun(
                                user_id= session_manager.session_id,
                                curr_base_code = base_code.code
                                )
    return FormattedOutput().show_portfolio_output_format(portfolio_fun_data)

@handle_errors
@session_check
@validate_command("buy")
def cli_buy_fun(**k_cli) -> str:
    """Функция обработки команды на покупку"""
    session_manager = k_cli.get('_session')
    _amount = k_cli['--amount']
    _currency = get_currency(code = k_cli.get('--currency'),
                             curr_data = sl
                                .get(key = "currencies")
                                .get(k_cli.get('--currency'))
                             )
    use_case_ret = buy(user_id = session_manager.session_id,
                       curr_code = _currency.code,
                       amount = _amount)
    return FormattedOutput().buy_output_format({
                        "amount": _amount,
                        "currency": _currency.code,
                        "use_cases_ret": use_case_ret}
                        )

@handle_errors
@session_check
@validate_command("sell")
def cli_sell_fun(**k_cli) ->str:
    """Функция обработки команды на продажу"""
    session_manager = k_cli.get('_session')
    _amount = k_cli['--amount']
    _currency = get_currency(code = k_cli.get('--currency'),
                             curr_data = sl
                                .get(key = "currencies")
                                .get(k_cli.get('--currency')))
    use_case_ret = sell(user_id=session_manager.session_id,
                       curr_code=_currency.code,
                       amount=_amount)
    return FormattedOutput().sell_output_format({
                        "amount": _amount,
                        "currency": _currency.code,
                        "use_cases_ret": use_case_ret}
                        )

@handle_errors
@validate_command("get-rate")
def cli_get_rates(**k_cli) -> str:
    """Функция обработки команды на показ курса валют"""
    curr_from = get_currency(code = k_cli.get('--from'),
                             curr_data = sl
                                .get(key = "currencies")
                                .get(k_cli.get('--from')))
    curr_to = get_currency(code = k_cli.get('--to'),
                             curr_data = sl
                                .get(key = "currencies")
                                .get(k_cli.get('--to')))
    updater = RatesUpdater.build()
    use_case_ret = get_rate(
             curr_from = curr_from.code,
             curr_to = curr_to.code,
             updater = updater)
    return FormattedOutput().get_rate_output_format({
                        "curr_from": curr_from.code,
                        "curr_to": curr_to.code,
                        "reverse_rate": use_case_ret.get("reverse_rate"),
                        "convert_rate": use_case_ret.get("convert_rate"),
                        "last_refresh": use_case_ret.get("last_refresh")}
                        )

@handle_errors
@validate_command("show-rates")
def cli_show_rates(**k_cli) -> str:
    """
    Обрабатываем запрос на показ курса валют
    по фильтру, либо топ криптовалют, либо
    указанную в --currency, опционально показываем
    в валюте указанной в --base
    """
    converted_code = get_currency(code = sl.get(key = "base_currency"),
                             curr_data = sl
                                .get(key = "currencies")
                                .get(sl.get(key = "base_currency")))

    if k_cli.get("--base"):
        converted_code = get_currency(code = k_cli["--base"],
                             curr_data = sl
                                .get(key = "currencies")
                                .get(k_cli["--base"]))
    if k_cli.get("--currency"):
        _curr_code = get_currency(code = k_cli["--currency"],
                             curr_data = sl
                                .get(key = "currencies")
                                .get(k_cli["--currency"]))
        result = show_rates_fun(filtered_key = "currency",
                                curr_code = _curr_code.code,
                                convert_code = converted_code.code)
    elif '--top' in k_cli:

        result = show_rates_fun(filtered_key="top",
                                top_n = k_cli["--top"],
                                convert_code = converted_code.code)
    else:
        result = show_rates_fun(convert_code = converted_code.code)


    return FormattedOutput().show_rates_output_format(result)

@handle_errors
@validate_command("update-rates")
def cli_update_rates(**k_cli) -> str:
    """
    Вызов функции обновления курсов валют
    опционально из одного источника --source
    """
    updater = RatesUpdater.build(source = k_cli.get("--source"))
    # Логгер временно пишет в консоль только внутри with.
    # После выхода handler удаляется, логи идут только в файл.
    with enable_console_logging(logger_name = "logger_1",
                                time_config = sl.get(key = 'data_format_local')):
        return updater.run_update()

@handle_errors
@session_check
@validate_command("change-password")
def cli_change_password(**k_cli) -> str:
    """Обработка команды на смену пароля"""
    change_password(k_cli.get("--password"), k_cli.get('_session').session_id)
    return "Пароль успешно изменен."

@handle_errors
@validate_command("scheduler-run")
def cli_scheduler_run(**k_cli) -> str:
    """Запуск фонового обновления валют"""

    updater = RatesUpdater.build()
    scheduler = k_cli.get("_scheduler")
    scheduler.updater = updater.run_update
    scheduler.start()
    return "Запущено фоновое обновление курсов валют"

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
    "show-rates": cli_show_rates,
    "update-rates": cli_update_rates,
    "change-password": cli_change_password,
    "scheduler-run": cli_scheduler_run,
    "help": cli_help_fun
}

def get_cli_fun(command_name:str) -> Callable:
    """Передача cli_функций в run() по словарю CLI_FUN"""
    if command_name in CLI_FUN:
        return CLI_FUN[command_name]
    else:
        # проверка на случай если в config.json будет добавлена
        # не определенная в программе команда
        def unexpected_command_in_config(*args) -> str:
            """Проверка корректности команды из config.json"""
            return ("Проверьте файл config.json, "
                    "в список команд добавлена "
                    "не поддерживаемая функция")
        return unexpected_command_in_config