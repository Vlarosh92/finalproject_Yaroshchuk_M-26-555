from datetime import datetime

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiClientsError,
    ApiRequestError,
    CacheCurrException,
    CacheExistException,
    CurrencyNotFoundError,
    PasswordAuthentificationException,
    PortfolioDontFindException,
    RatesExistValidationException,
    UserAuthentificationException,
    UserExistAuthentificationException,
    WalletsException,
)
from valutatrade_hub.core.models import Portfolio, Users, Wallet
from valutatrade_hub.core.utils import (
    apply_rate,
    curr_code_union,
    data_time_comprehension,
    password_creator,
)
from valutatrade_hub.decorators import log_action, memoize
from valutatrade_hub.infra.database import DataBaseManager
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import ApiStorageClass
from valutatrade_hub.parser_service.updater import RatesUpdater


def convert_currency(curr_code_base: str,
                     curr_code_convert: str,
                     ) -> float:
    """
    Функция конвертации курса базовой валюты
    к курсу конвертационной валюты
    """
    dbm = DataBaseManager()
    base_sys_code = SettingsLoader().get(key="base_currency")

    # проверяем если первая валюта является базовой приравниваем её курс к 1
    # иначе составляем пару и ищем в локальном кеше rates.json
    if curr_code_base == base_sys_code:
        rate_base = 1
    else:
        rate_base_code = curr_code_union(curr_code_base, base_sys_code)
        rate_base = dbm.get_rates()["pairs"][rate_base_code]['rate']

    # проверяем если вторая валюта является базовой приравниваем её курс к 1
    # иначе составляем пару и ищем в локальном кеше rates.json
    if curr_code_convert == base_sys_code:
        rate_conv = 1
    else:
        rate_conv_code = curr_code_union(curr_code_convert, base_sys_code)
        rate_conv = dbm.get_rates()["pairs"][rate_conv_code]['rate']

    return rate_base / rate_conv
@memoize
def portfolio_fun(user_id: int,
                       curr_base_code: str) -> tuple:
    """
    Функция получения данных по портфелю
    Возращает коды валют их баланс и
    сумма в пересчете к базовой валюте
    """
    dbm = DataBaseManager()
    user_data = dbm.get_user(user_id = str(user_id))

    portfolio_data = dbm.get_portfolios(user_id=str(user_id))

    wallets_dict = {}
    for code, data in portfolio_data.get("wallets").items():
        _wallet = Wallet(
            currency_code = code,
            balance = data.get("balance")
        )
        wallets_dict[code] = _wallet
    portfolio_data["wallets"] = wallets_dict

    curr_portfolio = Portfolio(
            **portfolio_data,
            user = Users(**user_data)
        )

    actual_wallets = curr_portfolio.wallets
    if not actual_wallets:
        raise WalletsException(message = "Отсутствуют кошельки в портфеле")

    exchange_rates = dbm.get_rates()


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


@log_action("LOGIN")
def login_account(username: str,
                  password: str) -> dict:
    """Проверяем соответствие пароля пользователю"""

    dbm = DataBaseManager()
    all_user = dbm.get_user()

    data_user = False

    for us in all_user:
        if us.get('username') == username:
            data_user = us

    # если в бд не нашлось пользователя с таким именем
    if not data_user:
        raise UserAuthentificationException(field = username)

    # информация для логгирования
    log_mass = ""
    log_mass += f"username: {username} "
    if not Users(**data_user).verify_password(password):
        raise PasswordAuthentificationException
    return {"result": data_user.get("user_id"),
            "log_info": log_mass}

def change_password(password: str,
                    user_id: int) -> None:
    """Функция смены пароля пользователя"""


    dbm = DataBaseManager()
    data_user = dbm.get_user(user_id = str(user_id))


    _user = Users(**data_user)
    _user.change_password(password)

    users_data = dbm.get_user()
    for du in users_data:
        if du["user_id"] == _user.user_id:
            du['hashed_password'] = _user.hashed_password
            break
    dbm.save_user(new_data=users_data, full_save = True)

@log_action("REGISTER")
def register_new_account(username: str,
                         password: str) -> dict:
    """Функция регистрации нового аккаунта"""

    dbm = DataBaseManager()
    # Загружаем данные из users.json
    # Если файла нет отдаем пустой список
    data_user = dbm.get_user()
    user_name_list = [du['username'] for du in data_user]

    # Если уже зарегистрирован такой пользователь
    if username in user_name_list:
        raise UserExistAuthentificationException(field = username)

    data_portfolios = dbm.get_portfolios()
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
    dbm.save_user(new_data = new_users_data, full_save = True)
    dbm.save_portfolios(new_data = new_portfolio_data, full_save = True)

    # информация для логгирования
    log_mass = ""
    log_mass += f"username: {user.username} "
    log_mass += f"user_id: {user.user_id} "
    log_mass += (f"registration_date: "
                 f"{user.registration_date.strftime("%Y-%m-%dT%H:%M:%S")} ")

    return {"result":max_id, "log_info":log_mass}
