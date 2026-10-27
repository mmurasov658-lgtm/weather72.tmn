
import asyncio
import aiohttp
import json
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

#  НАСТРОЙКИ 

TELEGRAM_TOKEN = "8753724027:AAGpfH2xbMMKFA9Q84R7vi6ymdsHjFhposs"
WEATHER_API_KEY = "249f12c4f7488f676b40dc7e73800491"

FAVORITES_FILE = "favorites.json"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Пользователи, которые сейчас вводят город
waiting_for_city = set()

#  КЛАВИАТУРЫ 

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🌤 Погода сейчас"),
            KeyboardButton(text="⭐ Избранное"),
        ],
        [
            KeyboardButton(text="➕ Добавить город"),
            KeyboardButton(text="🗑 Удалить город"),
        ],
    ],
    resize_keyboard=True,
)

# СОХРАНЕНИЕ ИЗБРАННОГО 

def load_favorites():
    if not os.path.exists(FAVORITES_FILE):
        return {}

    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


favorites = load_favorites()


def save_favorites():
    temp_file = FAVORITES_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(
            favorites,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(temp_file, FAVORITES_FILE)


def get_cities(user_id: int) -> list:
    return favorites.get(str(user_id), [])


def add_city(user_id: int, city: str) -> bool:
    user_key = str(user_id)
    cities = favorites.setdefault(user_key, [])

    if any(c.lower() == city.lower() for c in cities):
        return False

    if len(cities) >= 20:
        return False

    cities.append(city)
    save_favorites()
    return True


def remove_city(user_id: int, index: int):
    user_key = str(user_id)
    cities = favorites.get(user_key, [])

    if 0 <= index < len(cities):
        cities.pop(index)
        save_favorites()
        return True

    return False


#  ПОГОДА OPENWEATHERMAP 

async def get_weather(city: str) -> str:
    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "q": city,
        "appid": WEATHER_API_KEY,
        "units": "metric",
        "lang": "ru",
    }

    timeout = aiohttp.ClientTimeout(total=15)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:
        async with session.get(url, params=params) as response:
            data = await response.json()

            if response.status == 404:
                return "❌ Город не найден. Попробуй другое название."

            if response.status == 401:
                return "❌ Проверь API-ключ OpenWeatherMap."

            if response.status == 429:
                return "❌ Превышен лимит запросов к погодному API."

            if response.status != 200:
                return "❌ Ошибка сервиса погоды. Попробуй позже."

    city_name = data["name"]
    country = data.get("sys", {}).get("country", "")
    weather = data["weather"][0]
    main = data["main"]

    temp = main["temp"]
    feels = main["feels_like"]
    humidity = main["humidity"]
    wind = data.get("wind", {}).get("speed", 0) * 3.6
    description = weather["description"].capitalize()

    return (
        f"🌍 {city_name}, {country}\n\n"
        f"🌤 {description}\n"
        f"🌡 Температура: {temp} °C\n"
        f"🤔 Ощущается как: {feels} °C\n"
        f"💧 Влажность: {humidity}%\n"
        f"💨 Ветер: {wind:.1f} км/ч"
    )


#  КНОПКИ ИЗБРАННОГО 

