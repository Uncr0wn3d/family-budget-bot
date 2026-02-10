"""
Telegram бот для учета семейного бюджета
Для двух пользователей с автоматическим определением категорий
"""
from aiohttp import web
import asyncio

# Функция-обработчик для проверки, что бот жив
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    # Создаем веб-приложение
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render передает порт в переменную окружения PORT
    import os
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    # Запускаем веб-сервер фоном
    await site.start()
    
    # Далее ваш привычный запуск бота
    # await dp.start_polling(bot)

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
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
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ID разрешенных пользователей (замените на ваши Telegram ID)
ALLOWED_USERS = [399447361,416881967]  # Оставьте пустым, заполнится автоматически при первом /start

db = Database()


# HTTP сервер для Render (чтобы не падал Web Service)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Отключаем логи HTTP


def start_health_check_server():
    """Запускает HTTP-сервер для Render"""
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"✅ Health check server started on port {port}")


def get_salary_period():
    """
    Вычисляет начало текущего зарплатного периода.
    ЗП 10 числа (или раньше если выходной/праздник)
    Рабочие дни: Ср-Сб (воскресенье начало недели)
    """
    now = datetime.now()
    
    # Функция для проверки является ли день выходным (Сб=5, Вс=6)
    def is_weekend(date):
        return date.weekday() >= 5
    
    # Функция для нахождения рабочего дня назад от 10 числа
    def get_salary_day(year, month):
        salary_date = datetime(year, month, 10)
        
        # Если 10 число - выходной, идем назад до рабочего дня
        while is_weekend(salary_date):
            salary_date = salary_date - timedelta(days=1)
        
        return salary_date
    
    # Получаем день ЗП текущего месяца
    current_salary_day = get_salary_day(now.year, now.month)
    
    # Если сегодня до дня ЗП, то период начался в прошлом месяце
    if now.date() < current_salary_day.date():
        if now.month == 1:
            prev_salary_day = get_salary_day(now.year - 1, 12)
        else:
            prev_salary_day = get_salary_day(now.year, now.month - 1)
        return prev_salary_day
    else:
        return current_salary_day


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
• 500 biedronka
• 1200 taxi
• 350 кофе

Категории: 🍔 Еда, 📦 Прочее

📊 **Используйте кнопки ниже** для управления ботом

Ваш ID: `{user_id}`
Зарегистрированные: {len(ALLOWED_USERS)}/2
"""
    
    # Создаем кнопочное меню
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    
    keyboard = [
        [KeyboardButton("📊 Статистика"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("📝 История"), KeyboardButton("🔍 Мой ID")],
        [KeyboardButton("📂 Категории"), KeyboardButton("ℹ️ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')


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
    
    # Отправляем уведомление второму пользователю
    other_user_id = None
    for uid in ALLOWED_USERS:
        if uid != user_id:
            other_user_id = uid
            break
    
    if other_user_id:
        notification = f"🔔 Новый расход:\n"
        notification += f"👤 {username}\n"
        notification += f"💰 {amount:.2f} zł\n"
        notification += f"📂 {category}\n"
        notification += f"📝 {description}"
        
        try:
            await context.bot.send_message(chat_id=other_user_id, text=notification)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление: {e}")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    # Получаем период (по умолчанию зарплатный период)
    period = 'salary'
    if context.args and context.args[0] in ['week', 'month', 'year', 'all', 'salary']:
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
    elif period == 'salary':
        start_date = get_salary_period()
        period_name = f"С {start_date.strftime('%d.%m.%Y')} (зарплатный период)"
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
            InlineKeyboardButton("ЗП период", callback_data="stats_salary"),
            InlineKeyboardButton("Неделя", callback_data="stats_week"),
        ],
        [
            InlineKeyboardButton("Месяц", callback_data="stats_month"),
            InlineKeyboardButton("Все время", callback_data="stats_all"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response, reply_markup=reply_markup, parse_mode='Markdown')


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс между пользователями с разбивкой по категориям"""
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        return
    
    # Получаем детальную статистику по пользователям и категориям
    by_user_category = db.get_by_user_and_category()
    
    if not by_user_category:
        await update.message.reply_text("📊 Пока нет данных для расчета баланса.")
        return
    
    # Группируем данные
    user_totals = {}
    category_totals = {'Еда': 0, 'Прочее': 0}
    user_category_amounts = {}
    
    for username, category, amount in by_user_category:
        # Общие суммы по пользователям
        if username not in user_totals:
            user_totals[username] = 0
        user_totals[username] += amount
        
        # Суммы по категориям
        category_totals[category] += amount
        
        # Суммы по пользователям и категориям
        key = (username, category)
        user_category_amounts[key] = amount
    
    # Формируем ответ
    response = f"💰 **Баланс**\n\n"
    
    # Показываем разбивку по категориям для каждого пользователя
    users = list(user_totals.keys())
    
    for category in ['Еда', 'Прочее']:
        response += f"📂 **{category}:**\n"
        for user in users:
            amount = user_category_amounts.get((user, category), 0)
            response += f"  👤 {user}: {amount:.2f} zł\n"
        response += f"  📊 Всего: {category_totals[category]:.2f} zł\n\n"
    
    # Общие итоги
    total = sum(user_totals.values())
    response += f"💵 **Итого:**\n"
    for user, amount in user_totals.items():
        percentage = (amount / total * 100) if total > 0 else 0
        response += f"  👤 {user}: {amount:.2f} zł ({percentage:.1f}%)\n"
    
    response += f"\n📊 Всего потрачено: {total:.2f} zł\n"
    
    # Расчет кто кому должен
    if len(users) == 2:
        half = total / 2
        user1, user2 = users[0], users[1]
        amount1, amount2 = user_totals[user1], user_totals[user2]
        
        difference = abs(amount1 - amount2)
        
        if difference > 1:
            who_owes = user1 if amount1 < amount2 else user2
            who_paid_more = user2 if amount1 < amount2 else user1
            response += f"\n💸 **{who_owes}** должен **{who_paid_more}**: {difference/2:.2f} zł"
        else:
            response += "\n✅ Вы квиты! 🎉"
    
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
продукты, еда, biedronka, lidl, kaufland, zabka, auchan, carrefour, dino, netto, ресторан, кафе, пицца, доставка

