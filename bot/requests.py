from asgiref.sync import sync_to_async
from bot.models import User, Category, Item, Order, Courier


@sync_to_async
def set_user(tg_id):
    User.objects.get_or_create(tg_id=tg_id)


@sync_to_async
def get_categories():
    return list(Category.objects.all())


@sync_to_async
def get_category_item(category_id):
    return list(Item.objects.filter(category_id=category_id))


@sync_to_async
def get_item(item_id):
    return Item.objects.get(id=item_id)


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
def get_сourier():
    return list(Courier.objects.all())