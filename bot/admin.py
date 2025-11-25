from django.contrib import admin
from django.db.models import Avg, BooleanField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from .models import (
    Category,
    Courier,
    CourierAssignment,
    CourierDelivery,
    Florist,
    FloristAssignment,
    FloristCallback,
    Item,
    Order,
    Owner,
    User
)


class CourierAssignmentInline(admin.TabularInline):
    model = CourierAssignment
    extra = 1
    readonly_fields = ('assigned_at', 'delivered_at')


class FloristAssignmentInline(admin.TabularInline):
    model = FloristAssignment
    extra = 1
    readonly_fields = ('assigned_at', 'completed_at')


class FloristCallbackInline(admin.TabularInline):
    model = FloristCallback
    extra = 1
    readonly_fields = ('created_at',)
    fields = ('florist', 'needs_callback', 'callback_made', 'phone_number')
    raw_id_fields = ('florist',)
    verbose_name = "Обратный звонок флориста"
    verbose_name_plural = "Обратные звонки флористов"


class CourierDeliveryInline(admin.TabularInline):
    model = CourierDelivery
    extra = 0
    readonly_fields = ('courier', 'order', 'delivered_at')
    fields = ('delivered',)
    verbose_name = 'Доставка курьера'
    verbose_name_plural = 'Доставки курьеров'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('tg_id',)
    search_fields = ('tg_id',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'category')
    search_fields = ('name', 'category__name')
    list_filter = ('category',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'status',
        'delivery_date',
        'delivery_time',
        'get_courier',
        'is_delivered'
    )
    search_fields = ('name', 'address')
    list_filter = ('status', 'delivery_date')
    readonly_fields = ('created_at', 'completed_at')
    inlines = [FloristCallbackInline]

    def get_queryset(self, request):
        courier_delivery_subquery = CourierDelivery.objects.filter(
            order=OuterRef('pk')).order_by(
                '-delivered_at').values('delivered'
                                        )[:1]

        qs = super().get_queryset(request)
        qs = qs.annotate(
            courier_time=Avg('courierassignment__delivery_time'),
            florist_time=Avg('floristassignment__processing_time'),
            is_delivered=Coalesce(Subquery(
                courier_delivery_subquery, output_field=BooleanField()), False)
        )
        return qs

    def avg_courier_time(self, obj):
        return obj.courier_time
    avg_courier_time.short_description = 'Среднее время доставки'

    def avg_florist_time(self, obj):
        return obj.florist_time
    avg_florist_time.short_description = 'Среднее время обработки'

    def get_courier(self, obj):
        return obj.courier.name if obj.courier else 'Не назначен'
    get_courier.short_description = 'Курьер'

    def is_delivered(self, obj):
        return obj.is_delivered
    is_delivered.boolean = True
    is_delivered.short_description = 'Доставлено'


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'get_total_orders')
    search_fields = ('name',)
    list_filter = ('status',)
    inlines = [CourierAssignmentInline]

    def get_total_orders(self, obj):
        return obj.assigned_orders.count()
    get_total_orders.short_description = 'Количество заказов'


@admin.register(Florist)
class FloristAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'get_total_orders')
    search_fields = ('name',)
    list_filter = ('status',)
    inlines = [FloristAssignmentInline]

    def get_total_orders(self, obj):
        return obj.assigned_orders.count()
    get_total_orders.short_description = 'Количество заказов'


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('user', 'can_assign', 'can_view_stats')
    search_fields = ('user__tg_id',)

@admin.register(CourierDelivery)
class CourierDeliveryAdmin(admin.ModelAdmin):
    list_display = ('courier', 'order', 'delivered', 'delivered_at')
    list_filter = ('courier', 'delivered')
    search_fields = ('courier__name', 'order__name', 'order__address')

@admin.register(FloristCallback)
class FloristCallbackAdmin(admin.ModelAdmin):
    list_display = (
        'florist',
        'get_order_name',
        'needs_callback',
        'callback_made',
        'phone_number'
    )
    list_filter = ('florist', 'needs_callback', 'callback_made')
    search_fields = (
        'florist__name',
        'order__name',
        'order__address',
        'phone_number'
    )

    def get_order_name(self, obj):
        return obj.order.name if obj.order else "Консультация"
    get_order_name.short_description = 'Заказ/Консультация'
