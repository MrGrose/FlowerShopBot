from datetime import date, time
# from bot.models import Order
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.types import LabeledPrice, PreCheckoutQuery
from environs import Env
import bot.requests as rq
import bot.keyboards as kb
from bot.keyboards import filter_bouquets, items, confirm_phone_keyboard
from aiogram import Bot
import re
from bot.requests import get_category_item
router = Router()


# Состояния
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
    await callback.message.answer("Возврат в каталог.", reply_markup=kb.main_menu)


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
# reset_state()
# Сбросить состояние пользователя в чате. Вы можете использовать этот метод для завершения разговоров.


@router.message(F.text == "Посмотреть всю коллекцию")
async def catalog(message: Message, state: FSMContext):
    await state.set_state(OrderState.choosing_occasion)
    await message.answer(
        "Давайте подберем букет.\n"
        "К какому событию готовимся? Выберите один из вариантов, либо укажите свой",
        reply_markup=await kb.categories())


@router.callback_query(F.data.startswith("category_"), OrderState.choosing_occasion)
async def choose_occasion(callback: CallbackQuery, state: FSMContext):
    occasion = callback.data.split("_")[1]
    await state.update_data(occasion=occasion)

    await state.set_state(OrderState.choosing_price)

    await callback.message.answer(
        "На какую сумму рассчитываете?",
        reply_markup=await kb.price()
    )


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
async def category(callback: CallbackQuery, state: FSMContext):
    item_data = await rq.get_item(callback.data.split("_")[1])

    await state.update_data(
        item_price=item_data.price,
        item_photo=item_data.photo,
        item_name=item_data.name,
    )
    await state.set_state(OrderState.waiting_item_price)

    photo = FSInputFile(f"media/{item_data.photo}")
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


# 4000 0000 0000 0002 тестовая карта
async def send_invoice(message: Message, bot: Bot, state: FSMContext):

    env = Env()
    env.read_env()
    pay_token = env.str("PAY_TG_TOKEN")

    item_data = await state.get_data()
    price = item_data.get("item_price")
    item_id = item_data.get("occasion")
    # photo = item_data.get("item_photo")
    item_name = item_data.get("item_name")

    delivery_price = 500
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Оплата заказа # 1",
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
        # photo_url=f"D:/FlowerShopBot/FlowerShopProject/media/{photo}",
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
        new_order = await rq.create_order(
            user_id=message.from_user.id,
            item_id=user_data["occasion"],
            name=user_data["name"],
            address=user_data["address"],
            delivery_date=user_data['delivery_date'].isoformat(),
            delivery_time=user_data['delivery_time'].strftime('%H:%M')
        )
    except Exception as e:
        await message.answer("❌ Ошибка при создании заказа")
        print(f"Order ошибка: {e}")
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

    courier_message = (
        "🚨 Новый заказ!\n"
        f"🔢 Номер заказа: #{new_order.id}\n"
        f"📦 Адрес: {new_order.address}\n"
        f"📅 Дата: {user_data['delivery_date']}\n"
        f"⏰ Время: {user_data['delivery_time']}\n"
        f"👤 Клиент: {new_order.name}\n"
        # f"📞 Телефон: {user_data.get('phone', 'не указан')}"
    )

    await message.bot.send_message(
        chat_id=7956301673,
        text=courier_message
    )



@router.message(F.text == "Заказать консультацию")
async def consultation_1(message: Message, state: FSMContext):
    await message.answer("Укажите номер телефона, и наш флорист перезвонит вам в течение 20 минут")
    await state.set_state(OrderState.waiting_for_phone)


@router.message(OrderState.waiting_for_phone)
async def consultation(message: Message, state: FSMContext):
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
    # TODO: Если пользователь выбрал Подтвердить Доделать логику, что выводить потом!!!!!!!!!


@router.callback_query(F.data == 'edit_phone', OrderState.confrim_for_phone)
async def edit_phone(callback: CallbackQuery, state: FSMContext):
    await state.update_data(phone=None)
    await callback.message.answer('Введите номер!')
    await state.set_state(OrderState.waiting_for_phone)
    await callback.answer()


@router.message(F.text == "Посмотреть всю коллекцию")
async def collection(message: Message, state: FSMContext):
    data = await state.get_data()
    occasion = data.get("occasion")

    all_items = await get_category_item(occasion)

    if all_items:
        keyboard = await items(all_items)
        await message.answer("Все букеты по выбранному событию:", reply_markup=keyboard)
    else:
        await message.answer("Букетов по данному событию нет.")


# TODO: Логика кнопок Без повода
# TODO: Логика кнопок Другой повод с подменю, где бот просит написать “какой повод”.