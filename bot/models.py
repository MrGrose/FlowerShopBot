from django.db import models
from datetime import date


class User(models.Model):
    tg_id = models.BigIntegerField(unique=True)

    def __str__(self):
        return f"{self.tg_id}"


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.name}'


class Item(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(max_length=120)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    structure = models.TextField(max_length=100)
    photo = models.ImageField(upload_to='bouquets/')
    photo_url = models.CharField(max_length=200, blank=True, null=True)

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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=30, null=True)
    address = models.CharField(max_length=50, null=True)
    delivery_date = models.DateField(default=date.today)
    delivery_time = models.TimeField()

    def __str__(self):
        return f"Заказ# {self.id} для {self.name}"
