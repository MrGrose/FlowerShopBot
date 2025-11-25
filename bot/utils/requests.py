from asgiref.sync import sync_to_async
from bot.models import User, Category, Item, Order, Courier
from typing import List, Dict, Any


@sync_to_async
def set_user(tg_id: int) -> None:
    """
    Создает или получает пользователя по Telegram ID.

    Args:
        tg_id (int): Telegram ID пользователя.
    """
    User.objects.get_or_create(tg_id=tg_id)


@sync_to_async
def get_categories() -> List[Category]:
    """
    Возвращает список всех категорий букетов.

    Returns:
        List[Category]: Список объектов категорий.
    """
    return list(Category.objects.all())


@sync_to_async
def get_category_item(category_id: int) -> List[Item]:
    """
    Возвращает список букетов для указанной категории.

    Args:
        category_id (int): ID категории.

    Returns:
        List[Item]: Список объектов букетов.
    """
    return list(Item.objects.filter(category_id=category_id))


@sync_to_async
def get_item(item_id: int) -> Dict[str, Any]:
    """
    Возвращает детализированную информацию о букете.

    Args:
        item_id (int): ID букета.

    Returns:
        Dict[str, Any]: Словарь с данными букета.
    """
    item = Item.objects.get(id=item_id)
    return {
        'id': item.id,
        'name': item.name,
        'description': item.description,
        'structure': item.structure,
        'price': item.price,
        'photo': item.photo.name if item.photo else None,
        'category_id': item.category.id if item.category else None
    }


@sync_to_async
def create_order(
    user_id: int,
    item_id: int,
    name: str,
    address: str,
    delivery_date: str,
    delivery_time: str
) -> Order:
    """
    Создает новый заказ.

    Args:
        user_id (int): Telegram ID пользователя.
        item_id (int): ID букета.
        name (str): Имя получателя.
        address (str): Адрес доставки.
        delivery_date (str): Дата доставки.
        delivery_time (str): Время доставки.

    Returns:
        Order: Объект созданного заказа.
    """
    user = User.objects.get(tg_id=user_id)
    item = Item.objects.get(id=item_id)
    return Order.objects.create(
        user=user,
        item=item,
        name=name,
        address=address,
        delivery_date=delivery_date,
        delivery_time=delivery_time
    )


@sync_to_async
def get_courier() -> Courier:
    """
    Возвращает курьера с ID=2.

    Returns:
        Courier: Объект курьера.
    """
    return Courier.objects.get(id=2)


@sync_to_async
def get_all_items() -> List[Item]:
    """
    Возвращает список всех доступных букетов.

    Returns:
        List[Item]: Список объектов букетов.
    """
    return list(Item.objects.all())