from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Prefetch, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .forms import DishForm, IngredientForm, RecipeItemForm, StockForm, SupplyForm
from .models import Dish, Ingredient, RecipeItem, Stock, Supply


PAGE_SIZE = 10


def _search_query(search, *fields):
    variants = {search, search.lower(), search.upper(), search.title()}
    query = Q()
    for field in fields:
        for variant in variants:
            query |= Q(**{f"{field}__contains": variant})
    return query


class PageContextMixin:
    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(
            queryset,
            page_size,
            allow_empty_first_page=self.get_allow_empty(),
        )
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["querystring"] = query_params.urlencode()
        return context


class FormPageMixin(PageContextMixin):
    template_name = "inventory/form.html"
    success_message = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.get_form_title()
        context["cancel_url"] = self.get_cancel_url()
        context["cancel_pk"] = self.get_cancel_pk()
        return context

    def get_form_title(self):
        return self.page_title

    def get_cancel_url(self):
        return self.cancel_route

    def get_cancel_pk(self):
        obj = getattr(self, "object", None)
        return obj.pk if obj else None

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response


class DashboardView(TemplateView):
    template_name = "inventory/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        low_stocks = (
            Stock.objects.select_related("ingredient")
            .filter(quantity__lte=F("ingredient__min_stock"), ingredient__is_active=True)
            .order_by("quantity", "ingredient__name")[:6]
        )
        supply_cost = Supply.objects.aggregate(
            total=Sum(F("quantity") * F("unit_price"))
        )["total"] or Decimal("0")
        context.update(
            {
                "ingredient_count": Ingredient.objects.filter(is_active=True).count(),
                "dish_count": Dish.objects.filter(is_available=True).count(),
                "supply_count": Supply.objects.count(),
                "low_stock_count": Stock.objects.filter(
                    quantity__lte=F("ingredient__min_stock"),
                    ingredient__is_active=True,
                ).count(),
                "supply_cost": supply_cost,
                "low_stocks": low_stocks,
                "recent_supplies": Supply.objects.select_related("ingredient")[:5],
                "category_summary": (
                    Ingredient.objects.filter(is_active=True)
                    .values("category")
                    .annotate(ingredient_count=Count("id"))
                    .order_by("-ingredient_count", "category")[:5]
                ),
            }
        )
        return context


