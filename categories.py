"""
Модуль для автоматического определения категории по описанию
"""

# Словарь категорий и ключевых слов
CATEGORIES = {
    'Еда': [
        # Русские магазины
        'продукты', 'еда', 'ашан', 'магнит', 'пятерочка', 'перекресток',
        'супермаркет', 'рынок', 'овощи', 'фрукты', 'мясо', 'хлеб', 'молоко',
        # Польские магазины
        'biedronka', 'lidl', 'kaufland', 'zabka', 'żabka', 'auchan', 'carrefour',
        'dino', 'netto', 'intermarche', 'stokrotka', 'topaz', 'polomarket',
        'lewiatan', 'delikatesy', 'alma',
        # Общие
        'grocery', 'food', 'market', 'sklep', 'zakupy',
        # Заведения общепита
        'ресторан', 'кафе', 'бар', 'пицца', 'суши', 'доставка',
        'restauracja', 'kawiarnia', 'pub', 'pizzeria', 'kebab', 
        'mcdonald', 'kfc', 'pizza hut', 'glovo', 'pyszne.pl', 'uber eats',
        'restaurant', 'cafe', 'pizza', 'sushi', 'delivery'
    ]
}

DEFAULT_CATEGORY = 'Прочее'


def determine_category(description: str) -> str:
    """
    Определить категорию по описанию
    
    Args:
        description: Описание расхода
    
    Returns:
        Название категории
    """
    description_lower = description.lower()
    
    # Проходим по всем категориям и ищем совпадения
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword in description_lower:
                return category
    
    # Если не нашли совпадений, возвращаем "Прочее"
    return DEFAULT_CATEGORY


def get_all_categories() -> list:
    """Получить список всех категорий"""
    return list(CATEGORIES.keys()) + [DEFAULT_CATEGORY]


def get_category_keywords(category: str) -> list:
    """Получить ключевые слова для категории"""
    return CATEGORIES.get(category, [])
