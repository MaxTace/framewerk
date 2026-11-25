-- 1. Все активные ингредиенты.
SELECT id, name, category, unit, min_stock
FROM inventory_ingredient
WHERE is_active = 1
ORDER BY name;

-- 2. Список доступных блюд.
SELECT id, name, price
FROM inventory_dish
WHERE is_available = 1
ORDER BY name;

-- 3. Ингредиенты, остаток которых ниже минимального порога.
SELECT ingredient.name, stock.quantity, ingredient.min_stock, ingredient.unit
FROM inventory_stock AS stock
JOIN inventory_ingredient AS ingredient ON ingredient.id = stock.ingredient_id
WHERE stock.quantity <= ingredient.min_stock
ORDER BY ingredient.name;

-- 4. Поставки выбранного ингредиента за заданный период.
SELECT received_at, quantity, unit_price, supplier, document_number
FROM inventory_supply
WHERE ingredient_id = 1 AND received_at >= '2026-01-01'
ORDER BY received_at DESC;

-- 5. Поиск по названию ингредиента или категории.
SELECT id, name, category, unit
FROM inventory_ingredient
WHERE name LIKE '%томат%' OR category LIKE '%овощ%';

-- 6. Поставки с названием ингредиента.
SELECT supply.received_at, ingredient.name, supply.quantity, ingredient.unit, supply.supplier
FROM inventory_supply AS supply
JOIN inventory_ingredient AS ingredient ON ingredient.id = supply.ingredient_id
ORDER BY supply.received_at DESC;

-- 7. Состав рецептов с названием блюда и количеством ингредиента.
SELECT dish.name AS dish, ingredient.name AS ingredient, recipe.quantity, ingredient.unit
FROM inventory_recipeitem AS recipe
JOIN inventory_dish AS dish ON dish.id = recipe.dish_id
JOIN inventory_ingredient AS ingredient ON ingredient.id = recipe.ingredient_id
ORDER BY dish.name, ingredient.name;

-- 8. Количество поставок по каждому ингредиенту.
SELECT ingredient.name, COUNT(supply.id) AS supply_count
FROM inventory_ingredient AS ingredient
LEFT JOIN inventory_supply AS supply ON supply.ingredient_id = ingredient.id
GROUP BY ingredient.id, ingredient.name
ORDER BY supply_count DESC, ingredient.name;

-- 9. Суммарный объем поставок по ингредиентам.
SELECT ingredient.name, SUM(supply.quantity) AS supplied_quantity, ingredient.unit
FROM inventory_ingredient AS ingredient
JOIN inventory_supply AS supply ON supply.ingredient_id = ingredient.id
GROUP BY ingredient.id, ingredient.name, ingredient.unit
ORDER BY supplied_quantity DESC;

-- 10. Стоимость каждой поставки и общие расходы.
SELECT supplier, SUM(quantity * unit_price) AS total_cost
FROM inventory_supply
WHERE unit_price IS NOT NULL
GROUP BY supplier
ORDER BY total_cost DESC;

-- 11. Ингредиенты, входящие в несколько блюд.
SELECT ingredient.name, COUNT(DISTINCT recipe.dish_id) AS dish_count
FROM inventory_ingredient AS ingredient
JOIN inventory_recipeitem AS recipe ON recipe.ingredient_id = ingredient.id
GROUP BY ingredient.id, ingredient.name
HAVING COUNT(DISTINCT recipe.dish_id) > 1
ORDER BY dish_count DESC;

-- 12. Средняя цена блюд меню.
SELECT AVG(price) AS average_menu_price
FROM inventory_dish
WHERE is_available = 1;
