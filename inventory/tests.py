from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from PIL import Image

from .models import Dish, Ingredient, RecipeItem, Stock, Supply


class InventoryModelTests(TestCase):
    def setUp(self):
        self.ingredient = Ingredient.objects.create(
            name="Тестовая мука",
            unit=Ingredient.Unit.KILOGRAM,
            min_stock=Decimal("2"),
        )

    def test_new_ingredient_gets_empty_stock(self):
        self.assertEqual(self.ingredient.stock.quantity, Decimal("0"))

    def test_new_supply_increases_stock_once(self):
        supply = Supply.objects.create(
            ingredient=self.ingredient,
            quantity=Decimal("5.250"),
            unit_price=Decimal("70.00"),
        )
        stock = Stock.objects.get(ingredient=self.ingredient)
        self.assertEqual(stock.quantity, Decimal("5.250"))

        supply.supplier = "Поставщик"
        supply.save()
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, Decimal("5.250"))

    def test_supply_quantity_cannot_be_changed_after_receipt(self):
        supply = Supply.objects.create(
            ingredient=self.ingredient,
            quantity=Decimal("3.000"),
        )
        supply.quantity = Decimal("4.000")
        with self.assertRaises(ValidationError):
            supply.save()
        self.assertEqual(
            Stock.objects.get(ingredient=self.ingredient).quantity,
            Decimal("3.000"),
        )

    def test_recipe_item_connects_dish_and_ingredient(self):
        dish = Dish.objects.create(name="Тестовое блюдо", price=Decimal("250.00"))
        RecipeItem.objects.create(
            dish=dish,
            ingredient=self.ingredient,
            quantity=Decimal("0.200"),
        )
        self.assertEqual(dish.ingredients.get(), self.ingredient)


class InventoryViewTests(TestCase):
    def setUp(self):
        self.ingredient = Ingredient.objects.create(
            name="Помидор",
            category="Овощи",
            unit=Ingredient.Unit.KILOGRAM,
            min_stock=Decimal("3"),
        )
        self.dish = Dish.objects.create(name="Салат", price=Decimal("450.00"))

    def test_dashboard_and_main_lists_render(self):
        for url_name in (
            "inventory:dashboard",
            "inventory:ingredient_list",
            "inventory:dish_list",
            "inventory:stock_list",
            "inventory:supply_list",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)

    def test_ingredient_search_filters_results(self):
        Ingredient.objects.create(name="Рис", unit=Ingredient.Unit.KILOGRAM)
        response = self.client.get(
            reverse("inventory:ingredient_list"),
            {"q": "пом"},
        )
        self.assertContains(response, "Помидор")
        self.assertNotContains(response, "Рис")

    def test_supply_creation_updates_stock(self):
        response = self.client.post(
            reverse("inventory:supply_add"),
            {
                "ingredient": self.ingredient.pk,
                "quantity": "4.500",
                "unit_price": "100.00",
                "supplier": "Ферма",
                "document_number": "П-1",
                "received_at": "2026-10-31",
            },
        )
        self.assertRedirects(response, reverse("inventory:supply_list"))
        self.assertEqual(
            Stock.objects.get(ingredient=self.ingredient).quantity,
            Decimal("4.500"),
        )

    def test_dish_form_uploads_and_stores_an_image(self):
        image_buffer = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(image_buffer, format="PNG")
        image_file = SimpleUploadedFile(
            "dish.png",
            image_buffer.getvalue(),
            content_type="image/png",
        )

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("inventory:dish_add"),
                {
                    "name": "Суп",
                    "description": "Сезонный суп",
                    "image": image_file,
                    "price": "320.00",
                    "is_available": "on",
                },
            )
            dish = Dish.objects.get(name="Суп")
            self.assertRedirects(
                response,
                reverse("inventory:dish_detail", args=[dish.pk]),
            )
            self.assertTrue(dish.image.name.startswith("dishes/"))
            self.assertTrue(dish.image.storage.exists(dish.image.name))

    def test_dish_form_rejects_non_image_upload(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("inventory:dish_add"),
                {
                    "name": "Суп",
                    "description": "Сезонный суп",
                    "image": SimpleUploadedFile(
                        "dish.png",
                        b"not an image",
                        content_type="image/png",
                    ),
                    "price": "320.00",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response.context["form"].errors)
        self.assertFalse(Dish.objects.filter(name="Суп").exists())

    def test_duplicate_recipe_ingredient_returns_form_error(self):
        RecipeItem.objects.create(
            dish=self.dish,
            ingredient=self.ingredient,
            quantity=Decimal("0.200"),
        )
        response = self.client.post(
            reverse("inventory:recipe_item_add", args=[self.dish.pk]),
            {"ingredient": self.ingredient.pk, "quantity": "0.300"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Этот ингредиент уже добавлен в рецепт.")
        self.assertEqual(RecipeItem.objects.filter(dish=self.dish).count(), 1)

    def test_dish_detail_returns_404_for_missing_dish(self):
        response = self.client.get(
            reverse("inventory:dish_detail", args=[9999]),
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_page_number_falls_back_to_first_page(self):
        for index in range(11):
            Ingredient.objects.create(
                name=f"Продукт {index:02}",
                unit=Ingredient.Unit.PIECE,
            )
        response = self.client.get(
            reverse("inventory:ingredient_list"),
            {"page": "не-номер", "unit": "unknown"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertTrue(response.context["invalid_filter"])

    def test_pagination_keeps_active_filters(self):
        for index in range(11):
            Ingredient.objects.create(
                name=f"Мука {index:02}",
                unit=Ingredient.Unit.KILOGRAM,
            )
        response = self.client.get(
            reverse("inventory:ingredient_list"),
            {"unit": Ingredient.Unit.KILOGRAM, "page": "1"},
        )
        self.assertEqual(response.context["querystring"], "unit=kg")
        self.assertContains(response, "?unit=kg&amp;page=2")

    def test_detail_and_form_pages_render(self):
        url_names = (
            ("inventory:ingredient_detail", self.ingredient.pk),
            ("inventory:ingredient_add", None),
            ("inventory:dish_detail", self.dish.pk),
            ("inventory:dish_add", None),
            ("inventory:recipe_item_add", self.dish.pk),
            ("inventory:stock_edit", self.ingredient.stock.pk),
            ("inventory:supply_add", None),
        )
        for url_name, pk in url_names:
            with self.subTest(url_name=url_name):
                args = [pk] if pk is not None else []
                response = self.client.get(reverse(url_name, args=args))
                self.assertEqual(response.status_code, 200)
