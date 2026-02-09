"""
Telegram бот для учета семейного бюджета
Для двух пользователей с автоматическим определением категорий
"""

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import re
from database import Database
from categories import determine_category
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ID разрешенных пользователей (замените на ваши Telegram ID)
ALLOWED_USERS = []  # Оставьте пустым, заполнится автоматически при первом /start

db = Database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - приветствие и инструкция"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    # Добавляем пользователя в разрешенные, если список пуст или меньше 2
    if len(ALLOWED_USERS) < 2 and user_id not in ALLOWED_USERS:
        ALLOWED_USERS.append(user_id)
        logger.info(f"Добавлен пользователь: {user_id} ({username})")
    
    welcome_text = f"""
👋 Привет, {username}!

Я бот для учета семейного бюджета. Вот что я умею:

📝 **Добавить расход:**
Просто напишите сумму и описание, например:
• 500 ашан
• 1200 такси
• 350 кофе

Я автоматически определю категорию! 🎯

📊 **Команды:**
/stats - посмотреть статистику
/history - история трат (можно редактировать)
/balance - баланс между вами
/categories - список категорий

Зарегистрированные пользователи: {len(ALLOWED_USERS)}/2
"""
    await update.message.reply_text(welcome_text)


async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка добавления расхода в формате 'сумма описание'"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    # Проверка доступа
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    text = update.message.text.strip()
    
    # Парсим сумму и описание
    match = re.match(r'^(\d+(?:[.,]\d+)?)\s+(.+)$', text)
    
    if not match:
        await update.message.reply_text(
            "❓ Не могу распознать формат.\n"
            "Используйте: сумма описание\n"
            "Например: 500 продукты"
        )
        return
    
    amount_str, description = match.groups()
    amount = float(amount_str.replace(',', '.'))
    
    # Определяем категорию
    category = determine_category(description)
    
    # Сохраняем в БД
    expense_id = db.add_expense(user_id, username, amount, category, description)
    
    # Формируем ответ
    response = f"✅ Добавлено:\n"
    response += f"💰 {amount:.2f} zł\n"
    response += f"📂 {category}\n"
    response += f"📝 {description}\n"
    response += f"👤 {username}"
    
    # Кнопки для редактирования
    keyboard = [
        [
            InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_{expense_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{expense_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response, reply_markup=reply_markup)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    # Получаем период (по умолчанию текущий месяц)
    period = 'month'
    if context.args and context.args[0] in ['week', 'month', 'year', 'all']:
        period = context.args[0]
    
    # Определяем даты
    now = datetime.now()
    if period == 'week':
        start_date = now - timedelta(days=7)
        period_name = "Последние 7 дней"
    elif period == 'month':
        start_date = now.replace(day=1)
        period_name = "Текущий месяц"
    elif period == 'year':
        start_date = now.replace(month=1, day=1)
        period_name = "Текущий год"
    else:  # all
        start_date = None
        period_name = "За все время"
    
    # Получаем статистику
    total = db.get_total(start_date)
    by_category = db.get_by_category(start_date)
    by_user = db.get_by_user(start_date)
    
    # Формируем ответ
    response = f"📊 **Статистика: {period_name}**\n\n"
    response += f"💰 **Общая сумма:** {total:.2f} zł\n\n"
    
    # По категориям
    if by_category:
        response += "📂 **По категориям:**\n"
        for category, amount in by_category:
            percentage = (amount / total * 100) if total > 0 else 0
            response += f"  • {category}: {amount:.2f} zł ({percentage:.1f}%)\n"
        response += "\n"
    
    # По пользователям
    if by_user:
        response += "👥 **По пользователям:**\n"
        for user, amount in by_user:
            percentage = (amount / total * 100) if total > 0 else 0
            response += f"  • {user}: {amount:.2f} zł ({percentage:.1f}%)\n"
    
    # Кнопки для выбора периода
    keyboard = [
        [
            InlineKeyboardButton("Неделя", callback_data="stats_week"),
            InlineKeyboardButton("Месяц", callback_data="stats_month"),
        ],
        [
            InlineKeyboardButton("Год", callback_data="stats_year"),
            InlineKeyboardButton("Все время", callback_data="stats_all"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response, reply_markup=reply_markup, parse_mode='Markdown')


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс между пользователями"""
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    by_user = db.get_by_user()
    
    if len(by_user) < 2:
        await update.message.reply_text("📊 Пока нет данных для расчета баланса.")
        return
    
    user1, amount1 = by_user[0]
    user2, amount2 = by_user[1]
    
    total = amount1 + amount2
    half = total / 2
    
    difference = abs(amount1 - amount2)
    who_owes = user1 if amount1 < amount2 else user2
    who_paid_more = user2 if amount1 < amount2 else user1
    
    response = f"💰 **Баланс**\n\n"
    response += f"👤 {user1}: {amount1:.2f} zł\n"
    response += f"👤 {user2}: {amount2:.2f} zł\n\n"
    response += f"📊 Всего: {total:.2f} zł\n"
    response += f"⚖️ Поровну: {half:.2f} zł каждому\n\n"
    
    if difference > 1:  # Если разница больше 1 рубля
        response += f"💸 **{who_owes}** должен **{who_paid_more}**: {difference/2:.2f} zł"
    else:
        response += "✅ Вы квиты! 🎉"
    
    await update.message.reply_text(response, parse_mode='Markdown')


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние траты"""
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = int(context.args[0])
    
    expenses = db.get_recent_expenses(limit)
    
    if not expenses:
        await update.message.reply_text("📝 История трат пуста.")
        return
    
    response = f"📝 **Последние {len(expenses)} трат:**\n\n"
    
    for exp in expenses:
        exp_id, user_id, username, amount, category, description, date = exp
        date_obj = datetime.fromisoformat(date)
        date_str = date_obj.strftime("%d.%m %H:%M")
        
        response += f"🕐 {date_str}\n"
        response += f"💰 {amount:.2f} zł | 📂 {category}\n"
        response += f"📝 {description} | 👤 {username}\n"
        response += f"ID: {exp_id}\n\n"
    
    response += "\nДля редактирования используйте:\n"
    response += "/edit [ID] - изменить\n"
    response += "/delete [ID] - удалить"
    
    await update.message.reply_text(response, parse_mode='Markdown')


async def delete_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить расход"""
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❓ Используйте: /delete [ID]")
        return
    
    expense_id = int(context.args[0])
    
    if db.delete_expense(expense_id):
        await update.message.reply_text("✅ Расход удален!")
    else:
        await update.message.reply_text("❌ Расход не найден.")


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список категорий и ключевых слов"""
    response = """
📂 **Категории и ключевые слова:**

🍔 **Еда**
продукты, еда, ашан, лидл, магнит, пятерочка, перекресток, супермаркет, рынок, овощи, мясо, хлеб

🚗 **Транспорт**
такси, бензин, заправка, метро, автобус, транспорт, яндекс, uber

🎉 **Развлечения**
кино, театр, ресторан, кафе, бар, развлечения, парк, концерт

💊 **Здоровье**
аптека, врач, лекарства, больница, анализы, здоровье

🏠 **Дом**
квартира, коммуналка, ремонт, мебель, икея, леруа

📦 **Прочее**
Все остальное
"""
    await update.message.reply_text(response, parse_mode='Markdown')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Обработка статистики
    if data.startswith('stats_'):
        period = data.replace('stats_', '')
        
        # Определяем даты
        now = datetime.now()
        if period == 'week':
            start_date = now - timedelta(days=7)
            period_name = "Последние 7 дней"
        elif period == 'month':
            start_date = now.replace(day=1)
            period_name = "Текущий месяц"
        elif period == 'year':
            start_date = now.replace(month=1, day=1)
            period_name = "Текущий год"
        else:  # all
            start_date = None
            period_name = "За все время"
        
        # Получаем статистику
        total = db.get_total(start_date)
        by_category = db.get_by_category(start_date)
        by_user = db.get_by_user(start_date)
        
        # Формируем ответ
        response = f"📊 **Статистика: {period_name}**\n\n"
        response += f"💰 **Общая сумма:** {total:.2f} zł\n\n"
        
        if by_category:
            response += "📂 **По категориям:**\n"
            for category, amount in by_category:
                percentage = (amount / total * 100) if total > 0 else 0
                response += f"  • {category}: {amount:.2f} zł ({percentage:.1f}%)\n"
            response += "\n"
        
        if by_user:
            response += "👥 **По пользователям:**\n"
            for user, amount in by_user:
                percentage = (amount / total * 100) if total > 0 else 0
                response += f"  • {user}: {amount:.2f} zł ({percentage:.1f}%)\n"
        
        # Те же кнопки
        keyboard = [
            [
                InlineKeyboardButton("Неделя", callback_data="stats_week"),
                InlineKeyboardButton("Месяц", callback_data="stats_month"),
            ],
            [
                InlineKeyboardButton("Год", callback_data="stats_year"),
                InlineKeyboardButton("Все время", callback_data="stats_all"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Удаление расхода
    elif data.startswith('delete_'):
        expense_id = int(data.replace('delete_', ''))
        if db.delete_expense(expense_id):
            await query.edit_message_text("✅ Расход удален!")
        else:
            await query.edit_message_text("❌ Ошибка при удалении.")


def main():
    """Запуск бота"""
    # Получаем токен из переменных окружения
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        raise ValueError("Не найден TELEGRAM_BOT_TOKEN в переменных окружения!")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("delete", delete_expense))
    application.add_handler(CommandHandler("categories", show_categories))
    
    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик текстовых сообщений (добавление расходов)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        add_expense
    ))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
