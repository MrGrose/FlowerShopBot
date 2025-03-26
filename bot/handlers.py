from datetime import date, time
from bot.models import Order
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.types import LabeledPrice, PreCheckoutQuery
from environs import Env
import bot.requests as rq
import bot.keyboards as kb
from bot.keyboards import filter_bouquets, items
from aiogram import Bot
router = Router()


# Состояния
class OrderState(StatesGroup):
    choosing_occasion = State()
    choosing_price = State()
    waiting_for_name = State()
    waiting_for_address = State()
    waiting_for_date = State()
    waiting_for_time = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await rq.set_user(message.from_user.id)
    await message.answer(
        "Привет! 👋 Добро пожаловать в магазин цветов 'FlowerShop'."
        "Закажите доставку праздничного букета, собранного специально для ваших любимых, "
        "родных и коллег. Наш букет со смыслом станет главным подарком на вашем празднике!"
        "Для продолжения работы с ботом необходимо дать согласие на обработку персональных данных."
    )
    pdf_file = "form.pdf"
    try:
        # Отправляем PDF-файл
        await message.answer_document(FSInputFile(pdf_file))
    except FileNotFoundError:
        await message.answer("Файл с соглашением не найден. Пожалуйста, попробуйте позже.")

    await message.answer(
        "После ознакомления с документом выберите действие:\n\n"
        "✅ Нажмите 'Принять', чтобы продолжить пользоваться услугами нашего сервиса.\n\n"

        "⚠️Нажимая 'Принять', я подтверждаю своё согласие на обработку персональных данных.",
        reply_markup=kb.form_button
    )

@router.callback_query(F.data == "to_main")
async def to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Возврат на главную.", reply_markup=kb.menu)


@router.message(F.text == "Принять")
async def event_form(message: Message, state: FSMContext):
    await message.answer(
        "Спасибо! Вы приняли условия обработки персональных данных. "
        "Теперь мы можем продолжить работу. 🛠️\n\n"
        "Выберите действие из меню ниже:"
    )
    await catalog(message, state)


@router.message(F.text == "Отказаться")
async def not_event_form(message: Message, state: FSMContext):
    await message.answer(
        "Вы отказались от обработки персональных данных. "
        "Чтобы начать заново, используйте команду /start."
    )
    await state.clear()     # завершение состояния и возврат к /start


# Каталог ["День Рождения", "Свадьба", "В школу", "Без повода", "Другой повод"]
@router.message(F.text == "Посмотреть всю коллекцию")
async def catalog(message: Message, state: FSMContext):
    await state.set_state(OrderState.choosing_occasion)
    await message.answer(
        "Давайте подберем букет.\n"
        "К какому событию готовимся? Выберите один из вариантов, либо укажите свой",
        reply_markup=await kb.categories())


# Обработка выбора повода
@router.callback_query(F.data.startswith("category_"), OrderState.choosing_occasion)
async def choose_occasion(callback: CallbackQuery, state: FSMContext):
    # Сохраняем выбранный повод
    occasion = callback.data.split("_")[1]
    await state.update_data(occasion=occasion)

    # Переходим к выбору суммы
    await state.set_state(OrderState.choosing_price)

    # Предлагаем выбрать сумму
    await callback.message.answer(
        "На какую сумму рассчитываете?",
        reply_markup=await kb.price()
    )


# Обработка выбора суммы
@router.callback_query(F.data.startswith("price_"), OrderState.choosing_price)
async def choose_price(callback: CallbackQuery, state: FSMContext):
    price = callback.data.split("_")[1]
    await state.update_data(price=price)

    data = await state.get_data()
    occasion = data.get("occasion")
    price = data.get("price")

    filtered_items = await filter_bouquets(occasion, price)

    if filtered_items:
        keyboard = await items(filtered_items)
        await callback.message.answer("Вот подходящие букеты:", reply_markup=keyboard)
    else:
        await callback.message.answer("К сожалению, подходящих букетов не найдено.")


