from django import forms

from .models import Dish, Ingredient, RecipeItem, Stock, Supply


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"


class IngredientForm(StyledModelForm):
    class Meta:
        model = Ingredient
        fields = ["name", "category", "unit", "min_stock", "notes", "is_active"]
        widgets = {
            "min_stock": forms.NumberInput(attrs={"step": "0.001", "min": "0"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class DishForm(StyledModelForm):
    class Meta:
        model = Dish
        fields = ["name", "description", "image", "price", "is_available"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }


class RecipeItemForm(StyledModelForm):
    class Meta:
        model = RecipeItem
        fields = ["ingredient", "quantity"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ingredient"].queryset = Ingredient.objects.filter(is_active=True)


class StockForm(StyledModelForm):
    class Meta:
        model = Stock
        fields = ["quantity"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0"}),
        }


class SupplyForm(StyledModelForm):
    class Meta:
        model = Supply
        fields = [
            "ingredient",
            "quantity",
            "unit_price",
            "supplier",
            "document_number",
            "received_at",
        ]
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "received_at": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ingredient"].queryset = Ingredient.objects.filter(is_active=True)
