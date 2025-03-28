from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.requests import get_categories, get_category_item

# Показываем кнопки для подтверждения
form_button = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Принять")],
                                            [KeyboardButton(text="Отказаться")]],
                                  resize_keyboard=True,
                                  one_time_keyboard=True,
                                  input_field_placeholder="Выберите пункт меню...")


menu = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Заказать букет")],
                                     [KeyboardButton(text="Заказать консультацию")],
                                     [KeyboardButton(text="Посмотреть всю коллекцию")],],
                           resize_keyboard=True,
                           one_time_keyboard=True,
                           input_field_placeholder="Выберите пункт меню...")


# Фильтрация букетов
async def filter_bouquets(occasion: str, price: str):
    all_items = await get_category_item(occasion)
    filtered_items = []

    for item in all_items:
        if price == "~500" and item.price <= 500:
            filtered_items.append(item)
        elif price == "~1000" and item.price <= 1000:
            filtered_items.append(item)
        elif price == "~2000" and item.price <= 2000:
            filtered_items.append(item)
        elif price == "Больше" and item.price > 2000:
            filtered_items.append(item)
        elif price == "Не важно":
            filtered_items.append(item)

    return filtered_items


# TODO: реализовать возврат на главную
# Создание клавиатуры с букетами
async def items(filtered_items):
    keyboard = InlineKeyboardBuilder()
    for item in filtered_items:
        keyboard.add(InlineKeyboardButton(text=item.name, callback_data=f"item_{item.id}"))
    keyboard.add(InlineKeyboardButton(text="На главную", callback_data="to_main"))
    return keyboard.adjust(1).as_markup()


# TODO: реализовать возврат на главную
# Создание категорий
async def categories():
    all_categories = await get_categories()
    keyboard = InlineKeyboardBuilder()
    for category in all_categories:
        keyboard.add(InlineKeyboardButton(text=category.name, callback_data=f"category_{category.id}"))
    keyboard.add(InlineKeyboardButton(text="На главную", callback_data="to_main"))
    return keyboard.adjust(1).as_markup()


# TODO: реализовать возврат на главную
# Создание кнопок с ценой
async def price():
    prices = ["~500", "~1000", "~2000", "Больше", "Не важно"]
    keyboard = InlineKeyboardBuilder()
    for price in prices:
        keyboard.add(InlineKeyboardButton(text=price, callback_data=f"price_{price}"))
    keyboard.add(InlineKeyboardButton(text="На главную", callback_data="to_main"))
    return keyboard.adjust(1).as_markup()


def confirm_phone_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text='Подтвердить', callback_data='confirm_phone'))
    keyboard.add(InlineKeyboardButton(text='Изменить', callback_data='edit_phone'))
    return keyboard.adjust(2).as_markup()