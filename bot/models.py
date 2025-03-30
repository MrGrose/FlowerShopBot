import json
from datetime import date

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class User(models.Model):
    tg_id = models.BigIntegerField(unique=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.tg_id}"


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Событие"
        verbose_name_plural = "События"

    def __str__(self):
        return f"{self.name}"


class Item(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=120)
    price = models.FloatField()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True
    )
    structure = models.TextField(max_length=100)
    photo = models.ImageField(upload_to="bouquets/")

    class Meta:
        verbose_name = "Букет"
        verbose_name_plural = "Букеты"

    def __str__(self):
        return f"{self.name} — {self.price}₽"

    @property
    def photo_name(self):
        return self.photo.name if self.photo else None


class Courier(models.Model):
    name = models.CharField(max_length=30)
    tg_id = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=20, choices=[
        ("active", "Активен"),
        ("vacation", "В отпуске"),
        ("sick", "На больничном")
    ], default="active")
    assigned_orders = models.ManyToManyField(
        "Order",
        through="CourierAssignment",
        related_name="courier_assignments"
    )

    class Meta:
        verbose_name = "Курьер"
        verbose_name_plural = "Курьеры"

    def __str__(self):
        return f"Курьер: {self.name}"


class Florist(models.Model):
    name = models.CharField(max_length=30)
    tg_id = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=20, choices=[
        ("active", "Активен"),
        ("vacation", "В отпуске"),
        ("sick", "На больничном")
    ], default="active")
    assigned_orders = models.ManyToManyField(
        "Order",
        through="FloristAssignment"
    )

    class Meta:
        verbose_name = "Флорист"
        verbose_name_plural = "Флористы"

    def __str__(self):
        return f"Флорист {self.name}"


class Order(models.Model):
    status = models.CharField(max_length=20, choices=[
        ("new", "Новый"),
        ("in_work", "В работе"),
        ("delivered", "Доставлен"),
        ("canceled", "Отменен")
    ], default="new")

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=30, null=True)
    address = models.CharField(max_length=50, null=True)
    delivery_date = models.DateField(default=date.today)
    delivery_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.DurationField(null=True, blank=True)
    courier = models.ForeignKey(
        "Courier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"Заказ# {self.id} для {self.name}"


class FSMData(models.Model):
    user_id = models.IntegerField(primary_key=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    data = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"FSMData for user {self.user_id}"

    def get_data(self):
        return json.loads(self.data) if self.data else {}

    def set_data(self, value):
        self.data = json.dumps(value, ensure_ascii=False)


class CourierAssignment(models.Model):
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_time = models.DurationField(null=True, blank=True)


class FloristAssignment(models.Model):
    florist = models.ForeignKey(Florist, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.DurationField(null=True, blank=True)


class Owner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    can_assign = models.BooleanField(default=True)
    can_view_stats = models.BooleanField(default=True)


@receiver(post_save, sender=Order)
def assign_courier(sender, instance, created, **kwargs):
    if created:
        courier = Courier.objects.filter(status="active").first()
        if courier:
            CourierAssignment.objects.create(
                courier=courier,
                order=instance
            )
            instance.courier = courier
            instance.save()


class FloristCallback(models.Model):
    florist = models.ForeignKey(
        "Florist",
        on_delete=models.CASCADE,
        verbose_name="Флорист",
        null=True,
        blank=True
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        verbose_name="Заказ",
        null=True,
        blank=True
    )
    needs_callback = models.BooleanField(
        default=True,
        verbose_name="Требуется перезвонить"
    )
    callback_made = models.BooleanField(
        default=False,
        verbose_name="Перезвонил"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Номер телефона"
    )

    class Meta:
        verbose_name = "Звонок флориста"
        verbose_name_plural = "Звонки флористов"

    def __str__(self):
        return (
            f"Звонок для заказа {self.order.id if self.order else "Консультация"}"
            f"- {self.florist.name if self.florist else "Не назначен"}"
        )


class CourierDelivery(models.Model):
    courier = models.ForeignKey(
        "Courier",
        on_delete=models.CASCADE,
        verbose_name="Курьер"
    )
    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        verbose_name="Заказ"
    )
    delivered = models.BooleanField(default=False, verbose_name="Доставлено")
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время доставки"
    )

    class Meta:
        verbose_name = "Доставка курьера"
        verbose_name_plural = "Доставки курьеров"

    def __str__(self):
        return f"Доставка заказа {self.order.id} - {self.courier.name}, Доставлено: {self.delivered}"