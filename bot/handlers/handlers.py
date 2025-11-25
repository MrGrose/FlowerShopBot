import json
import logging
import re
from datetime import date, time
from decimal import Decimal

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramUnauthorizedError,
)
from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    ErrorEvent,
    FSInputFile,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery
)
from asgiref.sync import sync_to_async

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.utils import timezone

import bot.keyboards.keyboards as kb
import bot.utils.requests as rq

from bot.models import CourierDelivery, Florist, FloristCallback, FSMData, Item
from bot.utils.requests import get_all_items, get_category_item
from bot.keyboards.keyboards import (
    confirm_phone_keyboard,
    create_courier_keyboard,
    create_florist_keyboard,
    create_pagination_buttons,
    filter_bouquets,
    for_another_reason,
    items
)


logging.basicConfig(
    format="[%(asctime)s] - %(levelname)s - %(funcName)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

router = Router()

ITEMS_PER_PAGE = 3


class ResponseFormatError(Exception):
    """Ошибка формата данных"""
    pass


class ServerError(Exception):
    """Ошибка сервера"""
    pass


class OrderState(StatesGroup):
    """Состояния для управления заказами."""
    choosing_occasion = State()
    choosing_price = State()
    waiting_for_name = State()
    waiting_for_address = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_phone = State()
    confrim_for_phone = State()
    waiting_item_price = State()
    waiting_consultation = State()
    viewing_all_items = State()
    current_page = State()


@router.errors()
async def error_handler(event: ErrorEvent) -> None:
    """Обрабатывает ошибки, возникающие во время выполнения запросов.

    Args:
        event (ErrorEvent): Событие ошибки, которое произошло.
    """
    error = event.exception
    logger.error("Произошла ошибка: %s", error, exc_info=True)

    message = event.update.message
    if not message:
        return

    error_message = "❌ Произошла неизвестная ошибка. Пожалуйста, обратитесь к разработчикам."

    if isinstance(error, TelegramBadRequest):
        error_message = "❌ Ошибка: пользователь не найден. Проверьте данные и попробуйте снова."

    elif isinstance(error, TelegramUnauthorizedError):
        error_message = "❌ Ошибка: бот заблокирован пользователем."

    elif isinstance(error, ResponseFormatError):
        error_message = "❌ Ошибка формата данных. Проверьте корректность данных."

    elif isinstance(error, ServerError):
        error_message = "❌ Ошибка на стороне сервера. Попробуйте позже."

    elif isinstance(error, (ValueError, KeyError)):
        error_message = "❌ Некорректные данные."

    elif isinstance(error, TimeoutError):
        error_message = "❌ Превышено время ожидания ответа."
    try:
        await event.update.message.answer(error_message)
    except Exception as e:
        logger.error("Ошибка отправки сообщения: %s", e)


async def show_welcome_message(message: Message) -> None:
    """Отправляет приветственное сообщение пользователю.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await message.answer(
        "Привет! 👋 Добро пожаловать в магазин цветов 'FlowerShop'."
        "Закажите доставку праздничного букета, собранного специально для ваших любимых, "
        "родных и коллег.\nНаш букет со смыслом станет главным подарком на вашем празднике!"
        "Для продолжения работы с ботом необходимо дать согласие на обработку персональных данных."
    )

    pdf_file = "form.pdf"
    try:
        await message.answer_document(FSInputFile(pdf_file))
    except FileNotFoundError:
        await message.answer(
            "Файл с соглашением не найден. Пожалуйста, попробуйте позже."
        )
    await message.answer(
        "После ознакомления с документом выберите действие:\n\n"
        "✅ Нажмите 'Принять', чтобы продолжить пользоваться услугами нашего сервиса.\n\n"
        "⚠️ Нажимая 'Принять', я подтверждаю своё согласие на обработку персональных данных.",
        reply_markup=kb.form_button
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обрабатывает команду `/start`.

    Обрабатывает также восстанавливает состояние после остановки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await rq.set_user(message.from_user.id)
    fsm_data = await sync_to_async(
        FSMData.objects.filter(user_id=message.from_user.id).first)()

    if fsm_data and fsm_data.state:
        await message.answer(
            "Обнаружен незавершенный диалог. Продолжить?",
            reply_markup=kb.choice_continue_or_restart()
        )
    else:
        await show_welcome_message(message)


@router.callback_query(F.data == "restart")
async def restart_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    """Перезапускает диалог, очищая состояние и отправляя приветственное сообщение.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()
    await show_welcome_message(callback.message)


@router.callback_query(F.data == "continue")
async def continue_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    """Восстановление на предыдущий диалог.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    fsm_data = await sync_to_async(
        FSMData.objects.filter(user_id=callback.from_user.id).first)()

    if not fsm_data:
        await callback.message.answer("❌ Нет данных для продолжения.")
        await state.clear()
        return

    await state.set_state(fsm_data.state)

    try:
        data = json.loads(fsm_data.data)
        await state.set_data(data)
    except (TypeError, json.JSONDecodeError):
        data = {}

    current_state = await state.get_state()

    if current_state == OrderState.choosing_occasion.state:
        await callback.message.answer(
            "Давайте подберем букет.\n"
            "К какому событию готовимся? Выберите один из вариантов, либо укажите свой",
            reply_markup=await kb.categories())

    elif current_state == OrderState.choosing_price.state:
        await callback.message.answer(
            "На какую сумму рассчитываете?",
            reply_markup=await kb.price())

    elif current_state == OrderState.waiting_for_name.state:
        await callback.message.answer("Введите имя получателя:")
    elif current_state == OrderState.waiting_for_address.state:
        await callback.message.answer("Введите адрес доставки:")
    elif current_state == OrderState.waiting_for_date.state:
        await callback.message.answer("Введите дату доставки (ГГГГ-ММ-ДД):")
    elif current_state == OrderState.waiting_for_time.state:
        await callback.message.answer("Введите время доставки (ЧЧ:ММ):")
    elif current_state == OrderState.waiting_for_phone.state:
        await callback.message.answer("Введите номер телефона:")
    elif current_state == OrderState.confrim_for_phone.state:
        phone = data.get('phone', 'Не указан')
        await callback.message.answer(
            f"Подтвердите или измените номер телефона: {phone}",
            reply_markup=await kb.confirm_phone_keyboard())
    elif current_state == OrderState.waiting_item_price.state:
        await callback.message.answer(
            "На какую сумму рассчитываете?",
            reply_markup=await kb.price())
    elif current_state == OrderState.waiting_consultation.state:
        await callback.message.answer(
            "Заказать консультацию",
            reply_markup=await kb.continue_consult)
    elif current_state == OrderState.viewing_all_items.state:
        await callback.message.answer(
            "Вы просматриваете все букеты. Хотите что-то еще более уникальное?\n"
            "Подберите другой букет из нашей коллекции или закажите консультацию флориста",
            reply_markup=await kb.for_another_reason()
        )

    else:
        await callback.message.answer("Продолжаем с каталога.")
        await catalog(callback.message, state)   


async def save_fsm_data(user_id: int, state: FSMContext) -> None:
    """Сохраняет состояние FSM в базу данных.

    Args:
        user_id (int): Telegram ID пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:
        current_state = await state.get_state()
        data = await state.get_data()
        serialized_data = {}

        for key, value in data.items():
            if isinstance(value, (date, time)):
                serialized_data[key] = value.isoformat()
            elif isinstance(value, Decimal):
                serialized_data[key] = float(value)
            elif isinstance(value, list):
                serialized_data[key] = [
                    {
                        "id": getattr(item, 'id', None),
                        "name": getattr(item, 'name', None),
                        "price": float
                        (getattr(item, 'price', 0.0)) if isinstance(
                            getattr(item, 'price', None), (int, float)
                        ) else 0.0
                    }
                    for item in value
                ]
            elif isinstance(value, dict):
                serialized_data[key] = {
                    "id": value.get('id', None),
                    "name": value.get('name', None),
                    "price": float(value.get(
                        'price', 0.0)) if isinstance(
                            value.get('price'), (int, float)
                        ) else 0.0
                }
            else:
                serialized_data[key] = value

        await sync_to_async(FSMData.objects.update_or_create)(
            user_id=user_id,
            defaults={
                'state': current_state,
                'data': json.dumps(serialized_data, ensure_ascii=False)
            }
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния: {str(e)}")
        raise


async def load_fsm_data(user_id: int, state: FSMContext) -> None:
    """Загружает состояние FSM из базы данных.

    Args:
        user_id (int): Telegram ID пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:
        fsm_data = await sync_to_async(
            FSMData.objects.filter(user_id=user_id).first
        )()
        logger.info(f"Загружаемые данные из FSM: {fsm_data}")
        if fsm_data:
            await state.set_state(fsm_data.state)

            try:
                data = json.loads(fsm_data.data)

                for key, value in data.items():
                    if isinstance(value, list) and key == 'filtered_items':
                        data[key] = [
                            await sync_to_async(Item.objects.get)(id=item_dict["id"])
                            for item_dict in value
                        ]
                    elif isinstance(value, dict) and "id" in value:
                        data[key] = await sync_to_async(Item.objects.get)(id=value["id"])
                    elif isinstance(value, (int, float)):
                        data[key] = Decimal(str(value))
                await state.set_data(data)

            except (TypeError, json.JSONDecodeError) as e:
                logger.error("Ошибка декодирования JSON: %s", str(e))
                await state.set_data({})
    except ObjectDoesNotExist as e:
        logger.error("Объект не найден: %s", str(e))
        await state.set_data({})
    except Exception as e:
        logger.error("Ошибка при загрузке данных: %s", str(e), exc_info=True)
        raise


async def reconstruct_item(item_dict: dict) -> Item:
    """Восстанавливает объект товара по его словарному представлению.

    Args:
        item_dict (dict): Словарь с информацией о товаре.

    Returns:
        Item: Объект товара из базы данных.
    """
    try:
        item = await sync_to_async(Item.objects.get)(pk=item_dict['id'])
        return item
    except ObjectDoesNotExist:
        logger.error("Товар с id=%s не существует", item_dict['id'])
        raise ResponseFormatError("Некорректные данные товара")


@router.callback_query(F.data == "to_main")
async def to_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Возвращает пользователя в главный каталог.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()
    await callback.message.answer(
        "Возврат в каталог.",
        reply_markup=kb.main_menu
    )


@router.message(F.text == "Принять")
async def event_form(message: Message, state: FSMContext) -> None:
    """Обрабатывает нажатие кнопки 'Принять' пользователем.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await save_fsm_data(message.from_user.id, state)
    await message.answer("✅ Соглашение принято!")
    await catalog(message, state)


@router.message(F.text == "Отказаться")
async def not_event_form(message: Message, state: FSMContext) -> None:
    """Обрабатывает нажатие кнопки 'Отказаться' пользователем.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await message.answer(
        "Вы отказались от обработки персональных данных. "
        "Чтобы начать заново, используйте команду /start.")

    await state.clear()


@router.message(F.text == "Каталог")
async def catalog(message: Message, state: FSMContext) -> None:
    """Показ категорий букетов.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await save_fsm_data(message.from_user.id, state)
    await state.set_state(OrderState.choosing_occasion)
    await message.answer(
        "Давайте подберем букет.\n"
        "К какому событию готовимся? "
        "Выберите один из вариантов, либо укажите свой",
        reply_markup=await kb.categories())


@router.callback_query(
    F.data.startswith("category_"),
    OrderState.choosing_occasion,
)
async def choose_occasion(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор события для букета.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    occasion = callback.data.split("_")[1]
    await state.update_data(occasion=occasion)

    if occasion == '5':
        await handle_no_reason(callback, state)
    elif occasion == '6':
        await handle_another_reason(callback, state)
    else:
        await handle_regular_reason(callback, state)

    await save_fsm_data(callback.from_user.id, state)


async def handle_no_reason(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает случай, когда пользователь не выбрал конкретное событие.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    all_items = await get_all_items()
    if not all_items:
        await callback.message.answer("Доступных букетов нет")
        return

    await state.set_state(OrderState.viewing_all_items)
    await state.update_data(filtered_items=all_items)
    await state.update_data(current_page=1)
    await display_bouquets(callback, state)
    await save_fsm_data(callback.from_user.id, state)


async def handle_another_reason(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает случай, когда пользователь выбирает консультацию.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await callback.message.answer(
        "Выберите доступный вариант:",
        reply_markup=for_another_reason()
    )
    await state.set_state(OrderState.waiting_consultation)
    await save_fsm_data(callback.from_user.id, state)


async def handle_regular_reason(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает обычный случай выбора события.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await state.set_state(OrderState.choosing_price)
    await callback.message.answer(
        "На какую сумму рассчитываете?",
        reply_markup=await kb.price()
    )

    await save_fsm_data(callback.from_user.id, state)


@router.callback_query(F.data.startswith("price_"), OrderState.choosing_price)
async def choose_price(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор цены для букета.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    price = callback.data.split("_")[1]
    await state.update_data(price=price)
    data = await state.get_data()
    occasion = data.get("occasion")
    price = data.get("price")
    filtered_items = await filter_bouquets(occasion, price)
    if not filtered_items:
        await callback.message.answer("К сожалению, подходящих букетов не найдено.")
        return

    await state.set_state(OrderState.viewing_all_items)
    await state.update_data(filtered_items=filtered_items)
    await state.update_data(current_page=1)
    await display_bouquets(callback, state)
    await save_fsm_data(callback.from_user.id, state)


@router.callback_query(F.data.startswith("item_"))
async def category(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор товара.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:
        item_id = callback.data.split("_")[1]
        item_data = await rq.get_item(item_id)

        await state.update_data(
            item_price=item_data['price'],
            item_photo=item_data['photo'],
            item_name=item_data['name'],
            occasion=item_data['category_id']
        )

        await save_fsm_data(callback.from_user.id, state)
        await state.set_state(OrderState.waiting_item_price)

        photo_path = f"media/{item_data['photo']}" if item_data['photo'] else None
        if photo_path:
            photo = FSInputFile(photo_path)
        else:
            await callback.message.answer("Фото букета недоступно.")

        await callback.message.answer_photo(photo=photo)
        await callback.answer(f"Вы выбрали товар {item_data['name']}")
        await callback.message.answer(
            f"*Букет:* {item_data['name']}\n"
            f"*Описание:* {item_data['description']}\n"
            f"*Цветочный состав:* {item_data['structure']}\n"
            f"*Цена:* {item_data['price']}р.",
            parse_mode="Markdown"
        )
        await callback.message.answer(
            "*Хотите что-то еще более уникальное?*\n"
            "*Подберите другой букет из нашей коллекции или закажите консультацию флориста*",
            parse_mode="Markdown",
            reply_markup=kb.menu
            )
    except Exception as e:
        logger.error(f"Ошибка загрузки товара: {str(e)}")
        await callback.answer("❌ Ошибка при загрузке данных, попробуйте позже.")


async def display_bouquets(callback: CallbackQuery, state: FSMContext) -> None:
    """Отображение букетов с пагинацией.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    all_items = data.get("filtered_items")
    current_page = data.get("current_page", 1)
    if not all_items:
        await callback.message.answer("Нет доступных букетов.")
        return

    start_index = (current_page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    items_on_page = all_items[start_index:end_index]

    if not items_on_page:
        await callback.message.answer("Нет букетов на этой странице.")
        return

    keyboard = await items(items_on_page)

    total_pages = (len(all_items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    navigation_buttons = kb.create_pagination_buttons(
        current_page,
        total_pages
    )

    page_info = f"Страница {current_page} из {total_pages}"
    await callback.message.edit_text(
        f"Доступные букеты:\n{page_info}", 
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=(
                keyboard.inline_keyboard + navigation_buttons.inline_keyboard)
            )
        )


@router.callback_query(F.data.startswith("page_"), OrderState.viewing_all_items)
async def navigate_pages(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает навигацию между страницами товаров.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    page = int(callback.data.split("_")[1])
    await state.update_data(current_page=page)
    await display_bouquets(callback, state)
    await save_fsm_data(callback.from_user.id, state)


@router.message(F.text == "Заказать букет")
async def order(message: Message, state: FSMContext) -> None:
    """Начинает процесс заказа букета.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await save_fsm_data(message.from_user.id, state)
    await message.answer("Введите имя получателя:")
    await state.set_state(OrderState.waiting_for_name)


@router.message(OrderState.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    """Обрабатывает введение имени получателя.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    name = message.text.strip()
    if re.match(r'^[А-Яа-яA-Za-z]{2,}$', name):
        await state.update_data(name=name)
        await message.answer(
            "📍 Укажите адрес, куда доставить букет "
            "(например, г. Красноярск, ул. Ленина, д. 15):"
        )
        await state.set_state(OrderState.waiting_for_address)
    else:
        await message.answer("⚠️ Пожалуйста, введите корректное имя (только буквы, не менее 2 символов).")

    await save_fsm_data(message.from_user.id, state)


@router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext) -> None:
    """Обрабатывает введение адреса доставки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """

    adress_pattern = re.compile(
        r"^(г\.\s*[А-Яа-яЁё\- ]+,\s*"
        r"(ул\.|улица|просп\.|проспект|пр-т)\s*[А-Яа-яЁё\- ]+,\s*"
        r"(д\.|дом)\s*\d+[А-Яа-я]*(,\s*(кв\.|квартира)\s*\d+)?$)"
    )

    address = message.text.strip()
    example_address = (
        "Примеры корректных адресов:\n"
        "• г. Москва, ул. Ленина, д. 15\n"
        "• г. Санкт-Петербург, Невский проспект, дом 25/3, кв. 10"
    )

    errors = []

    if not address.startswith("г. "):
        errors.append("Адрес должен начинаться с указания города (г. Москва)")

    if "ул." not in address and "улица" not in address:
        errors.append("Укажите улицу (ул. Ленина или улица Ленина)")

    if "д." not in address and "дом" not in address:
        errors.append("Укажите номер дома (д. 10 или дом 15)")

    if errors:
        error_message = "❌ Обнаружены ошибки:\n" + "\n".join(f"- {e}" for e in errors)
        await message.answer(f"{error_message}\n\n{example_address}")
        return

    if not adress_pattern.match(address):
        await message.answer(
            f"❌ Некорректный формат адреса.\n\n{example_address}"
        )
        return

    await state.update_data(address=address)
    await message.answer("✅ Адрес принят! Введите дату доставки (ГГГГ-ММ-ДД):")
    await state.set_state(OrderState.waiting_for_date)


@router.message(OrderState.waiting_for_date)
async def process_date(message: Message, state: FSMContext) -> None:
    """Обрабатывает введение даты доставки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:
        await save_fsm_data(message.from_user.id, state)
        if not message.text:
            await message.answer("Введите дату в формате ГГГГ-ММ-ДД:")
            return

        try:
            delivery_date = date.fromisoformat(message.text.strip())
            if delivery_date < date.today():
                await message.answer("❌ Дата не может быть в прошлом!")
                return
        except ValueError:
            await message.answer("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД.")
            return

        await state.update_data(delivery_date=delivery_date)
        await message.answer("Введите время доставки (например, 14:00):")
        await state.set_state(OrderState.waiting_for_time)
    except Exception as e:
        logger.error(f"Ошибка обработки даты: {str(e)}")
        await message.answer("❌ Ошибка при обработке даты!")


@router.message(OrderState.waiting_for_time)
async def process_time(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает введение времени доставки.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
        bot (Bot): Экземпляр бота.
    """
    await save_fsm_data(message.from_user.id, state)
    if not message.text:
        await message.answer("⌛ Введите время в формате ЧЧ:ММ (например, 14:00):")
        return

    user_input = message.text.strip()

    try:
        if len(user_input) != 5 or user_input[2] != ":":
            raise ValueError

        hours, minutes = map(int, user_input.split(":"))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError

        delivery_time = time(hours, minutes)

    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:00).")
        return

    await state.update_data(delivery_time=delivery_time)
    await send_invoice(message, bot, state)
    await state.set_state(None)


async def send_invoice(message: Message, bot: Bot, state: FSMContext) -> None:
    """Отправляет счет-фактуру пользователю для оплаты.

    Args:
        message (Message): Сообщение от пользователя.
        bot (Bot): Экземпляр бота.
        state (FSMContext): Контекст состояния.
    """
    try:
        await save_fsm_data(message.from_user.id, state)
        data = await state.get_data()

        item = data.get("occasion")
        if not item:
            await message.answer("❌ Ошибка: товар не найден.")
            return

        prices = [
            LabeledPrice(label="Букет", amount=int(data["item_price"] * 100)),
            LabeledPrice(label="Доставка", amount=50000)
        ]

        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Оплата заказа",
            description=f"Букет: {data["item_name"]}",
            payload=f"order_{data["item_name"]}",
            provider_token=settings.PAY_TG_TOKEN,
            currency="rub",
            prices=prices,
            photo_url="https://cs11.pikabu.ru/post_img/2019/02/19/9/155058987464147624.jpg",
            photo_size=100,
            photo_width=800,
            photo_height=450,
            protect_content=True,
            start_parameter="flower_shop",
            request_timeout=30,
        )
    except TelegramBadRequest as e:
        logger.error("Ошибка Telegram API: %s", e)
        await message.answer("❌ Ошибка платежной системы. Попробуйте позже.")
    except Exception as e:
        logger.error("Неизвестная ошибка: %s", e)
        await message.answer("❌ Ошибка при создании платежа.")


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot) -> None:
    """Обрабатывает предварительный запрос на оплату.

    Args:
        pre_checkout_query (PreCheckoutQuery): Запрос на предварительную оплату.
        bot (Bot): Экземпляр бота.
    """
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext) -> None:
    """Обрабатывает успешную оплату.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:

        user_data = await state.get_data()

        required_fields = ["occasion", "name", "address", "delivery_date", "delivery_time"]
        for field in required_fields:
            if field not in user_data:
                raise KeyError(f"Отсутствует обязательное поле: {field}")

        delivery_date = (
            user_data["delivery_date"].isoformat() 
            if isinstance(user_data["delivery_date"], date)
            else str(user_data["delivery_date"])
        )

        delivery_time = (
            user_data["delivery_time"].strftime("%H:%M")
            if isinstance(user_data["delivery_time"], time)
            else str(user_data["delivery_time"])
        )

        new_order = await rq.create_order(
            user_id=message.from_user.id,
            item_id=user_data["occasion"],
            name=user_data["name"],
            address=user_data["address"],
            delivery_date=delivery_date,
            delivery_time=delivery_time
        )

        if not new_order or not hasattr(new_order, "id"):
            raise ValueError("Ошибка создания заказа")

        client_message = (
            f"Оплачено: {message.successful_payment.total_amount // 100} "
            f"{message.successful_payment.currency}\n"
            f"✅ Заказ #{new_order.id} оформлен!\n"
            f"▪ Имя: {new_order.name}\n"
            f"▪ Адрес: {new_order.address}\n"
            f"▪ Дата доставки: {delivery_date}\n"
            f"▪ Время: {delivery_time}\n"
            "Заказ передан курьеру"
        )
        await message.answer(client_message)

        try:
            courier = await rq.get_courier()
            if not courier:
                await message.answer("❌ Нет доступных курьеров.")
                return

            try:
                courier_delivery = await sync_to_async(CourierDelivery.objects.create)(
                    courier=courier, 
                    order=new_order
                )
            except IntegrityError as e:
                logger.error("Ошибка создания доставки: %s", e)
                await message.answer("❌ Ошибка при создании заказа.")
                return

            courier_keyboard = create_courier_keyboard(courier_delivery.id)
            courier_message = (
                f">>>>{courier.name}\n"
                "🚨 Новый заказ!\n"
                f"🔢 Номер заказа: #{new_order.id}\n"
                f"📦 Адрес: {new_order.address}\n"
                f"📅 Дата: {delivery_date}\n"
                f"⏰ Время: {delivery_time}\n"
                f"👤 Клиент: {new_order.name}\n"
            )
            try:
                await message.bot.send_message(
                    chat_id=courier.tg_id,
                    text=courier_message,
                    reply_markup=courier_keyboard
                )
            except TelegramBadRequest as e:
                logger.error("Ошибка отправки сообщения курьеру: %s", e)

        except Exception as e:
            logger.error("Ошибка назначения курьера: %s", e)
            await message.answer("❌ Ошибка при обработке заказа.")

        await sync_to_async(FSMData.objects.filter(
            user_id=message.from_user.id
        ).delete)()
        await state.clear()

    except KeyError as e:
        logger.error("Отсутствует ключ в данных: %s", e)
        await message.answer("❌ Ошибка данных заказа.")
    except ValueError as e:
        logger.error("Ошибка создания заказа: %s", e)
        await message.answer("❌ Ошибка при создании заказа.")
    except Exception as e:
        logger.error("Неизвестная ошибка: %s", e, exc_info=True)
        await message.answer("❌ Ошибка. Обратитесь в поддержку.")


@router.callback_query(F.data.startswith("delivered_"))
async def process_delivered(callback: CallbackQuery) -> None:
    """Обрабатывает пометку о доставке.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
    """
    courier_delivery_id = int(callback.data.split("_")[1])
    courier_delivery = await sync_to_async(CourierDelivery.objects.get)(id=courier_delivery_id)
    courier_delivery.delivered = True
    courier_delivery.delivered_at = timezone.now()
    await sync_to_async(courier_delivery.save)()
    await callback.message.answer("✅ Отмечено как доставленный!")


@router.message(F.text == "Заказать консультацию")
async def consultation_1(message: Message, state: FSMContext) -> None:
    """Начинает процесс заказа консультации.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await state.set_state(OrderState.waiting_consultation)
    await save_fsm_data(message.from_user.id, state)
    await message.answer(
        "📞 Укажите номер телефона (пример: +79161234567 или 89161234567),"
        "и наш флорист перезвонит вам в течение 20 минут"
    )
    await state.set_state(OrderState.waiting_for_phone)


@router.message(OrderState.waiting_for_phone)
async def consultation(message: Message, state: FSMContext) -> None:
    """Обрабатывает введение номера телефона для консультации.

    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await save_fsm_data(message.from_user.id, state)
    phone = message.text.strip()

    if not re.match(r"^(\+7|8)[\d\- ]{10,}$", phone):
        await message.answer("Номер введён некорректно, "
                             "введите номер в формате +79161234567 или 89161234567"
                             )
        return

    await state.update_data(phone=phone)

    await message.answer(
        f'📞 Ваш номер телефоне - {phone}\n'
        f'Подтвердите его!',
        reply_markup=await confirm_phone_keyboard()
        )

    await state.set_state(OrderState.confrim_for_phone)


@router.callback_query(F.data == 'confirm_phone', OrderState.confrim_for_phone)
async def confirm_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждает номер телефона пользователя.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    try:
        confirm_data = await state.get_data()
        phone = confirm_data.get('phone')   

        await callback.message.answer(
            f'📞 Ваш номер - {phone} \n'
            f'👤 Наш флорист перезвонит вам в течение 20 минут'
        )
        try:
            florist = await sync_to_async(Florist.objects.filter(status='active').first)()
            if florist:

                florist_callback = await sync_to_async(
                    FloristCallback.objects.create)(
                        phone_number=phone,
                        needs_callback=True,
                        order=None,
                        florist=florist
                )

                florist_keyboard = create_florist_keyboard(florist_callback.id)

                flourist_message = (
                    "Звонок клиенту:\n"
                    "🚨 Требуется консультация клиенту\n"
                    f"🔢 Номер тел: #{phone}"
                )

                await callback.bot.send_message(
                    chat_id=florist.tg_id,
                    text=flourist_message,
                    reply_markup=florist_keyboard
                )
            else:
                await callback.message.answer("К сожалению, в данный момент нет доступных флористов.")
        except IntegrityError:
            await callback.message.answer("❌ Ошибка при создании заявки!")
    except Exception as e:
        logger.error(f"Ошибка подтверждения телефона: {str(e)}")
        await callback.message.answer("❌ Ошибка при обработке запроса!")


@router.callback_query(F.data.startswith("call_made_"))
async def process_call_made(callback: CallbackQuery) -> None:
    """Обрабатывает пометку о том, что звонок сделан.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
    """
    try:
        florist_callback_id = int(callback.data.split("_")[2])
        florist_callback = await sync_to_async(FloristCallback.objects.get)(
            id=florist_callback_id
        )
        florist_callback.callback_made = True
        await sync_to_async(florist_callback.save)()
        await callback.message.answer("✅ Отмечено как перезвонивший!")
    except ObjectDoesNotExist:
        await callback.answer("❌ Запрос на звонок не найден!")
    except Exception as e:
        logger.error(f"Ошибка обработки звонка: {str(e)}")
        await callback.answer("❌ Ошибка при обновлении статуса!")


@router.callback_query(F.data == 'edit_phone', OrderState.confrim_for_phone)
async def edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Позволяет пользователю изменить введенный номер телефона.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await save_fsm_data(callback.from_user.id, state)
    await state.update_data(phone=None)
    await callback.message.answer('Введите номер!')
    await state.set_state(OrderState.waiting_for_phone)
    await callback.answer()


@router.message(F.text == "Посмотреть всю коллекцию")
async def collection(message: Message, state: FSMContext) -> None:
    """Предлагает пользователю посмотреть всю коллекцию букетов с пагинацией.
    Args:
        message (Message): Сообщение от пользователя.
        state (FSMContext): Контекст состояния.
    """
    await save_fsm_data(message.from_user.id, state)
    data = await state.get_data()
    occasion = data.get("occasion")

    all_items = await get_category_item(occasion)

    if not all_items:
        await message.answer("Букетов по данному событию нет.")
        return

    await state.update_data(
        filtered_items=all_items,
        current_page=1
    )

    items_on_page = all_items[:3]
    keyboard = await items(items_on_page)

    if len(all_items) > 3:
        total_pages = (len(all_items) + 2) // 3
        navigation_buttons = create_pagination_buttons(1, total_pages)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=(
                keyboard.inline_keyboard +
                navigation_buttons.inline_keyboard
            )
        )

    await message.answer(
        "Все букеты по выбранному событию:",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает навигацию по страницам.

    Args:
        callback (CallbackQuery): Callback-запрос от пользователя.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    all_items = data.get("filtered_items")
    current_page = data.get("current_page", 1)

    if not all_items:
        await callback.message.answer("Нет доступных букетов.")
        return

    if callback.data.startswith("page_"):
        new_page = int(callback.data.split("_")[1])
        await state.update_data(current_page=new_page)
        current_page = new_page

    start_index = (current_page - 1) * 3
    end_index = start_index + 3
    items_on_page = all_items[start_index:end_index]

    if not items_on_page:
        await callback.message.answer("Нет букетов на этой странице.")
        return

    keyboard = await items(items_on_page)
    total_pages = (len(all_items) + 2) // 3
    navigation_buttons = create_pagination_buttons(current_page, total_pages)

    page_info = f"Страница {current_page} из {total_pages}"
    await callback.message.edit_text(
        f"{page_info}\nВсе букеты по выбранному событию:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=(
                keyboard.inline_keyboard + 
                navigation_buttons.inline_keyboard
            )
        )
    )


@router.message()
async def unknown_message(message: Message) -> None:
    """Обрабатывает неизвестные сообщения от пользователя.

    Args:
        message (Message): Сообщение от пользователя.
    """
    await message.answer("Неизвестная команда. Воспользуйтесь меню или командой /start", reply_markup=kb.main_menu)