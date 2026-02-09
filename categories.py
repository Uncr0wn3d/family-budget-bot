"""
Модуль для автоматического определения категории по описанию
"""

# Словарь категорий и ключевых слов
CATEGORIES = {
    'Еда': [
        'продукты', 'еда', 'ашан', 'лидл', 'магнит', 'пятерочка', 'перекресток',
        'супермаркет', 'рынок', 'овощи', 'фрукты', 'мясо', 'хлеб', 'молоко',
        'grocery', 'food', 'market', 'kaufland', 'biedronka', 'carrefour',
        'zabka', 'auchan', 'tesco', 'lidl'
    ],
    'Транспорт': [
        'такси', 'бензин', 'заправка', 'метро', 'автобус', 'транспорт',
        'яндекс', 'uber', 'bolt', 'машина', 'авто', 'парковка', 'билет',
        'taxi', 'gas', 'fuel', 'metro', 'bus', 'train', 'ticket', 'parking'
    ],
    'Развлечения': [
        'кино', 'театр', 'ресторан', 'кафе', 'бар', 'развлечения', 'парк',
        'концерт', 'музей', 'клуб', 'пицца', 'суши', 'доставка',
        'cinema', 'restaurant', 'cafe', 'bar', 'club', 'pizza', 'sushi',
        'entertainment', 'movie', 'concert', 'delivery'
    ],
    'Здоровье': [
        'аптека', 'врач', 'лекарства', 'больница', 'анализы', 'здоровье',
        'стоматолог', 'витамины', 'таблетки', 'медицина',
        'pharmacy', 'doctor', 'medicine', 'hospital', 'health', 'pills'
    ],
    'Дом': [
        'квартира', 'коммуналка', 'ремонт', 'мебель', 'икея', 'леруа',
        'свет', 'вода', 'газ', 'интернет', 'аренда', 'уборка',
        'rent', 'utilities', 'furniture', 'ikea', 'home', 'apartment',
        'internet', 'electricity', 'water', 'cleaning'
    ],
    'Одежда': [
        'одежда', 'обувь', 'магазин', 'шоппинг', 'зара', 'hm',
        'clothes', 'shoes', 'shopping', 'zara', 'fashion', 'wear'
    ],
    'Связь': [
        'телефон', 'мобильный', 'связь', 'тариф', 'мтс', 'билайн', 'мегафон',
        'phone', 'mobile', 'cellular', 'plan', 'subscription'
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
