from datetime import datetime


from valutatrade_hub.core.utils import (
    password_check,
    curr_code_union,
    password_changer
)



class Users:
    def __init__(self,
                 user_id: int,
                 username: str,
                 hashed_password: str,
                 salt: str,
                 registration_date: datetime
                 ):
        """Инициализируем нового пользователя"""
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # Методы ________________________________________________________
    def get_user_info(self) -> dict:
        """
        Получаем следующую информацию о пользователе,
        id, имя, дата регистрации
        """
        # Соль не добавляем так как это часть пароля
        return {"user_id": self._user_id,
                "username": self._username,
                "registration_date": self._registration_date.strftime(
                    "%Y-%m-%dT%H:%M:%S")}

    def change_password(self,
                        new_password: str) -> None:
        """
        Функция получает новый пароль в строковом
        формате, хеширует, и обновляет хешированные пароль
        и соль.
        """
        if isinstance(new_password, str) and len(new_password) > 3:
            self._hashed_password = password_changer(new_password, self._salt)
        else:
            raise Exception()

    def verify_password(self,
                        password: str) -> bool:
        """
        Метод проверяет введенный пароль на соответствие паролю аккаунта.
        """
        if isinstance(new_password, str) and len(new_password) > 3:
            return password_check(self._hashed_password, password, self._salt)
        else:
            raise Exception()


    # Геттеры _______________________________________________________
    @property
    def user_id(self):
        """получение user_id"""
        return self._user_id
    @property
    def salt(self):
        """получение соли"""
        return self._salt
    @property
    def hashed_password(self):
        """получение хеш-пароля"""
        return self._hashed_password
    @property
    def username(self):
        """получение имени пользователя"""
        return self._username
    @property
    def registration_date(self):
        """получение даты регистрации"""
        return self._registration_date

    # Сеттеры _______________________________________________________
    @username.setter
    def username(self, value: str):
        """установка имени пользователя"""
        if value.strip():
            self._username = value
        else:
            Exception()
    @registration_date.setter
    def registration_date(self, reg_data: datetime):
        """установка даты регистрации пользователя"""
        self._registration_date = reg_data



class Wallet:
    def __init__(self,
                currency_code: str,
                balance: float = 0.0
                ):
        self._currency_code = currency_code
        self._balance = balance

    # Методы ________________________________________________________

    def deposit(self, amount: float) -> None:
        """
        Пополнение кошелька на сумму amount
        """
        if amount > 0:
            self._balance = self._balance + amount

    def withdraw(self, amount: float) -> None:
        """
        Снятие с кошелька суммы
        amount, в случае не превышения
        суммы на кошельке
        """
        if self._balance >= amount and amount>0:
            self._balance = self._balance - amount
        else:
            raise Exception()

    def get_balance_info(self) -> dict:
        """
        Вывод информации о кошельке.
        """
        return {"currency_code" : self._currency_code,
                "balance" : self._balance}

    # Геттеры _______________________________________________________
    @property
    def balance(self):
        """получение баланса счета"""
        return self._balance

    @property
    def currency_code(self):
        """получение валютного кода кошелька"""
        return self._currency_code
    # Сеттеры _______________________________________________________
    @balance.setter
    def balance(self, value: float):
        """установка баланса счета"""
        if isinstance(value, (float, int)):
            if value >= 0:
                self._balance = value
            else:
                raise Exception(
                    message = "Баланс не должен быть отрицательным")

        else:
            raise Exception(field = "balance")

class Portfolio:
    def __init__(self,
                 user_id: int,
                 wallets: dict[str, Wallet],
                 user: Users = None
                 ):
        self._user_id = user_id
        self._wallets = wallets
        self._user = user
    # Методы ________________________________________________________
    def add_currency(self, currency_code: str) -> None:
        """
        добавить новый кошелек, выдаст ошибку
        в случае наличия кошелька для этой валюты
        """
        if currency_code in self._wallets:
            raise WalletsException(message="Данный кошелек уже существует")
        self._wallets[currency_code] = Wallet(currency_code=currency_code)


    def get_total_value(self,
                        base_currency: str = "USD",
                        settings_base_curr: str = "USD",
                        rates_pairs: dict = None) -> float:
        """
        Функция возращает сумму по всем кошелькам
        переведенную в выбранную валюту
        """
        if rates_pairs is None:
            return 0
        tot_sum = 0
        for k, w in self.wallets.items():
            if k == settings_base_curr:
                tot_sum += w.balance
            else:
                tot_sum += w.balance * (rates_pairs['pairs']
                [curr_code_union(k, settings_base_curr)]
                ["rate"])
        # переводим в выбранную базовою валюту
        if base_currency != settings_base_curr:
            tot_sum /= (rates_pairs['pairs']
                [curr_code_union(base_currency, settings_base_curr)]
                ["rate"])
        return tot_sum
    def get_wallet(self, currency_code: str) -> Wallet:
        """
        Возвращает кошелек по коду валюты.
        Если кошелька нет выдает ошибку.
        """
        if currency_code not in self._wallets:
            raise WalletsException(message = "Кошелька с таким кодом не существует")
        return self._wallets[currency_code]

    # Геттеры _______________________________________________________
    @property
    def user(self):
        """получение экземпляра пользователя"""
        return self._user
    @property
    def user_id(self):
        """Возвращает user_id портфеля"""
        return self._user_id
    @property
    def wallets(self):
        """Возвращает копию словаря кошельков"""
        return {**self._wallets}