class IngredientListView(PageContextMixin, ListView):
    model = Ingredient
    template_name = "inventory/ingredient_list.html"
    context_object_name = "ingredients"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        queryset = Ingredient.objects.exclude(is_active=False)
        self.search = self.request.GET.get("q", "").strip()[:100]
        self.unit = self.request.GET.get("unit", "")
        valid_units = {value for value, _ in Ingredient.Unit.choices}
        self.invalid_filter = bool(self.unit and self.unit not in valid_units)

        if self.search:
            queryset = queryset.filter(_search_query(self.search, "name", "category"))
        if self.unit in valid_units:
            queryset = queryset.filter(unit=self.unit)
        return (
            queryset.select_related("stock")
            .annotate(stock_is_low=Q(stock__quantity__lte=F("min_stock")))
            .order_by("name")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        valid_units = {value for value, _ in Ingredient.Unit.choices}
        context.update(
            {
                "search": self.search,
                "selected_unit": self.unit if self.unit in valid_units else "",
                "units": Ingredient.Unit.choices,
                "invalid_filter": self.invalid_filter,
            }
        )
        return context


class IngredientDetailView(DetailView):
    model = Ingredient
    template_name = "inventory/ingredient_detail.html"
    context_object_name = "ingredient"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ingredient = self.object
        context.update(
            {
                "stock": Stock.objects.filter(ingredient=ingredient).first(),
                "supplies": ingredient.supplies.order_by("-received_at", "-pk")[:10],
                "recipe_items": ingredient.recipe_items.select_related("dish").order_by(
                    "dish__name"
                ),
            }
        )
        return context


class IngredientFormMixin(FormPageMixin):
    model = Ingredient
    form_class = IngredientForm
    page_title = "Новый ингредиент"
    edit_title = "Редактировать ингредиент"
    cancel_route = "inventory:ingredient_list"
    success_message = "Ингредиент сохранен."

    def get_form_title(self):
        return self.edit_title if self.object else self.page_title

    def get_cancel_url(self):
        return "inventory:ingredient_detail" if self.object else self.cancel_route

    def get_success_url(self):
        return reverse("inventory:ingredient_detail", kwargs={"pk": self.object.pk})


class IngredientCreateView(IngredientFormMixin, CreateView):
    pass


class IngredientUpdateView(IngredientFormMixin, UpdateView):
    pass


class DishListView(PageContextMixin, ListView):
    model = Dish
    template_name = "inventory/dish_list.html"
    context_object_name = "dishes"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        queryset = Dish.objects.all().prefetch_related(
            Prefetch("recipe_items", queryset=RecipeItem.objects.select_related("ingredient"))
        )
        self.search = self.request.GET.get("q", "").strip()[:100]
        self.ingredient_id = self.request.GET.get("ingredient", "")
        self.invalid_filter = False

        if self.search:
            queryset = queryset.filter(
                _search_query(self.search, "name", "description", "ingredients__name")
            ).distinct()
        if self.ingredient_id:
            if self.ingredient_id.isdecimal() and Ingredient.objects.filter(
                pk=self.ingredient_id
            ).exists():
                queryset = queryset.filter(ingredients__pk=self.ingredient_id)
            else:
                self.invalid_filter = True
        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search": self.search,
                "ingredients": Ingredient.objects.filter(is_active=True).order_by("name"),
                "selected_ingredient": (
                    self.ingredient_id if not self.invalid_filter else ""
                ),
                "invalid_filter": self.invalid_filter,
            }
        )
        return context


class DishDetailView(DetailView):
    model = Dish
    template_name = "inventory/dish_detail.html"
    context_object_name = "dish"

    def get_queryset(self):
        return Dish.objects.prefetch_related(
            Prefetch("recipe_items", queryset=RecipeItem.objects.select_related("ingredient"))
        )


class DishFormMixin(FormPageMixin):
    model = Dish
    form_class = DishForm
    page_title = "Новое блюдо"
    edit_title = "Редактировать блюдо"
    cancel_route = "inventory:dish_list"
    success_message = "Блюдо сохранено."

    def get_form_title(self):
        return self.edit_title if self.object else self.page_title

    def get_cancel_url(self):
        return "inventory:dish_detail" if self.object else self.cancel_route

    def get_success_url(self):
        return reverse("inventory:dish_detail", kwargs={"pk": self.object.pk})


class DishCreateView(DishFormMixin, CreateView):
    pass


class DishUpdateView(DishFormMixin, UpdateView):
    pass


