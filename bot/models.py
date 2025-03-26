from django.db import models
from django.utils import timezone


class User(models.Model):
    tg_id = models.BigIntegerField(unique=True)

    def __str__(self):
        return f"User {self.tg_id}"


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"Событие {self.name}"


class Item(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=120)
    price = models.IntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    structure = models.TextField(max_length=30)
    photo = models.ImageField(upload_to='bouquets/')

    def __str__(self):
        return f"{self.name} — {self.price}₽"


class Courier(models.Model):
    name = models.CharField(max_length=30)
    tg_id = models.BigIntegerField(unique=True)

    def __str__(self):
        return f'Курьер: {self.name}'


class Florist(models.Model):
    name = models.CharField(max_length=30)
    tg_id = models.BigIntegerField(unique=True)

    def __str__(self):
        return f'{self.name} Telegram ID: {self.tg_id}'


class Order(models.Model):
    user = models.CharField(max_length=30, null=True)
    item = models.CharField(max_length=30, null=True)
    name = models.CharField(max_length=30, null=True)
    address = models.CharField(max_length=50, null=True)
    data = models.DateField(default=timezone.now)
    delivery_time = models.TimeField(default=timezone.now)

    def __str__(self):
        return f"Заказ# {self.id} для {self.name}"
