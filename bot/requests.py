from asgiref.sync import sync_to_async
from bot.models import User, Category, Item, Order, Courier, Florist
from typing import List, Dict, Any

@sync_to_async
def set_user(tg_id: int) -> None:
    User.objects.get_or_create(tg_id=tg_id)


@sync_to_async
def get_categories() -> List[Category]:
    return list(Category.objects.all())


@sync_to_async
def get_category_item(category_id: int) -> List[Item]:
    return list(Item.objects.filter(category_id=category_id))


@sync_to_async
def get_item(item_id) -> Dict[str, Any]:
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
def create_order(user_id, item_id, name, address, delivery_date, delivery_time):
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
def get_сourier() -> int:
    return Courier.objects.get(id=2)


@sync_to_async
def get_all_items() -> List[Item]:
    return list(Item.objects.all())