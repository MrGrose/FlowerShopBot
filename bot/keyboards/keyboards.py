from aiogram.types import (
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.requests import get_categories, get_category_item

form_button = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Принять")],
              [KeyboardButton(text="Отказаться")]],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Выберите пункт меню..."
)


menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Заказать букет")],
              [KeyboardButton(text="Заказать консультацию")],
              [KeyboardButton(text="Посмотреть всю коллекцию")],],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Выберите пункт меню..."
)


main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Каталог")],],
    resize_keyboard=True,
    one_time_keyboard=True,
    input_field_placeholder="Выберите пункт меню..."
)

continue_button = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(
        text="Продолжить", callback_data="continue")]]
    )

continue_consult = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Заказать консультацию")],],
    resize_keyboard=True,
    one_time_keyboard=True
)


def create_florist_keyboard(florist_callback_id: int) -> InlineKeyboardMarkup:
    callback_data_call_made = f"call_made_{florist_callback_id}"
    call_made_button = InlineKeyboardButton(
        text="✅ Перезвонил",
        callback_data=callback_data_call_made
    )
    florist_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[call_made_button]]
    )
    return florist_keyboard


def create_courier_keyboard(courier_delivery_id: int) -> InlineKeyboardMarkup:
    callback_data_delivered = f"delivered_{courier_delivery_id}"
    delivered_button = InlineKeyboardButton(
        text="✅ Доставлено",
        callback_data=callback_data_delivered
    )
    courier_keyboard = InlineKeyboardMarkup(inline_keyboard=[[delivered_button]])
    return courier_keyboard


def create_pagination_buttons(
    current_page: int,
    total_pages: int
     ) -> InlineKeyboardMarkup:

    keyboard = []
    if current_page > 1:
        keyboard.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"page_{current_page - 1}")
        )
    if current_page < total_pages:
        keyboard.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"page_{current_page + 1}")
        )
    return InlineKeyboardMarkup(inline_keyboard=[keyboard])


def choice_continue_or_restart() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="continue")],
        [InlineKeyboardButton(text="Начать заново", callback_data="restart")]
    ])
    return keyboard


async def items(items: list) -> InlineKeyboardMarkup:
    keyboard = []
    for item in items:
        keyboard.append([InlineKeyboardButton(
            text=f"{item.name} - {item.price}р.",
            callback_data=f"item_{item.id}"
        )])
    keyboard.append([InlineKeyboardButton(
        text="В главное меню",
        callback_data="to_main")]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def categories() -> InlineKeyboardMarkup:
    all_categories = await get_categories()
    keyboard = InlineKeyboardBuilder()
    for category in all_categories:
        keyboard.add(InlineKeyboardButton(
            text=category.name,
            callback_data=f"category_{category.id}")
        )
    keyboard.add(InlineKeyboardButton(
        text="На главную",
        callback_data="to_main")
    )
    return keyboard.adjust(1).as_markup()


async def price() -> InlineKeyboardMarkup:
    prices = ["~500", "~1000", "~2000", "Больше", "Не важно"]
    keyboard = InlineKeyboardBuilder()
    for price in prices:
        keyboard.add(InlineKeyboardButton(
            text=price,
            callback_data=f"price_{price}")
        )
    keyboard.add(InlineKeyboardButton(
        text="На главную",
        callback_data="to_main")
    )
    return keyboard.adjust(1).as_markup()


async def confirm_phone_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(
        text='Подтвердить',
        callback_data='confirm_phone')
    )
    keyboard.add(InlineKeyboardButton(
        text='Изменить',
        callback_data='edit_phone')
    )
    return keyboard.adjust(2).as_markup()


async def for_another_reason() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Заказать консультацию")],
            [KeyboardButton(text="Каталог")]],
        resize_keyboard=True,
        one_time_keyboard=True)


async def filter_bouquets(occasion: str, price: str) -> list:
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