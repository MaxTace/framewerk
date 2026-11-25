from django.contrib import admin

from .models import Dish, Ingredient, RecipeItem, Stock, Supply


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "unit", "min_stock", "is_active")
    list_filter = ("unit", "category", "is_active")
    search_fields = ("name", "category")


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_available")
    list_filter = ("is_available",)
    search_fields = ("name", "description")
    inlines = [RecipeItemInline]


@admin.register(RecipeItem)
class RecipeItemAdmin(admin.ModelAdmin):
    list_display = ("dish", "ingredient", "quantity")
    list_filter = ("dish", "ingredient")
    search_fields = ("dish__name", "ingredient__name")
    autocomplete_fields = ("dish", "ingredient")


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("ingredient", "quantity", "updated_at")
    search_fields = ("ingredient__name",)
    readonly_fields = ("updated_at",)


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    list_display = ("ingredient", "quantity", "unit_price", "supplier", "received_at")
    list_filter = ("received_at", "supplier")
    search_fields = ("ingredient__name", "supplier", "document_number")
    readonly_fields = (
        "ingredient",
        "quantity",
        "unit_price",
        "supplier",
        "document_number",
        "received_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