def favorites_keyboard(user_id: int, delete_mode=False):
    cities = get_cities(user_id)
    rows = []

    for index, city in enumerate(cities):
        if delete_mode:
            text = f"🗑 {city}"
            action = f"delete:{index}"
        else:
            text = f"🌤 {city}"
            action = f"weather:{index}"

        rows.append([
            InlineKeyboardButton(
                text=text,
                callback_data=action,
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


#  КОМАНДЫ 

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Привет! 👋 Я бот погоды.\n\n"
        "Выбирай город кнопками, добавляй его в избранное "
        "и смотри погоду в пару кликов.\n\n"
        "⭐ Сохраняй до 20 любимых городов.",
        reply_markup=main_keyboard,
    )


@dp.message(Command("cancel"))
async def cancel(message: Message):
    waiting_for_city.discard(message.from_user.id)
    await message.answer(
        "Действие отменено.",
        reply_markup=main_keyboard,
    )


#  ПОКАЗ ИЗБРАННОГО 

async def show_favorites(message: Message):
    cities = get_cities(message.from_user.id)

    if not cities:
        await message.answer(
            "⭐ Избранное пока пустое.\n"
            "Нажми «➕ Добавить город», чтобы начать."
        )
        return

    await message.answer(
        "⭐ Выбери город, чтобы посмотреть погоду:",
        reply_markup=favorites_keyboard(message.from_user.id),
    )


async def show_delete_menu(message: Message):
    cities = get_cities(message.from_user.id)

    if not cities:
        await message.answer("Избранное пустое — удалять нечего.")
        return

    await message.answer(
        "🗑 Какой город удалить?",
        reply_markup=favorites_keyboard(
            message.from_user.id,
            delete_mode=True,
        ),
    )


#  ОБРАБОТКА КНОПОК 

@dp.message(F.text == "⭐ Избранное")
async def favorites_menu(message: Message):
    await show_favorites(message)


@dp.message(F.text == "🗑 Удалить город")
async def delete_menu(message: Message):
    await show_delete_menu(message)


@dp.message(F.text == "➕ Добавить город")
async def add_city_start(message: Message):
    waiting_for_city.add(message.from_user.id)

    await message.answer(
        "Напиши название города, который хочешь сохранить.\n"
        "Например: Вена\n\n"
        "Для отмены отправь /cancel."
    )


@dp.message(F.text == "🌤 Погода сейчас")
async def weather_menu(message: Message):
    cities = get_cities(message.from_user.id)

    if cities:
        await show_favorites(message)
    else:
        waiting_for_city.add(message.from_user.id)
        await message.answer(
            "Сначала добавь город в избранное "
            "или просто напиши его название."
        )


@dp.callback_query(F.data.startswith("weather:"))
async def favorite_weather(callback: CallbackQuery):
    try:
        index = int(callback.data.split(":")[1])
        cities = get_cities(callback.from_user.id)

        if not 0 <= index < len(cities):
            await callback.answer("Город не найден.", show_alert=True)
            return

        city = cities[index]
        await callback.answer()
        await callback.message.answer("🔎 Загружаю погоду...")

        result = await get_weather(city)
        await callback.message.answer(result)

    except (aiohttp.ClientError, asyncio.TimeoutError):
        await callback.message.answer(
            "❌ Ошибка соединения. Попробуй позже."
        )
    except (ValueError, KeyError, TypeError):
        await callback.message.answer(
            "❌ Не удалось обработать данные."
        )


@dp.callback_query(F.data.startswith("delete:"))
async def favorite_delete(callback: CallbackQuery):
    try:
        index = int(callback.data.split(":")[1])

        if remove_city(callback.from_user.id, index):
            await callback.answer("Город удалён!")
        else:
            await callback.answer("Город уже удалён.")

        cities = get_cities(callback.from_user.id)

        if cities:
            await callback.message.edit_reply_markup(
                reply_markup=favorites_keyboard(
                    callback.from_user.id,
                    delete_mode=True,
                )
            )
        else:
            await callback.message.edit_text(
                "⭐ Избранное теперь пустое."
            )

    except (ValueError, TypeError):
        await callback.answer("Не удалось удалить город.")


#  ОБЫЧНЫЕ СООБЩЕНИЯ 

@dp.message()
async def text_handler(message: Message):
    if not message.text:
        return

    city = message.text.strip()
    user_id = message.from_user.id

    #  «Добавить город»
    if user_id in waiting_for_city:
        waiting_for_city.discard(user_id)

        if city.startswith("/"):
            await message.answer(
                "Добавление отменено.",
                reply_markup=main_keyboard,
            )
            return

        if len(city) > 100:
            await message.answer("Название слишком длинное.")
            return

        try:
            result = await get_weather(city)

            if result.startswith("❌"):
                await message.answer(result)
                return

            # Сохраняю именно название, найденное API
            actual_city = result.splitlines()[0]
            actual_city = actual_city.replace("🌍 ", "")
            actual_city = actual_city.split(",")[0].strip()

            if add_city(user_id, actual_city):
                await message.answer(
                    f"⭐ Город «{actual_city}» добавлен в избранное!\n\n"
                    f"{result}",
                    reply_markup=main_keyboard,
                )
            else:
                await message.answer(
                    "Город уже сохранён или достигнут лимит "
                    "в 20 городов.",
                    reply_markup=main_keyboard,
                )

        except (aiohttp.ClientError, asyncio.TimeoutError):
            await message.answer(
                "❌ Ошибка соединения. Попробуй позже."
            )

        return

    
    if city.startswith("/"):
        return

    
    try:
        result = await get_weather(city)
        await message.answer(result, reply_markup=main_keyboard)

    except (aiohttp.ClientError, asyncio.TimeoutError):
        await message.answer("❌ Ошибка соединения. Попробуй позже.")


#  ЗАПУСК 

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
