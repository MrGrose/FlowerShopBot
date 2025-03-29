from django.contrib import admin
from .models import User, Category, Item, Courier, Florist, Order


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'tg_id')
    search_fields = ('tg_id',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'category', 'structure')
    search_fields = ('name', 'category__name')
    list_filter = ('category',)


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ('name', 'tg_id')
    search_fields = ('name', 'tg_id')


@admin.register(Florist)
class FloristAdmin(admin.ModelAdmin):
    list_display = ('name', 'tg_id')
    search_fields = ('name', 'tg_id')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'delivery_date', 'delivery_time')
    search_fields = ('name', 'address')
    list_filter = ('delivery_date',)
    ordering = ('-delivery_date',)
    readonly_fields = ('delivery_date',)