class RecipeItemCreateView(FormPageMixin, CreateView):
    form_class = RecipeItemForm
    page_title = "Добавить ингредиент"
    cancel_route = "inventory:dish_list"

    def dispatch(self, request, *args, **kwargs):
        self.dish = get_object_or_404(Dish, pk=kwargs["dish_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_title(self):
        return f"Добавить ингредиент: {self.dish.name}"

    def get_cancel_url(self):
        return "inventory:dish_detail"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_pk"] = self.dish.pk
        context["dish"] = self.dish
        return context

    def form_valid(self, form):
        recipe_item = form.save(commit=False)
        recipe_item.dish = self.dish
        try:
            with transaction.atomic():
                recipe_item.save()
        except IntegrityError:
            form.add_error("ingredient", "Этот ингредиент уже добавлен в рецепт.")
            return self.form_invalid(form)
        self.object = recipe_item
        messages.success(self.request, "Ингредиент добавлен в рецепт.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("inventory:dish_detail", kwargs={"pk": self.dish.pk})


class RecipeItemDeleteView(View):
    def post(self, request, pk):
        recipe_item = get_object_or_404(RecipeItem.objects.select_related("dish"), pk=pk)
        dish_pk = recipe_item.dish_id
        recipe_item.delete()
        messages.success(request, "Ингредиент удален из рецепта.")
        return redirect("inventory:dish_detail", pk=dish_pk)


class DishDeleteView(View):
    def post(self, request, pk):
        dish = get_object_or_404(Dish, pk=pk)
        dish.delete()
        messages.success(request, "Блюдо удалено.")
        return redirect("inventory:dish_list")


class StockListView(PageContextMixin, ListView):
    model = Stock
    template_name = "inventory/stock_list.html"
    context_object_name = "stocks"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        queryset = Stock.objects.select_related("ingredient").filter(
            ingredient__is_active=True
        )
        self.search = self.request.GET.get("q", "").strip()[:100]
        self.status = self.request.GET.get("status", "")
        self.invalid_filter = bool(self.status and self.status not in {"low", "normal"})

        if self.search:
            queryset = queryset.filter(
                _search_query(self.search, "ingredient__name", "ingredient__category")
            )
        if self.status == "low":
            queryset = queryset.filter(quantity__lte=F("ingredient__min_stock"))
        elif self.status == "normal":
            queryset = queryset.filter(quantity__gt=F("ingredient__min_stock"))
        return queryset.order_by("ingredient__name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "search": self.search,
                "selected_status": self.status if not self.invalid_filter else "",
                "invalid_filter": self.invalid_filter,
            }
        )
        return context


class StockUpdateView(FormPageMixin, UpdateView):
    model = Stock
    form_class = StockForm
    cancel_route = "inventory:stock_list"
    success_url = reverse_lazy("inventory:stock_list")
    success_message = "Остаток обновлен."

    def get_queryset(self):
        return Stock.objects.select_related("ingredient")

    def get_form_title(self):
        return f"Изменить остаток: {self.object.ingredient.name}"

    def get_cancel_pk(self):
        return None


class IngredientDeleteView(View):
    def post(self, request, pk):
        ingredient = get_object_or_404(Ingredient, pk=pk)
        try:
            ingredient.delete()
        except ProtectedError:
            messages.error(
                request,
                "Нельзя удалить ингредиент, который указан в поставках или рецептах.",
            )
            return redirect("inventory:ingredient_detail", pk=pk)
        messages.success(request, "Ингредиент удален.")
        return redirect("inventory:ingredient_list")


class SupplyListView(PageContextMixin, ListView):
    model = Supply
    template_name = "inventory/supply_list.html"
    context_object_name = "supplies"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        queryset = Supply.objects.select_related("ingredient")
        self.search = self.request.GET.get("q", "").strip()[:100]
        self.ingredient_id = self.request.GET.get("ingredient", "")
        self.invalid_filter = False

        if self.search:
            queryset = queryset.filter(
                _search_query(
                    self.search,
                    "ingredient__name",
                    "supplier",
                    "document_number",
                )
            )
        if self.ingredient_id:
            if self.ingredient_id.isdecimal() and Ingredient.objects.filter(
                pk=self.ingredient_id
            ).exists():
                queryset = queryset.filter(ingredient_id=self.ingredient_id)
            else:
                self.invalid_filter = True
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quantity_by_unit = list(
            self.object_list.values("ingredient__unit")
            .annotate(total=Sum("quantity"))
            .order_by("ingredient__unit")
        )
        unit_labels = dict(Ingredient.Unit.choices)
        for row in quantity_by_unit:
            row["unit_label"] = unit_labels[row["ingredient__unit"]]
        context.update(
            {
                "search": self.search,
                "ingredients": Ingredient.objects.filter(is_active=True).order_by("name"),
                "selected_ingredient": (
                    self.ingredient_id if not self.invalid_filter else ""
                ),
                "invalid_filter": self.invalid_filter,
                "quantity_by_unit": quantity_by_unit,
            }
        )
        return context


class SupplyCreateView(FormPageMixin, CreateView):
    model = Supply
    form_class = SupplyForm
    cancel_route = "inventory:supply_list"
    success_url = reverse_lazy("inventory:supply_list")
    page_title = "Новая поставка"
    success_message = "Поставка зарегистрирована, остаток увеличен."