def get_rate(curr_from: str,
             curr_to: str
             ) -> tuple:
    """
    Функция получения курса валют.
    Проверяет последнее время обновления,
    при устаревании данных обновляет.
    """
    sl = SettingsLoader()
    dbm = DataBaseManager()
    # получаем множество допустимых валют из config.json
    currency_code_set = set(sl.get(key="supported_currency"))

    # получаем базовую системную валюту из config.json
    base_val_code = sl.get(key="base_currency")

    # загружаем данные по курсам и время последнего обновления
    exc_rates = dbm.get_rates()
    rates = exc_rates.get('pairs')
    last_refresh = exc_rates.get('last_refresh')

    # валидируем данные вводимых валют к допустимым
    if curr_from not in currency_code_set:
        CurrencyNotFoundError(field = curr_from)
    if curr_to not in currency_code_set:
        CurrencyNotFoundError(field = curr_to)

    # проверяем время последнего обновления валют
    # при вводе базовой валюты берет для сравнения last_refresh
    if curr_from !=base_val_code:
        rates_updated_at_from = rates.get(
            curr_code_union(curr_from, base_val_code)
        ).get('updated_at', False)
        if not rates_updated_at_from:
            raise RatesExistValidationException(
                field_currency_1= curr_from,
                field_currency_2= curr_to
            )
    else:
        rates_updated_at_from = last_refresh
    if curr_to != base_val_code:
        rates_updated_at_to = rates.get(
            curr_code_union(curr_to, base_val_code)
        ).get('updated_at', False)
        if not rates_updated_at_from:
            raise RatesExistValidationException(
                field_currency_1=curr_from,
                field_currency_2=curr_to
            )
    else:
        rates_updated_at_to = last_refresh


    # получаем срок допустимого устаревания данных
    ttl_seconds = sl.get(key="rates_ttl_seconds")

    # получаем свежесть последнего обновления
    time_delta_from = data_time_comprehension(time_str_1 = rates_updated_at_from)
    time_delta_to = data_time_comprehension(time_str_1 = rates_updated_at_to)

    # если данные старые обновляем
    if time_delta_from > ttl_seconds or time_delta_to > ttl_seconds:
        try:
            build_rates_updater().run_update()
        except ApiRequestError as e:
            raise e
    # получаем конвертированный курс
    convert_rate = convert_currency(curr_from, curr_to)

    return convert_rate, last_refresh
def trade_operation(user_id: int,
                 amount: int | float,
                 curr_code: str,
                 operation: str) -> dict:
    """
    Функция для проведения торговых операций
    Допустимые операции (operation) buy и sell
    """
    # Загружаем данные портфелей
    dbm = DataBaseManager()
    portfolios_data = dbm.get_portfolios()
    id_index = -1
    wallets_dict = dict()
    wallets_data = dict()
    # Находим индекс портфеля в списке по user_id
    for num, ld in enumerate(portfolios_data):
        if str(ld["user_id"]) == str(user_id):
            id_index = num
            wallets_data = ld.get("wallets")
    if id_index == -1:
        raise PortfolioDontFindException(field = str(user_id))
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

    # загружаем курсы валют из локального хранилища
    rates_data = dbm.get_rates()

    exchange_rates = rates_data.get('pairs')
    # получаем код базовой валюты и курс
    base_val_code = SettingsLoader().get(key="base_currency")
    code_rate_data = exchange_rates.get(
                        curr_code_union(curr_code,
                                        base_val_code))
    # если операция происходит с базовой валютой, то курс равен 1
    if curr_code == base_val_code:
        exchange_rate = 1
    else:
        exchange_rate = code_rate_data.get("rate", False)
        if not exchange_rate:
            raise RatesExistValidationException(
                field_currency_1= curr_code,
                field_currency_2= base_val_code
            )
    # получаем кошелёк
    actual_wallet = portfolio_example.get_wallet(curr_code)
    old_value = actual_wallet.balance
    # производим торговую операцию
    if operation == "buy":
        actual_wallet.deposit(amount)
    if operation == "sell":
        actual_wallet.withdraw(amount)
    # получаем новое значение баланса кошелька
    new_value = actual_wallet.balance
    base_curr_operation_value = apply_rate(amount, exchange_rate)


    # Переводи кошельки в формат для сохранения в файл
    wallets_data = dict()
    for key, wallet in portfolio_example.wallets.items():
        wallets_data[key] = {"balance" : wallet.balance}
    # сохраняем портфель
    portfolios_data[id_index] = {"user_id": user_id, "wallets": wallets_data}
    dbm.save_portfolios(new_data = portfolios_data, full_save = True)


    # очищаем кеш
    portfolio_fun.clear()
    show_rates_fun.clear()
    # информация для логирования
    log_mass = ""
    user_data = dbm.get_user(user_id = str(user_id))
    log_mass += f"user=\'{user_data.get('username')}\' "
    log_mass += f"currency='{curr_code}' "
    log_mass += f"amount='{amount}' "
    log_mass += f"rate='{exchange_rate}' "
    log_mass += f"base='{base_val_code}' "
    log_mass_verbose = "Balance before (" + str(old_value)
    log_mass_verbose += ") -> after (" + str(new_value) +") "
    return {"old_value": old_value,
            "new_value": new_value,
            "base_curr_operation_value": base_curr_operation_value,
            "exchange_rate": (1/exchange_rate),
            "base_val_code": base_val_code,
            "log_info": log_mass,
            "log_info_verbose": log_mass_verbose}

