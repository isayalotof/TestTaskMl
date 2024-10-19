# @ggggg_kkkkbot для корректной работы меню команд необходимо использовать этого бота
# в коде уже указан apikey, я оставил его на виду специально т.к это тестовое задание
import requests
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

API_KEY = '7579739811:AAF2LTZwsDsmh8e_PsL3SUaetpYxhgSgN0U'
bot = Bot(token=API_KEY)
dp = Dispatcher()

# Параметры торговли
CAPITAL = 100  # Начальный капитал в долларах
GRID_PARTS = 10  # Делим капитал на 10 частей
CAPITAL_PER_ORDER = CAPITAL / GRID_PARTS  # По 10 долларов на ордер
PURCHASE_THRESHOLD = 0.03  # Условия покупки: цена падает на 3%
SELL_THRESHOLD = 0.05  # Условия продажи: цена растет на 5%

# Структура состояния
class TradingAccount:
    def __init__(self, initial_balance):
        self.balance = initial_balance
        self.positions = {}  # Храним позиции для каждого актива

    def update_balance(self, amount):
        self.balance += amount

    def add_position(self, symbol, price, amount):
        if symbol not in self.positions:
            self.positions[symbol] = []
        self.positions[symbol].append({'buy_price': price, 'amount': amount})

    def get_positions(self, symbol):
        return self.positions.get(symbol, [])

    def remove_position(self, symbol, position):
        self.positions[symbol].remove(position)

# Инициализация торгового счета
accounts = TradingAccount(initial_balance=CAPITAL)

# Функции для взаимодействия с CoinGecko API
def fetch_top_assets(limit=10):
    """Получаем список активов с CoinGecko."""
    url = 'https://api.coingecko.com/api/v3/coins/markets'
    params = {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': limit, 'page': 1}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return [item['id'] for item in data]

def fetch_asset_price(asset_id):
    """Получаем текущую цену актива."""
    url = 'https://api.coingecko.com/api/v3/coins/markets'
    params = {'vs_currency': 'usd', 'ids': asset_id}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return float(data[0]['current_price'])

# Логика торговли
def buy_asset(account, asset_id, price):
    """Покупаем актив, если достаточно средств."""
    if account.balance >= CAPITAL_PER_ORDER:
        amount = CAPITAL_PER_ORDER / price
        account.add_position(asset_id, price, amount)
        account.update_balance(-CAPITAL_PER_ORDER)
        return f"Куплен {asset_id} по цене {price}. Остаток на счете: {account.balance:.2f}$."
    return "Недостаточно средств для покупки."

def sell_asset(account, asset_id, current_price):
    """Продаем актив, если его цена увеличилась на SELL_THRESHOLD."""
    positions = account.get_positions(asset_id)
    for position in positions:
        if current_price >= position['buy_price'] * (1 + SELL_THRESHOLD):
            sell_value = position['amount'] * current_price
            account.update_balance(sell_value)
            account.remove_position(asset_id, position)
            return f"Продан {asset_id} по цене {current_price}. Состояние счета: {account.balance:.2f}$."
    return None

# Создание инлайн-клавиатуры для выбора актива
def create_asset_selection_keyboard(assets):
    """Создаем клавиатуру для выбора актива."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for asset in assets:
        button = InlineKeyboardButton(text=asset.capitalize(), callback_data=f"trade_{asset}")
        keyboard.inline_keyboard.append([button])
    return keyboard

# Команды бота
@dp.message(Command("start"))
async def start(message: Message):
    """Запуск торгового бота. Выбор актива для торговли."""
    assets = fetch_top_assets()
    keyboard = create_asset_selection_keyboard(assets)
    await message.answer("Выберите актив для торговли:", reply_markup=keyboard)


@dp.callback_query(lambda callback_query: callback_query.data.startswith("trade_"))
async def handle_trade(callback_query: CallbackQuery):
    """Обработка выбора актива и моделирование торговли."""
    asset_id = callback_query.data.split("_")[1]
    await callback_query.answer(f"Вы выбрали {asset_id}. Получаем текущую цену...")

    price = fetch_asset_price(asset_id)
    await callback_query.message.answer(f"Текущая цена {asset_id}: {price}$. Начинаем торговлю по сеточной стратегии.")

    # Покупка актива
    buy_message = buy_asset(accounts, asset_id, price)
    await callback_query.message.answer(buy_message)

    # Продажа актива
    sell_message = sell_asset(accounts, asset_id, price)
    if sell_message:
        await callback_query.message.answer(sell_message)
    else:
        await callback_query.message.answer(f"Ждем роста цены для продажи {asset_id}.")


@dp.message(Command("balance"))
async def check_balance(message: Message):
    """Проверка текущего баланса."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Обновить баланс", callback_data="check_balance")]
    ])
    await message.answer(f"Текущий баланс: {accounts.balance:.2f}$.", reply_markup=keyboard)


@dp.callback_query(lambda callback_query: callback_query.data == "check_balance")
async def refresh_balance(callback_query: CallbackQuery):
    """Обновление информации о балансе."""
    await callback_query.answer("Обновляем баланс...")
    await callback_query.message.edit_text(f"Текущий баланс: {accounts.balance:.2f}$.")


@dp.message(Command("price"))
async def get_price(message: Message):
    """Получение текущей цены для актива по его названию."""
    # Извлекаем символ актива из сообщения
    if len(message.text.split()) < 2:
        await message.answer("Пожалуйста, укажите символ актива. Пример: /price bitcoin")
        return

    asset_id = message.text.split()[1].lower()

    try:
        price = fetch_asset_price(asset_id)
        await message.answer(f"Текущая цена {asset_id.capitalize()}: {price}$.")
    except (IndexError, KeyError):
        await message.answer(f"Актив {asset_id} не найден. Проверьте правильность написания.")


@dp.message(Command("help"))
async def show_help(message: Message):
    """Отображение всех доступных команд."""
    help_text = (
        "Вот список команд, которые вы можете использовать:\n"
        "/start - Начать торговлю и выбрать актив.\n"
        "/balance - Проверить текущий баланс.\n"
        "/price <asset> - Узнать текущую цену актива.\n"
        "/help - Показать список доступных команд."
    )
    await message.answer(help_text)


# Запуск бота
async def main():
    """Запуск бота и начальная настройка."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
