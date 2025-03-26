from django.contrib import admin
from .models import Florist, Courier, Customer, Bouquet, Order


@admin.register(Customer)
class Customer(admin.ModelAdmin):
    list_display = ('name', 'tg_id', 'phone_number', 'adress')
    search_fields = ('name', 'tg_id')


@admin.register(Florist)
class FloristAdmin(admin.ModelAdmin):
    list_display = ('name', 'tg_id')
    search_fields = ('name', 'tg_id')


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ('name', 'tg_id', 'phone')
    search_fields = ('name', 'tg_id')
    
@admin.register(Bouquet)
class BouquetAdmin(admin.ModelAdmin):
    list_display = ('name', 'price',)
    search_fields = ('name',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'florist', 'courier', 'status',
        'created_at', 'delivery_time', 'total_price'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('customer__name', 'florist__name', 'courier__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)