from datetime import datetime


from valutatrade_hub.core.models import (
    Users,
    Portfolio,
    Wallet)
from valutatrade_hub.core.utils import (
    apply_rate,
    load_data_from,
    save_data_in,
    password_creator,
    curr_code_union,
    ensure_rates_if_missing
)



def convert_currency(curr_code_base: str,
                     curr_code_convert: str,
                     ) -> float:
    """
    Функция конвертации курса базовой валюты
    к курсу конвертационной валюты
    """
    data = load_data_from(
                file_name="rates"
                )
    base_sys_code = "USD"

    # проверяем если первая валюта является базовой приравниваем её курс к 1
    # иначе составляем пару и ищем в локальном кеше rates.json
    if curr_code_base == base_sys_code:
        rate_base = 1
    else:
        rate_base_code = curr_code_union(curr_code_base, base_sys_code)
        rate_base = data["pairs"][rate_base_code]['rate']

    # проверяем если вторая валюта является базовой приравниваем её курс к 1
    # иначе составляем пару и ищем в локальном кеше rates.json
    if curr_code_convert == base_sys_code:
        rate_conv = 1
    else:
        rate_conv_code = curr_code_union(curr_code_convert, base_sys_code)
        rate_conv = dbm.get_rates()["pairs"][rate_conv_code]['rate']

    return rate_base / rate_conv

def portfolio_fun(user_id: int,
                       curr_base_code: str) -> tuple:
    """
    Функция получения данных по портфелю
    Возращает коды валют их баланс и
    сумма в пересчете к базовой валюте
    """

    user_data = load_data_from(
                file_name="users",
                tag="user_id",
                tag_name=str(user_id)
                )
    # переводим строку в формат datatime
    user_data["registration_date"] = datetime.strptime(
    user_data["registration_date"],
    "%Y-%m-%dT%H:%M:%S")

    portfolio_data = load_data_from(
            file_name="portfolios",
            tag="user_id",
            tag_name=str(user_id)
            )

    wallets_dict = {}
    for code, data in portfolio_data.get("wallets").items():
        _wallet = Wallet(
            currency_code = code,
            **data
        )
        wallets_dict[code] = _wallet
    portfolio_data["wallets"] = wallets_dict

    curr_portfolio = Portfolio(
            **portfolio_data,
            user = Users(**user_data)
        )

    actual_wallets = curr_portfolio.wallets
    if not actual_wallets:
        raise Exception()

    exchange_rates = load_data_from("rates")
    # если данные отсутствуют ставим заглушку
    if not exchange_rates:
        ensure_rates_if_missing()
        exchange_rates = load_data_from("rates")

    code_list = []
    value_list = []
    convert_list = []
    for k, w in actual_wallets.items():

        code_list.append(k)
        value_list.append(w.balance)
        convert_list.append(convert_currency(k, curr_base_code))

    total_sum = curr_portfolio.get_total_value(
        base_currency = curr_base_code,
        rates_pairs = exchange_rates)

    return (code_list,
            value_list,
            convert_list,
            curr_portfolio.user.username,
            curr_base_code,
            total_sum)



def login_account(username: str,
                  password: str) -> dict:
    """Проверяем соответствие пароля пользователю"""
    data_user = load_data_from(file_name="users",
                               tag="username",
                               tag_name=username)

    # если в бд не нашлось пользователя с таким именем
    if not data_user:
        raise Exception
        # переводим строку в формат datatime

    data_user["registration_date"] = datetime.strptime(
        data_user["registration_date"],
        "%Y-%m-%dT%H:%M:%S")

    if not Users(**data_user).verify_password(password):
        raise PasswordAuthentificationException
    return {"result": data_user.get("user_id")}

def change_password(password: str,
                    user_id: int) -> None:
    """Функция смены пароля пользователя"""
    data_user = load_data_from(file_name="users",
                               tag="user_id",
                               tag_name=str(user_id))

    # переводим строку в формат datatime
    data_user["registration_date"] = datetime.strptime(
        data_user["registration_date"],
        "%Y-%m-%dT%H:%M:%S")

    _user = Users(**data_user)
    _user.change_password(password)

    users_data = load_data_from(file_name="users")
    for du in users_data:

        if du["user_id"] == _user.user_id:
            du['hashed_password'] = _user.hashed_password
            break

    save_data_in(file_name='users',
                 input_data=users_data)