@router.callback_query(F.data.startswith("item_"))
async def category(callback: CallbackQuery):
    item_data = await rq.get_item(callback.data.split("_")[1])

    # Отправляем фото
    photo = FSInputFile(f"media/bouquets/{item_data.id}.jpg")
    await callback.message.answer_photo(photo=photo)
    await callback.answer(f"Вы выбрали товар {item_data.name}")
    await callback.message.answer(f"*Букет:* {item_data.name}\n"
                                  f"*Описание:* {item_data.description}\n"
                                  f"*Цветочный состав:* {item_data.structure}\n"
                                  f"*Цена:* {item_data.price}р.",
                                  parse_mode="Markdown")
    await callback.message.answer(
        "*Хотите что-то еще более уникальное?*\n"
        "*Подберите другой букет из нашей коллекции или закажите консультацию флориста*",
        parse_mode="Markdown",
        reply_markup=kb.menu
        )


@router.message(F.text == "Заказать букет")
async def order(message: Message, state: FSMContext):
    await message.answer("Введите имя получателя:")
    await state.set_state(OrderState.waiting_for_name)


@router.message(OrderState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите адрес доставки:")
    await state.set_state(OrderState.waiting_for_address)


@router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text)
    await message.answer("Введите дату доставки (например, 2025-03-30):")
    await state.set_state(OrderState.waiting_for_date)


@router.message(OrderState.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Введите время доставки (например, 14:00):")
    await state.set_state(OrderState.waiting_for_time)


@router.message(OrderState.waiting_for_time)
async def process_time(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(time=message.text)
    user_data = await state.get_data()
    try:
        delivery_date = date.fromisoformat(user_data['date'])
        delivery_time = time.fromisoformat(user_data['time'])
        item_id = user_data['occasion']

        new_order = await rq.create_order(
            user_id=message.from_user.id,
            item_id=item_id,
            name=user_data['name'],
            address=user_data['address'],
            date=delivery_date,
            time=delivery_time
        )

        await send_invoice(message, bot, new_order)
    # TODO: Логика подцветки заказа и далее пустить оплату
    except KeyError as e:
        await message.answer(f"❌ Ошибка: не найдено поле {e}")
    except ValueError as e:
        await message.answer(f"❌ Неверный формат данных: {e}")
    except Exception as e:
        await message.answer("😢 Произошла ошибка. Попробуйте позже.")
        print(f"Error: {e}")

    await state.clear()


# TODO: Добавить передачу цены букета, который выбрал клиент
# 4000 0000 0000 0002 тестовая карта
async def send_invoice(message: Message, bot: Bot, order):
    print(f"[order] {order.id} {order.name} {order.address} {order.data} {order.delivery_time}")
    env = Env()
    env.read_env()
    pay_token = env.str("PAY_TG_TOKEN")

    await bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Оплата заказа #{order.id}",
        description="Оплата заказа через Telegram бота",
        payload=f"order_{order.id}",
        provider_token=pay_token,
        currency="rub",
        prices=[
            LabeledPrice(label="Стоимость заказа", amount=5000),
            LabeledPrice(label="НДС", amount=100)
        ],
        # photo_url="https://shtrih-m-nsk.ru/upload/medialibrary/4b3/kkt_shtrikh_mini_02f-_9_.jpg",
        photo_size=100,
        photo_width=800,
        photo_height=450,
        need_name=False,
        is_flexible=False,
        protect_content=True,
        request_timeout=30,
        start_parameter='time-machine-example',
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    print(f"[pre_checkout_query] {pre_checkout_query}")
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.content_type == "successful_payment")
async def process_successful_payment(message: Message):
    print(f"[message.successful_payment] {message.successful_payment}")
    msg = (f"Спасибо за оплату {message.successful_payment.total_amount}"
           f"{message.successful_payment.currency}\n"
           "Заказ передан курьеру")
    await message.answer(msg)


# TODO: Логика кнопок Без повода
# TODO: Логика кнопок Другой повод с подменю, где бот просит написать “какой повод”.

# TODO: Разработка. Заказать консультацию (кнопка)
@router.message(F.text == "Заказать консультацию")
async def consultation(message: Message):
    pass


# TODO: Посмотреть всю коллекцию (кнопка)
@router.message(F.text == "Посмотреть всю коллекцию")
async def collection(message: Message):
    await catalog(message, None)