@log_action("BUY", verbose = True)
def buy(user_id: int,
                 amount: int | float,
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
@log_action("SELL")
def sell(user_id: int,
                 amount: int | float,
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

def build_rates_updater(source: str | None = None) -> RatesUpdater:
    """Функция создания RatesUpdater для заданного источника source"""
    db = DataBaseManager()
    api_storage = ApiStorageClass(db=db)
    # получаем список всех клиентов
    api_client_list = [
        CoinGeckoClient(),
        ExchangeRateApiClient()
    ]

    if source is not None:
        # Устанавливаем конкретный источник
        api_client_list = [cls
                           for cls in api_client_list
                           if source == cls.source]

        if not api_client_list:
            raise ApiClientsError(field = source)
    # очищаем кеш
    portfolio_fun.clear()
    show_rates_fun.clear()

    return RatesUpdater(
        api_clients=api_client_list,
        storage_class=api_storage
    )

@memoize
def show_rates_fun(filtered_key: str = "",
                   curr_code: str = None,
                   convert_code: str = None,
                   top_n: int = 0
                   ) -> list:
    """
    Функция возврата курсов валют с возможностью фильтрации
    через команды (filtered_key), а также с
    опциональным приведением к указанной валюте(convert_code)
    по актуальному курсу. Возвращаем результат фильтрации и время
    последнего обновления в локальном кеше.
    """
    dbm = DataBaseManager()
    base_val_code =  get_currency(code = SettingsLoader().get(key="base_currency"))
    rates_dict = dbm.get_rates()
    if not rates_dict:
        raise CacheExistException

    pairs = rates_dict["pairs"]

    # Фильтруем по коду валюты
    if filtered_key == "currency":
        if (curr_code_union(curr_code, base_val_code.code)
                not in rates_dict.get("pairs")
                and curr_code != base_val_code.code):
            raise CacheCurrException(field=base_val_code.code)
        filtered_rates = [(curr_code_union(curr_code, convert_code),
                           convert_currency(curr_code_base = curr_code,
                                            curr_code_convert = convert_code),
                           #updated at берется по первой валюте
                           pairs.get(
                               curr_code_union(curr_code, base_val_code.code)
                           ).get("updated_at")
                           ),
                          ]

        return filtered_rates

    # Фильтруем топ криптовалют по top_n самых дорогих
    if filtered_key == "top":

        filtered_rates = {(curr_code_union(k.replace("_"+base_val_code.code, ""),
                                           convert_code),
                           convert_currency(
                               curr_code_base = k.replace("_"+base_val_code.code, ""),
                               curr_code_convert = convert_code),

                          v.get("updated_at")
                           )
                          for k, v in pairs.items()
                          if k.replace("_"+base_val_code.code, "")
                          in ParserConfig.CRYPTO_CURRENCIES}
        # Сортировка по курсу с ограничением по top_n
        sorted_rates = sorted(filtered_rates,
                              key=lambda x: x[1],
                              reverse=True)[:top_n]

        return sorted_rates


    # если фильтры не указаны возвращаем все
    converted_rates = [(curr_code_union(
                                k.replace("_"+base_val_code.code, ""),
                                convert_code),
                        convert_currency(
                                curr_code_base=k.replace(
                                    "_"+base_val_code.code, ""),
                                curr_code_convert=convert_code),
                        v.get("updated_at")
                        )
                      for k, v in pairs.items()]
    # Сортировка по алфавиту
    sorted_rates = sorted(converted_rates,
                          key=lambda x: x[0],
                          reverse=False)

    # Меняем курс выбранной валютной базы к себе самой
    # на курс системно базовой валюты к выбранной валюте
    base_correction = []
    for num, it in enumerate(sorted_rates):
        split_rate = it[0].split("_")
        if split_rate[0] == split_rate[1]:
            base_correction.append(curr_code_union(
                                        base_val_code.code,
                                        split_rate[0]))
            base_correction.append(convert_currency(
                curr_code_base = base_val_code.code,
                curr_code_convert = split_rate[0]
            ))
            base_correction.append(it[2])
            sorted_rates[num] = tuple(base_correction)
    return sorted_rates








