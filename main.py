import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("Токен бота не найден! Создайте файл .env с BOT_TOKEN=your_token")
    exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Расписание (замените на своё)
SCHEDULE = {
    "понедельник": [
        "📚 9:00 - Математика",
        "📖 10:30 - Физика", 
        "💻 12:00 - Программирование",
        "🍽 13:30 - Обед",
        "📊 15:00 - Статистика"
    ],
    "вторник": [
        "🌐 9:00 - Веб-разработка",
        "📱 10:30 - Мобильные приложения",
        "🎨 12:00 - Дизайн",
        "🍽 13:30 - Обед",
        "📈 15:00 - Анализ данных"
    ],
    "среда": [
        "🤖 9:00 - Искусственный интеллект",
        "🔐 10:30 - Кибербезопасность",
        "☁️ 12:00 - Облачные технологии",
        "🍽 13:30 - Обед",
        "📊 15:00 - Базы данных"
    ],
    "четверг": [
        "📱 9:00 - iOS разработка",
        "🤖 10:30 - Android разработка",
        "🎮 12:00 - Геймдев",
        "🍽 13:30 - Обед",
        "💼 15:00 - Проектная работа"
    ],
    "пятница": [
        "🌍 9:00 - Английский язык",
        "💼 10:30 - Бизнес-аналитика",
        "🚀 12:00 - Стартапы",
        "🍽 13:30 - Обед",
        "📝 15:00 - Подведение итогов"
    ],
    "суббота": [
        "Отдыхай"
    ],
    "воскресенье": [
        "Отдыхай"
    ]
}

# Inline клавиатура с днями недели
def get_week_inline_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Понедельник", callback_data="day_понедельник")
            ],
            [
                InlineKeyboardButton(text="Вторник", callback_data="day_вторник")
            ],
            [
                InlineKeyboardButton(text="Среда", callback_data="day_среда")
            ],
            [
                InlineKeyboardButton(text="Четверг", callback_data="day_четверг")
            ],
            [
                InlineKeyboardButton(text="Пятница", callback_data="day_пятница")
            ],
            [
                InlineKeyboardButton(text="📅 Сегодня", callback_data="today"),
            ]
        ]
    )
    return keyboard

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = """
📅 Привет! Я бот с расписанием.

Выбери день недели чтобы увидеть расписание <3
    """
    await message.answer(welcome_text, reply_markup=get_week_inline_keyboard())


# Функция для показа расписания на сегодня
async def show_today_schedule(message: types.Message = None, callback: types.CallbackQuery = None):
    # Получаем текущий день недели (0-понедельник, 6-воскресенье)
    today_index = datetime.now().weekday()
    
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    today = days[today_index]
    
    schedule_today = SCHEDULE.get(today, [])
    
    if schedule_today:
        response = f"📅 Расписание на сегодня ({today.capitalize()}):\n\n"
        for lesson in schedule_today:
            response += f"• {lesson}\n"
    else:
        response = f"❌ Расписание на {today.capitalize()} не найдено"
    
    if callback:
        await callback.answer(response, show_alert=True)
    else:
        await message.answer(response)

# Функция для показа расписания на всю неделю
async def show_full_week(message: types.Message = None, callback: types.CallbackQuery = None):
    response = "📅 Расписание на всю неделю:\n\n"
    
    for day, lessons in SCHEDULE.items():
        response += f"🔹 {day.capitalize()}:\n"
        for lesson in lessons:
            response += f"   • {lesson}\n"
        response += "\n"
    
    if callback:
        # Для callback разбиваем на части если слишком длинное
        if len(response) > 200:
            parts = [response[i:i+200] for i in range(0, len(response), 200)]
            for part in parts[:3]:  # Максимум 3 части чтобы не спамить
                await callback.answer(part, show_alert=True)
                await asyncio.sleep(0.5)
        else:
            await callback.answer(response, show_alert=True)
    else:
        await message.answer(response)

# Функция для показа расписания конкретного дня (всплывающее сообщение)
async def show_day_schedule_popup(day: str, callback: types.CallbackQuery):
    schedule = SCHEDULE.get(day, [])
    
    if schedule:
        response = f"📅 Расписание на {day.capitalize()}:\n\n"
        for lesson in schedule:
            response += f"• {lesson}\n"
    else:
        response = f"❌ Расписание на {day.capitalize()} не найдено"
    
    # Показываем всплывающее сообщение
    await callback.answer(response, show_alert=True)

# Обработчик нажатий на inline кнопки
@dp.callback_query(F.data.startswith("day_"))
async def handle_day_callback(callback: types.CallbackQuery):
    day = callback.data.replace("day_", "")
    await show_day_schedule_popup(day, callback)

@dp.callback_query(F.data == "today")
async def handle_today_callback(callback: types.CallbackQuery):
    await show_today_schedule(callback=callback)

@dp.callback_query(F.data == "week")
async def handle_week_callback(callback: types.CallbackQuery):
    await show_full_week(callback=callback)

# Запуск бота
async def main():
    logger.info("Бот запускается...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
