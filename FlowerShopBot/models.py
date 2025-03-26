from django.db import models


class Customer(models.Model):
    tg_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=30)
    adress = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    
    def __str__(self):
        return f'{self.name} Telegram ID: {self.tg_id}'


class Florist(models.Model):
    tg_id = models.BigIntegerField(max_length=20)
    name = models.CharField(max_length=30)
    
    def __str__(self):
        return f'{self.name} Telegram ID: {self.tg_id}'


class Courier(models.Model):
    tg_id = models.BigIntegerField(max_length=20)
    name = models.CharField(max_length=30)
    phone = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f'Курьер: {self.name}'


class Bouquet(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=7, decimal_places=2)
    photo = models.ImageField(upload_to='bouquets/')
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} — {self.price}₽"
    
    
class Order(models.Model):
    
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('in_progress', 'В процессе'),
        ('done', 'Выполнен'),
        ('cancelled', 'Отменён'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    florist = models.ForeignKey(Florist, on_delete=models.SET_NULL, null=True, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    comment = models.TextField(blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    courier = models.ForeignKey(Courier, on_delete=models.SET_NULL, null=True, related_name='orders')

    
    def __str__(self):
        return f'Заказ #{self.id} - {self.customer.name} ({self.status})'
    
    