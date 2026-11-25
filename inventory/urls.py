from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("ingredients/", views.IngredientListView.as_view(), name="ingredient_list"),
    path("ingredients/add/", views.IngredientCreateView.as_view(), name="ingredient_add"),
    path(
        "ingredients/<int:pk>/",
        views.IngredientDetailView.as_view(),
        name="ingredient_detail",
    ),
    path(
        "ingredients/<int:pk>/edit/",
        views.IngredientUpdateView.as_view(),
        name="ingredient_edit",
    ),
    path(
        "ingredients/<int:pk>/delete/",
        views.IngredientDeleteView.as_view(),
        name="ingredient_delete",
    ),
    path("dishes/", views.DishListView.as_view(), name="dish_list"),
    path("dishes/add/", views.DishCreateView.as_view(), name="dish_add"),
    path("dishes/<int:pk>/", views.DishDetailView.as_view(), name="dish_detail"),
    path("dishes/<int:pk>/edit/", views.DishUpdateView.as_view(), name="dish_edit"),
    path("dishes/<int:pk>/delete/", views.DishDeleteView.as_view(), name="dish_delete"),
    path(
        "dishes/<int:dish_pk>/recipe/add/",
        views.RecipeItemCreateView.as_view(),
        name="recipe_item_add",
    ),
    path(
        "recipe-items/<int:pk>/delete/",
        views.RecipeItemDeleteView.as_view(),
        name="recipe_item_delete",
    ),
    path("stock/", views.StockListView.as_view(), name="stock_list"),
    path("stock/<int:pk>/edit/", views.StockUpdateView.as_view(), name="stock_edit"),
    path("supplies/", views.SupplyListView.as_view(), name="supply_list"),
    path("supplies/add/", views.SupplyCreateView.as_view(), name="supply_add"),
]
