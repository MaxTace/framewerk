from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone


class Ingredient(models.Model):
    class Unit(models.TextChoices):
        GRAM = "g", "г"
        KILOGRAM = "kg", "кг"
        MILLILITER = "ml", "мл"
        LITER = "l", "л"
        PIECE = "pcs", "шт."

    name = models.CharField("Название", max_length=120, unique=True)
    category = models.CharField("Категория", max_length=80, blank=True)
    unit = models.CharField("Единица измерения", max_length=3, choices=Unit.choices)
    min_stock = models.DecimalField(
        "Минимальный остаток",
        max_digits=10,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    notes = models.TextField("Примечание", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(min_stock__gte=0),
                name="ingredient_min_stock_nonnegative",
            ),
        ]
        verbose_name = "ингредиент"
        verbose_name_plural = "ингредиенты"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            Stock.objects.get_or_create(ingredient=self)

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"


class Dish(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)
    description = models.TextField("Описание", blank=True)
    image = models.ImageField("Фото блюда", upload_to="dishes/", blank=True)
    price = models.DecimalField(
        "Цена в меню",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    is_available = models.BooleanField("Доступно в меню", default=True)
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeItem",
        related_name="dishes",
        verbose_name="Ингредиенты",
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name="dish_price_nonnegative",
            ),
        ]
        verbose_name = "блюдо"
        verbose_name_plural = "блюда"

    def __str__(self):
        return self.name


class RecipeItem(models.Model):
    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="recipe_items",
        verbose_name="Блюдо",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="recipe_items",
        verbose_name="Ингредиент",
    )
    quantity = models.DecimalField(
        "Количество на порцию",
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )

    class Meta:
        ordering = ["ingredient__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["dish", "ingredient"],
                name="unique_ingredient_per_dish",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="recipe_quantity_positive",
            ),
        ]
        verbose_name = "ингредиент в рецепте"
        verbose_name_plural = "ингредиенты в рецептах"

    def __str__(self):
        return f"{self.ingredient} — {self.quantity} на порцию"


class Stock(models.Model):
    ingredient = models.OneToOneField(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="stock",
        verbose_name="Ингредиент",
    )
    quantity = models.DecimalField(
        "Количество на складе",
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    updated_at = models.DateTimeField("Обновлен", auto_now=True)

    class Meta:
        ordering = ["ingredient__name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=0),
                name="stock_quantity_nonnegative",
            ),
        ]
        verbose_name = "остаток"
        verbose_name_plural = "остатки"

    @property
    def is_low(self):
        return self.quantity <= self.ingredient.min_stock

    def __str__(self):
        return f"{self.ingredient.name}: {self.quantity} {self.ingredient.get_unit_display()}"


class Supply(models.Model):
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="supplies",
        verbose_name="Ингредиент",
    )
    quantity = models.DecimalField(
        "Количество",
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    unit_price = models.DecimalField(
        "Цена за единицу",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    supplier = models.CharField("Поставщик", max_length=120, blank=True)
    document_number = models.CharField("Номер документа", max_length=80, blank=True)
    received_at = models.DateField("Дата поставки", default=timezone.localdate)
    created_at = models.DateTimeField("Запись создана", auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="supply_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__isnull=True) | Q(unit_price__gte=0),
                name="supply_unit_price_nonnegative",
            ),
        ]
        verbose_name = "поставка"
        verbose_name_plural = "поставки"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not is_new:
            previous = type(self).objects.only("ingredient_id", "quantity").get(pk=self.pk)
            if (
                previous.ingredient_id != self.ingredient_id
                or previous.quantity != self.quantity
            ):
                raise ValidationError(
                    "Нельзя менять ингредиент или количество в уже зарегистрированной поставке."
                )
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                stock, _ = Stock.objects.select_for_update().get_or_create(
                    ingredient=self.ingredient,
                    defaults={"quantity": Decimal("0")},
                )
                Stock.objects.filter(pk=stock.pk).update(
                    quantity=F("quantity") + self.quantity,
                    updated_at=timezone.now(),
                )

    def __str__(self):
        return f"{self.ingredient.name}: {self.quantity} ({self.received_at})"