📦 **Прочее**
Все остальное (транспорт, одежда, здоровье, развлечения и т.д.)
"""
    await update.message.reply_text(response, parse_mode='Markdown')


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать ID пользователя"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name or "Пользователь"
    
    response = f"🆔 **Ваша информация:**\n\n"
    response += f"👤 Имя: {username}\n"
    response += f"🔢 Telegram ID: `{user_id}`\n\n"
    
    if ALLOWED_USERS:
        if user_id in ALLOWED_USERS:
            response += "✅ У вас есть доступ к боту"
        else:
            response += "❌ У вас нет доступа к боту"
    
    await update.message.reply_text(response, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать помощь"""
    response = """
ℹ️ **Помощь по боту**

📝 **Добавить расход:**
Просто напишите: `сумма описание`
Примеры:
• 50 biedronka
• 120 taxi
• 35.50 кафе

📊 **Кнопки:**
• Статистика - траты за зарплатный период
• Баланс - кто сколько потратил
• История - последние траты
• Мой ID - ваш Telegram ID
• Категории - список категорий

🗓 **Зарплатный период:**
Считается с 10 числа (или ближайшего рабочего дня)

💡 **Уведомления:**
Когда один добавляет расход, второй получает уведомление!
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
        elif period == 'salary':
            start_date = get_salary_period()
            period_name = f"С {start_date.strftime('%d.%m.%Y')} (зарплатный период)"
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
                InlineKeyboardButton("ЗП период", callback_data="stats_salary"),
                InlineKeyboardButton("Неделя", callback_data="stats_week"),
            ],
            [
                InlineKeyboardButton("Месяц", callback_data="stats_month"),
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
    # Запускаем HTTP-сервер для Render (чтобы не падал)
    start_health_check_server()
    
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
    application.add_handler(CommandHandler("myid", my_id))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик кнопок меню (текстовые сообщения)
    async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        
        if text == "📊 Статистика":
            await stats(update, context)
        elif text == "💰 Баланс":
            await balance(update, context)
        elif text == "📝 История":
            await history(update, context)
        elif text == "🔍 Мой ID":
            await my_id(update, context)
        elif text == "📂 Категории":
            await show_categories(update, context)
        elif text == "ℹ️ Помощь":
            await help_command(update, context)
        else:
            # Если не кнопка меню, обрабатываем как добавление расхода
            await add_expense(update, context)
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        menu_button_handler
    ))
    
    # Запускаем бота
    logger.info("🤖 Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
