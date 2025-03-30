import datetime
import json
import logging
import re
from datetime import date, time

import bot.keyboards as kb
import bot.requests as rq
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, ErrorEvent, FSInputFile,
                           InlineKeyboardMarkup, LabeledPrice, Message,
                           PreCheckoutQuery)
from asgiref.sync import sync_to_async
from bot.keyboards import (confirm_phone_keyboard, create_courier_keyboard,
                           create_florist_keyboard, filter_bouquets,
                           for_another_reason, items)
from bot.models import CourierDelivery, Florist, FloristCallback, FSMData, Item
from bot.requests import get_all_items, get_category_item
from environs import Env

logging.basicConfig(
    format="[%(asctime)s] - %(levelname)s - %(funcName)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
router = Router()

ITEMS_PER_PAGE = 3


class OrderState(StatesGroup):
    choosing_occasion = State()
    choosing_price = State()
    waiting_for_name = State()
    waiting_for_address = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_phone = State()
    confrim_for_phone = State()
    waiting_item_price = State()
    waiting_consultation_1 = State()
    viewing_all_items = State()
    current_page = State()


@router.errors()
async def error_handler(event: ErrorEvent):
    error = event.exception
    logger.error(f"Произошла ошибка: {error}")

    message = event.update.message
    if not message:
        return

    error_message = "❌ Произошла ошибка. Попробуйте снова позже."
    if isinstance(error, FileNotFoundError):
        error_message = "❌ Файл не найден."
    elif isinstance(error, ValueError):
        error_message = "❌ Некорректный ввод данных."
    elif isinstance(error, KeyError):
        error_message = "❌ Ошибка состояния. Попробуйте снова."
    elif isinstance(error, TimeoutError):
        error_message = "❌ Превышено время ожидания ответа от сервера."
    elif isinstance(error, TelegramAPIError):
        error_message = "❌ Ошибка Telegram API. Попробуйте позже."     
    try:
        await message.answer(error_message)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")


async def show_welcome_message(message: Message, state: FSMContext):
    await message.answer(
        "Привет! 👋 Добро пожаловать в магазин цветов 'FlowerShop'."
        "Закажите доставку праздничного букета, собранного специально для ваших любимых, "
        "родных и коллег. Наш букет со смыслом станет главным подарком на вашем празднике!"
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
    await rq.set_user(message.from_user.id)
    fsm_data = await sync_to_async(
        FSMData.objects.filter(user_id=message.from_user.id).first)()

    if fsm_data and fsm_data.state:
        await message.answer(
            "Обнаружен незавершенный диалог. Хотите продолжить или начать заново?",
            reply_markup=kb.choice_continue_or_restart()
        )
    else:
        await show_welcome_message(message, state)


@router.callback_query(F.data == "restart")
async def restart_dialog(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_welcome_message(callback.message, state)


@router.callback_query(F.data == "continue")
async def continue_dialog(callback: CallbackQuery, state: FSMContext):
    fsm_data = await sync_to_async(
        FSMData.objects.filter(user_id=callback.from_user.id).first)()

    if not fsm_data:
        await callback.message.answer("Нет сохраненных данных для продолжения.")
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
        await callback.message.answer("Пожалуйста, введите имя получателя:")
    elif current_state == OrderState.waiting_for_address.state:
        await callback.message.answer("Пожалуйста, введите адрес доставки:")
    elif current_state == OrderState.waiting_for_date.state:
        await callback.message.answer("Пожалуйста, введите дату доставки:")
    elif current_state == OrderState.waiting_for_time.state:
        await callback.message.answer("Пожалуйста, введите время доставки:")
    elif current_state == OrderState.waiting_for_phone.state:
        await callback.message.answer("Пожалуйста, введите номер телефона:")
    elif current_state == OrderState.confrim_for_phone.state:
        phone = data.get('phone', 'Не указан')
        await callback.message.answer(
            f"Подтвердите или измените номер телефона: {phone}",
            reply_markup=kb.confirm_phone_keyboard())
    elif current_state == OrderState.waiting_item_price.state:
        await callback.message.answer(
            "На какую сумму рассчитываете?",
            reply_markup=await kb.price())
    elif current_state == OrderState.waiting_consultation_1.state:
        await callback.message.answer(
            "Заказать консультацию",
            reply_markup=kb.continue_consult)
    elif current_state == OrderState.viewing_all_items.state:
        await callback.message.answer(
            "Вы просматриваете все букеты. Хотите что-то еще более уникальное?\n"
            "Подберите другой букет из нашей коллекции или закажите консультацию флориста",
            reply_markup=kb.for_another_reason()
        )

    else:
        await callback.message.answer("Продолжаем с каталога.")
        await catalog(callback.message, state)   


# Вынос отдельно в папку2
async def save_fsm_data(user_id: int, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()
    logger.info(f"Сохраняемые данные: {data}")
    serialized_data = {}

    for key, value in data.items():
        if isinstance(value, (date, time)):
            serialized_data[key] = value.isoformat()
        elif isinstance(value, list):  # Если это список объектов Django ORM
            serialized_data[key] = [
                {
                    "id": item.id,
                    "name": item.name,
                    "price": float(item.price)
                }
                for item in value
            ]
        elif hasattr(value, "_state"):  # Если это объект Django ORM
            serialized_data[key] = {
                "id": value.id,
                "name": value.name,
                "price": float(value.price)
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


# Вынос отдельно в папку2
async def load_fsm_data(user_id: int, state: FSMContext):
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

            await state.set_data(data)

        except (TypeError, json.JSONDecodeError):
            await state.set_data({})


async def reconstruct_item(item_dict: dict):
    item = await sync_to_async(Item.objects.get)(pk=item_dict['id'])
    return item


@router.callback_query(F.data == "to_main")
async def to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Возврат в каталог.", reply_markup=kb.main_menu)


@router.message(F.text == "Принять")
async def event_form(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    await message.answer(
        "Спасибо! Вы приняли условия обработки персональных данных. "
    )
    await catalog(message, state)


@router.message(F.text == "Отказаться")
async def not_event_form(message: Message, state: FSMContext):
    await message.answer(
        "Вы отказались от обработки персональных данных. "
        "Чтобы начать заново, используйте команду /start.")

    await state.clear()  # завершение состояния и возврат к /start


@router.message(F.text == "Каталог")
async def catalog(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    await state.set_state(OrderState.choosing_occasion)
    await message.answer(
        "Давайте подберем букет.\n"
        "К какому событию готовимся? Выберите один из вариантов, либо укажите свой",
        reply_markup=await kb.categories())


@router.callback_query(F.data.startswith("category_"),
                       OrderState.choosing_occasion)
async def choose_occasion(callback: CallbackQuery, state: FSMContext):
    occasion = callback.data.split("_")[1]
    await state.update_data(occasion=occasion)

    if occasion == '5':
        await handle_no_reason(callback, state)
    elif occasion == '6':
        await handle_another_reason(callback, state)
    else:
        await handle_regular_reason(callback, state)

    await save_fsm_data(callback.from_user.id, state)


async def handle_no_reason(callback: CallbackQuery, state: FSMContext):
    all_items = await get_all_items()
    if not all_items:
        await callback.message.answer("Доступных букетов нет")
        return

    await state.set_state(OrderState.viewing_all_items)
    await state.update_data(filtered_items=all_items)    # Сохраняем все букеты в состояние
    await state.update_data(current_page=1)              # Инициализируем текущую страницу
    await display_bouquets(callback, state)
    await save_fsm_data(callback.from_user.id, state)


# Блок для выноса в п.1
async def handle_another_reason(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Выберите доступный вариант:", reply_markup=for_another_reason())
    await state.set_state(OrderState.waiting_consultation_1)
    await save_fsm_data(callback.from_user.id, state)


# Блок для выноса в п.1
async def handle_regular_reason(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.choosing_price)
    await callback.message.answer(
        "На какую сумму рассчитываете?",
        reply_markup=await kb.price()
    )

    await save_fsm_data(callback.from_user.id, state)


@router.callback_query(F.data.startswith("price_"), OrderState.choosing_price)
async def choose_price(callback: CallbackQuery, state: FSMContext):
    price = callback.data.split("_")[1]
    await state.update_data(price=price)
    data = await state.get_data()
    occasion = data.get("occasion")
    price = data.get("price")
    filtered_items = await filter_bouquets(occasion, price)
    if not filtered_items:
        await callback.message.answer("К сожалению, подходящих букетов не найдено.")
        return

    await state.set_state(OrderState.viewing_all_items)     # Переключаем в состояние просмотра
    await state.update_data(filtered_items=filtered_items)  # Сохраняем отфильтрованные букеты
    await state.update_data(current_page=1)                 # Начинаем с первой страницы
    await display_bouquets(callback, state)                 # Отображаем букеты
    await save_fsm_data(callback.from_user.id, state)


@router.callback_query(F.data.startswith("item_"))
async def category(callback: CallbackQuery, state: FSMContext):
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


async def display_bouquets(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    all_items = data.get("filtered_items")      # Получаем отфильтрованные элементы
    current_page = data.get("current_page", 1)  # Получаем текущую страницу
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

    # Создаем кнопки "Назад" и "Вперед"
    total_pages = (len(all_items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    navigation_buttons = kb.create_pagination_buttons(
        current_page,
        total_pages
    )   # клавиатуру с кнопками пагинации

    # Добавляем информацию о текущей странице
    page_info = f"Страница {current_page} из {total_pages}"
    await callback.message.edit_text(
        f"Доступные букеты:\n{page_info}", 
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=(
                keyboard.inline_keyboard + navigation_buttons.inline_keyboard)
            )
        )   # Объединяем клавиатуры


@router.callback_query(F.data.startswith("page_"), OrderState.viewing_all_items)
async def navigate_pages(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    await state.update_data(current_page=page)
    await display_bouquets(callback, state)
    await save_fsm_data(callback.from_user.id, state)


@router.message(F.text == "Заказать букет")
async def order(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    await message.answer("Введите имя получателя:")
    await state.set_state(OrderState.waiting_for_name)


@router.message(OrderState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    await state.update_data(name=message.text)
    await message.answer("Введите адрес доставки (например, г. Красноярск, ул. Сбоводы 5, кв.4):")
    await state.set_state(OrderState.waiting_for_address)


@router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    await state.update_data(address=message.text)
    await message.answer("Введите дату доставки (например, 2025-03-30):")
    await state.set_state(OrderState.waiting_for_date)


@router.message(OrderState.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
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


@router.message(OrderState.waiting_for_time)
async def process_time(message: Message, state: FSMContext, bot: Bot):
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


async def send_invoice(message: Message, bot: Bot, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    # InvalidTokenError
    env = Env()
    env.read_env()
    pay_token = env.str("PAY_TG_TOKEN")

    item_data = await state.get_data()
    item_id = item_data.get('id', 0)
    price = item_data.get('item_price', 0)
    item_name = item_data.get('item_name', 'Букет')

    delivery_price = 500
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Оплата заказа",
        description=f"Букет: {item_name}",
        payload=f"order_{item_id}",
        provider_token=pay_token,
        currency="rub",
        prices=[
            LabeledPrice(label="Стоимость букета", amount=price*100),
            LabeledPrice(label="НДС", amount=-(int(price)/0.2)),
            LabeledPrice(label="Стоимость доставки", amount=(delivery_price*100)),
        ],
        # TODO: Сделать вывод картинки товара при оплате
        # photo_url="D:/FlowerShopBot/FlowerShopProject/media/image.webp",
        photo_size=100,
        photo_width=800,
        photo_height=450,
        protect_content=True,
        start_parameter="FlowerSh0pBot",
        request_timeout=30,
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext):
    user_data = await state.get_data()
    try:
        # TimeoutError
        new_order = await rq.create_order(
            user_id=message.from_user.id,
            item_id=user_data["occasion"],
            name=user_data["name"],
            address=user_data["address"],
            delivery_date=user_data['delivery_date'].isoformat(),
            delivery_time=user_data['delivery_time'].strftime('%H:%M')
        )
    except Exception:
        await message.answer("❌ Ошибка при создании заказа")
        return

    client_message = (
        f"Оплачено: {message.successful_payment.total_amount} "
        f"{message.successful_payment.currency}\n"
        f"✅ Заказ #{new_order.id} оформлен!\n"
        f"▪ Имя: {new_order.name}\n"
        f"▪ Адрес: {new_order.address}\n"
        f"▪ Дата доставки: {user_data['delivery_date']}\n"
        f"▪ Время: {user_data['delivery_time'].strftime('%H:%M')}\n"
        "Заказ передан курьеру"
    )
    await message.answer(client_message)

    courier = await rq.get_сourier()
    if courier:
        courier_delivery = await sync_to_async(
            CourierDelivery.objects.create)(
                courier=courier, order=new_order
            )

        courier_keyboard = create_courier_keyboard(courier_delivery.id)

        courier_message = (
            f">>>>{courier.name}\n"
            "🚨 Новый заказ!\n"
            f"🔢 Номер заказа: #{new_order.id}\n"
            f"📦 Адрес: {new_order.address}\n"
            f"📅 Дата: {user_data['delivery_date']}\n"
            f"⏰ Время: {user_data['delivery_time']}\n"
            f"👤 Клиент: {new_order.name}\n"
        )

        await message.bot.send_message(
            chat_id=courier.tg_id,
            text=courier_message,
            reply_markup=courier_keyboard
        )
    else:
        await message.answer("Не удалось получить информацию о курьере.")

    await sync_to_async(FSMData.objects.filter(user_id=message.from_user.id).delete)()
    await state.clear()


@router.callback_query(F.data.startswith("delivered_"))
async def process_delivered(callback: CallbackQuery):
    courier_delivery_id = int(callback.data.split("_")[1])
    courier_delivery = await sync_to_async(CourierDelivery.objects.get)(id=courier_delivery_id)
    courier_delivery.delivered = True
    courier_delivery.delivered_at = datetime.datetime.now()
    await sync_to_async(courier_delivery.save)()
    await callback.message.answer("✅ Отмечено как доставленный!")


@router.message(F.text == "Заказать консультацию")
async def consultation_1(message: Message, state: FSMContext):
    await state.set_state(OrderState.waiting_consultation_1)
    await save_fsm_data(message.from_user.id, state)
    await message.answer("Укажите номер телефона, и наш флорист перезвонит вам в течение 20 минут")
    await state.set_state(OrderState.waiting_for_phone)


@router.message(OrderState.waiting_for_phone)
async def consultation(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    phone = message.text.strip()

    if not re.match(r"^\+7\d{10}$|^8\d{10}$", phone):
        await message.answer("Номер введён некорректно, введите номер в формате +79199209292")
        return

    await state.update_data(phone=phone)

    await message.answer(
        f'Ваш номер телефоне - {phone}\n'
        f'Подтвердите его!',
        reply_markup=confirm_phone_keyboard()
        )

    await state.set_state(OrderState.confrim_for_phone)


@router.callback_query(F.data == 'confirm_phone', OrderState.confrim_for_phone)
async def confirm_phone(callback: CallbackQuery, state: FSMContext):
    confirm_data = await state.get_data()
    phone = confirm_data.get('phone')   

    await callback.message.answer(
        f'Ваш номер - {phone} \n'
        f'Наш флорист перезвонит вам в течение 20 минут'
    )
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


@router.callback_query(F.data.startswith("call_made_"))
async def process_call_made(callback: CallbackQuery):
    florist_callback_id = int(callback.data.split("_")[2])
    florist_callback = await sync_to_async(FloristCallback.objects.get)(id=florist_callback_id)
    florist_callback.callback_made = True
    await sync_to_async(florist_callback.save)()
    await callback.message.answer("✅ Отмечено как перезвонивший!")


@router.callback_query(F.data == 'edit_phone', OrderState.confrim_for_phone)
async def edit_phone(callback: CallbackQuery, state: FSMContext):
    await save_fsm_data(callback.from_user.id, state) 
    await state.update_data(phone=None)
    await callback.message.answer('Введите номер!')
    await state.set_state(OrderState.waiting_for_phone)
    await callback.answer()


@router.message(F.text == "Посмотреть всю коллекцию")
async def collection(message: Message, state: FSMContext):
    await save_fsm_data(message.from_user.id, state)
    data = await state.get_data()
    occasion = data.get("occasion")

    all_items = await get_category_item(occasion)

    if all_items:
        keyboard = await items(all_items)
        await message.answer("Все букеты по выбранному событию:", reply_markup=keyboard)
    else:
        await message.answer("Букетов по данному событию нет.")


@router.message()
async def unknown_message(message: Message):
    await message.answer("Неизвестная команда. Воспользуйтесь меню или командой /start", reply_markup=kb.main_menu)