def register_new_account(username: str,
                         password: str) -> dict:
    """Функция регистрации нового аккаунта"""
    # Загружаем данные из users.json
    # Если файла нет отдаем пустой список
    data_user = load_data_from("users")
    user_name_list = [du['username'] for du in data_user]

    # Если уже зарегистрирован такой пользователь
    if username in user_name_list:
        raise Exception()


    # Загружаем данные из portfolios.json
    data_portfolios = load_data_from("portfolios")

    # Формируем новый id через автоинкремент
    max_id = max([d["user_id"] for d in data_user], default = 0) + 1
    # Формируем пароль
    hashed_password, salt = password_creator(password)
    # Формируем данные
    user = Users(user_id = max_id,
                 username = username,
                 salt = salt,
                 hashed_password = hashed_password,
                 registration_date = datetime.now()
    )
    new_users_data = [*data_user, {
        'user_id': user.user_id,
        'username': user.username,
        'hashed_password': user.hashed_password,
        'salt': user.salt,
        'registration_date': user.registration_date.strftime("%Y-%m-%dT%H:%M:%S")}]
    new_portfolio_data = [*data_portfolios, {"user_id": max_id, "wallets": {}}]

    # Сохраняем данные
    save_data_in(file_name='users',
                 input_data=new_users_data)
    save_data_in(file_name="portfolios",
                 input_data=new_portfolio_data)

    return {"result":max_id}
def get_rate(curr_from: str,
             curr_to: str
             ) -> tuple:
    """
    Функция получения курса валют
    """

    # множество допустимых валют
    currency_code_set = ["USD", "EUR", "BTC", "RUB","ETH"]

    base_val_code = "USD"

    # загружаем данные по курсам и время последнего обновления
    exc_rates = load_data_from("rates")
    # если данные отсутствуют ставим заглушку
    if not exc_rates:
        ensure_rates_if_missing()

    # валидируем данные вводимых валют к допустимым
    if curr_from not in currency_code_set:
        CurrencyNotFoundError(field = curr_from)
    if curr_to not in currency_code_set:
        CurrencyNotFoundError(field = curr_to)

    # получаем конвертированный курс
    convert_rate = convert_currency(curr_from, curr_to)

    return convert_rate, last_refresh
def trade_operation(user_id: int,
                 amount: float,
                 curr_code: str,
                 operation: str) -> dict:
    """
    Функция для проведения торговых операций
    Допустимые операции (operation) buy и sell
    """

    # Загружаем данные портфелей
    portfolios_data = load_data_from(file_name="portfolios")
    id_index = -1
    wallets_dict = dict()
    wallets_data = dict()
    # Находим индекс портфеля в списке по user_id
    for num, ld in enumerate(portfolios_data):
        if str(ld["user_id"]) == str(user_id):
            id_index = num
            wallets_data = ld.get("wallets")
    if id_index == -1:
        raise Exception()
    # Создаем список экземпляров кошельков
    for key, val in wallets_data.items():
        wallets_dict[key] = Wallet(currency_code=key,
                                   balance=val["balance"])
    # Создаем экземпляр портфеля с кошельками
    portfolio_example = Portfolio(
        user_id=user_id,
        wallets=wallets_dict
    )
    # добавляем кошелек если при операции покупки такого кошелька нет
    if operation == "buy" and curr_code not in portfolio_example.wallets.keys():
        portfolio_example.add_currency(currency_code = curr_code)

    rates_data = load_data_from("rates")
    if not rates_data:
        ensure_rates_if_missing()
        rates_data = load_data_from("rates")
    exchange_rates = rates_data.get('pairs')
    base_val_code = "USD"

    code_rate_data = exchange_rates.get(
                        curr_code_union(curr_code,
                                        base_val_code))

    if curr_code == base_val_code:
        exchange_rate = 1
    else:
        exchange_rate = code_rate_data.get("rate", False)
        if not exchange_rate:
            raise Exception()

    actual_wallet = portfolio_example.get_wallet(curr_code)
    old_value = actual_wallet.balance
    if operation == "buy":
        actual_wallet.deposit(amount)
    if operation == "sell":
        actual_wallet.withdraw(amount)
    new_value = actual_wallet.balance

    base_curr_operation_value = apply_rate(amount, exchange_rate)

    wallets_data = dict()
    # Переводи кошельки в формат для сохранения в файл
    for key, wallet in portfolio_example.wallets.items():
        wallets_data[key] = {"balance" : wallet.balance}

    portfolios_data[id_index] = {"user_id": user_id, "wallets": wallets_data}
    save_data_in(file_name = "portfolios", input_data = portfolios_data)


    return {"old_value": old_value,
            "new_value": new_value,
            "base_curr_operation_value": base_curr_operation_value,
            "exchange_rate": (1/exchange_rate),
            "base_val_code": base_val_code}


def buy(user_id: int,
                 amount: float,
                 curr_code: str,
                 ) -> dict:
    """
    Функия покупки валюты. Обновляет кошелек при
    допустимых характеристиках операции и возращает
    данные связанные с операцией.
    """
    return trade_operation(user_id = user_id,
                           amount = amount,
                           curr_code = curr_code,
                           operation = "buy")

def sell(user_id: int,
                 amount: float,
                 curr_code: str,
                 ) -> dict:
    """
    Функия продажи валюты. Обновляет кошелек при
    допустимых характеристиках операции и возращает
    данные связанные с операцией.
    """
    return trade_operation(user_id = user_id,
                           amount = amount,
                           curr_code = curr_code,
                           operation = "sell")


