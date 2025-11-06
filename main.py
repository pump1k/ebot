import asyncio
import logging
import os
import aiohttp
import json
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "https://resp-spbkeit.ru")
API_USERNAME = os.getenv("API_USERNAME")  # username для JSON API
API_PASSWORD = os.getenv("API_PASSWORD")  # пароль для JSON API

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Глобальные переменные для токенов
access_token = None
refresh_token = None
token_expires_at = None

# Соответствие дней недели
DAYS_MAPPING = {
    "понедельник": 1,
    "вторник": 2,
    "среда": 3,
    "четверг": 4,
    "пятница": 5,
    "суббота": 6
}

DAYS_NAMES = {
    1: "Понедельник",
    2: "Вторник", 
    3: "Среда",
    4: "Четверг",
    5: "Пятница", 
    6: "Суббота"
}

LESSON_TIMES = {
    1: "8:30-10:00",
    2: "10:10-11:40", 
    3: "12:10-13:40",
    4: "14:00-15:30",
    5: "15:40-17:10", 
    6: "17:20-18:50",
    7: "19:00-20:30",
    8: "20:40-22:10"
}


# Храним выбранные группы пользователей
user_groups = {}

# Функция для получения JWT токена
async def get_jwt_token():
    """
    Получаем JWT токен через JSON API /login
    """
    global access_token, refresh_token, token_expires_at
    
    try:
        auth_data = {
            "username": API_USERNAME,
            "password": API_PASSWORD
        }
        logger.info("🔐 Получаем JWT токен...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/login",  # JSON API endpoint
                json=auth_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                logger.info(f"📡 Статус аутентификации: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    access_token = data["access_token"]
                    refresh_token = data["refresh_token"]
                    token_expires_at = datetime.fromisoformat(data["access_token_expires_at"])
                    
                    logger.info("✅ JWT токен успешно получен!")
                    return True
                    
                elif response.status == 400:
                    error_data = await response.json()
                    logger.error(f"❌ Ошибка 400: {error_data.get('msg', 'Неверный формат данных')}")
                    return False
                    
                elif response.status == 401:
                    error_data = await response.json()
                    logger.error(f"❌ Ошибка 401: {error_data.get('msg', 'Неверные учетные данные')}")
                    return False
                    
                else:
                    logger.error(f"❌ Ошибка {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"🚫 Ошибка при получении токена: {e}")
        return False

# Функция для обновления токена
async def refresh_jwt_token():
    """
    Обновляем JWT токен используя refresh token
    """
    global access_token, refresh_token, token_expires_at
    
    try:
        headers = {
            "Authorization": f"Bearer {refresh_token}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/refresh",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    access_token = data["access_token"]
                    refresh_token = data["refresh_token"]
                    token_expires_at = datetime.fromisoformat(data["access_token_expires_at"])
                    
                    logger.info("🔄 Токен успешно обновлен!")
                    return True
                else:
                    logger.error(f"❌ Ошибка обновления токена: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"🚫 Ошибка обновления токена: {e}")
        return False

# Функция для проверки валидности токена
async def ensure_valid_token():
    """
    Проверяем что токен валиден и при необходимости обновляем
    """
    global access_token, token_expires_at
    
    if not access_token:
        return await get_jwt_token()
    
    # Проверяем истечение токена (с запасом 5 минут)
    if token_expires_at and datetime.now() > token_expires_at - timedelta(minutes=5):
        logger.info("🔄 Токен скоро истекает, обновляем...")
        return await refresh_jwt_token()
    
    return True

# Функция для получения расписания
async def get_schedule(group_id, day_of_week):
    """
    Получаем расписание через API /api/get-schedule
    """
    # Убеждаемся что токен валиден
    if not await ensure_valid_token():
        return None
    
    try:
        params = {
            "group_id": group_id,
            "day_of_week": day_of_week
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"📅 Запрашиваем расписание: группа {group_id}, день {day_of_week}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/get-schedule",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                
                logger.info(f"📡 Статус получения расписания: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Расписание получено!")
                    
                    # ⭐ ВАЖНО: API возвращает {"data": {...}}
                    if "data" in data and "lessons" in data["data"]:
                        return data["data"]  # Возвращаем только data часть
                    else:
                        logger.error("❌ Неверная структура данных от API")
                        return None
                    
                elif response.status == 401:
                    # Токен невалиден, пробуем обновить
                    logger.warning("🔄 Токен невалиден, пробуем обновить...")
                    if await refresh_jwt_token():
                        return await get_schedule(group_id, day_of_week)
                    else:
                        return None
                        
                elif response.status == 400:
                    error_data = await response.json()
                    logger.error(f"❌ Ошибка 400: {error_data}")
                    return {"error": "bad_request", "message": error_data.get('msg', 'Неверные параметры')}
                        
                elif response.status == 404:
                    logger.error(f"❌ Расписание не найдено для группы {group_id}")
                    return {"error": "not_found", "message": "Расписание не найдено"}
                    
                elif response.status == 429:
                    logger.warning("⏳ Превышен лимит запросов")
                    return {"error": "rate_limit", "message": "Превышен лимит запросов"}
                    
                else:
                    logger.error(f"❌ Ошибка получения расписания: {response.status}")
                    error_text = await response.text()
                    logger.error(f"📄 Текст ошибки: {error_text}")
                    return None
                    
    except Exception as e:
        logger.error(f"🚫 Ошибка: {e}")
        return None



# Клавиатура выбора группы
def get_groups_keyboard():
    # ЗАМЕНИ НА РЕАЛЬНЫЕ ГРУППЫ ТВОЕГО КОЛЛЕДЖА
    groups = {
        "31": "31",
        "ISP-102": "ИСП-102", 
        "PROG-201": "ПРОГ-201",
        "PROG-202": "ПРОГ-202"
    }
    
    buttons = []
    for group_id, group_name in groups.items():
        buttons.append([InlineKeyboardButton(text=group_name, callback_data=f"group_{group_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура дней недели
def get_days_keyboard():
    buttons = []
    
    # Добавляем дни недели по два в ряд
    row = []
    for day_num in range(1, 7):  # 1-6
        day_name = DAYS_NAMES[day_num]
        row.append(InlineKeyboardButton(text=day_name, callback_data=f"day_{day_num}"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:  # Добавляем оставшиеся кнопки
        buttons.append(row)
    
    # Дополнительные кнопки
    buttons.extend([
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="today")],
        [InlineKeyboardButton(text="🔄 Сменить группу", callback_data="change_group")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Проверяем аутентификацию
    if not await ensure_valid_token():
        await message.answer("❌ Ошибка подключения к API. Проверь учетные данные.")
        return
    
    user_id = message.from_user.id
    
    if user_id not in user_groups:
        await message.answer("👋 Привет! Я бот с расписанием занятий.\n\n📚 Выбери свою группу:", 
                           reply_markup=get_groups_keyboard())
    else:
        group_name = user_groups[user_id]
        await message.answer(f"📅 Твоя группа: {group_name}\n\nВыбери день для просмотра расписания:", 
                           reply_markup=get_days_keyboard())

# Обработчик выбора группы
@dp.callback_query(F.data.startswith("group_"))
async def handle_group_select(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    group_id = callback.data.replace("group_", "")
    
    user_groups[user_id] = group_id
    
    await callback.message.edit_text(
        f"✅ Группа {group_id} выбрана!\n\nВыбери день для просмотра расписания:",
        reply_markup=get_days_keyboard()
    )

# Обработчик выбора дня
@dp.callback_query(F.data.startswith("day_"))
async def handle_day_select(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_groups:
        await callback.answer("❌ Сначала выбери группу!", show_alert=True)
        return
    
    day_number = int(callback.data.replace("day_", ""))
    group_id = user_groups[user_id]
    
    await callback.answer("⏳ Загружаем расписание...")
    
    # Получаем расписание
    schedule_data = await get_schedule(group_id, day_number)
    
    if isinstance(schedule_data, dict) and "error" in schedule_data:
        error_message = schedule_data.get("message", "Произошла ошибка")
        await callback.message.answer(f"❌ {error_message}")
        return
    
    if schedule_data:
        response = format_schedule_response(schedule_data, group_id, day_number)
        
        # ⭐ ВАЖНО: Отправляем обычным сообщением вместо всплывающего окна
        if len(response) > 4000:  # Telegram ограничение на сообщение
            # Разбиваем на части
            parts = split_long_message(response)
            for part in parts:
                await callback.message.answer(part)
        else:
            await callback.message.answer(response)
    else:
        await callback.message.answer("❌ Не удалось загрузить расписание")

# Обработчик "Сегодня"
@dp.callback_query(F.data == "today")
async def handle_today(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_groups:
        await callback.answer("❌ Сначала выбери группу!", show_alert=True)
        return
    
    # Определяем сегодняшний день
    today_number = datetime.now().weekday() + 1  # 1-понедельник, 6-суббота
    
    if today_number > 6:  # Воскресенье
        await callback.message.answer("📅 Сегодня воскресенье - выходной! 🎉")
        return
    
    group_id = user_groups[user_id]
    
    await callback.answer("⏳ Загружаем расписание на сегодня...")
    
    schedule_data = await get_schedule(group_id, today_number)
    
    if isinstance(schedule_data, dict) and "error" in schedule_data:
        error_message = schedule_data.get("message", "Произошла ошибка")
        await callback.message.answer(f"❌ {error_message}")
        return
    
    if schedule_data:
        response = format_schedule_response(schedule_data, group_id, today_number, "сегодня")
        
        if len(response) > 4000:
            parts = split_long_message(response)
            for part in parts:
                await callback.message.answer(part)
        else:
            await callback.message.answer(response)
    else:
        await callback.message.answer("❌ Не удалось загрузить расписание на сегодня")
# Обработчик смены группы
@dp.callback_query(F.data == "change_group")
async def handle_change_group(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔄 Выбери свою группу:",
        reply_markup=get_groups_keyboard()
    )


def split_long_message(text, max_length=4000):
    """
    Разбивает длинное сообщение на части
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        
        # Ищем последний перенос строки перед max_length
        split_pos = text.rfind('\n', 0, max_length)
        
        if split_pos == -1:
            # Если нет переносов - разбиваем по границе слова
            split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1:
                # Если нет пробелов - принудительно обрезаем
                split_pos = max_length
        
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    
    return parts

# Функция форматирования расписания
def format_schedule_response(schedule_data, group_id, day_number, day_prefix=""):
    """
    Форматируем расписание компактно чтобы влезало в сообщения
    """
    day_name = DAYS_NAMES[day_number]
    day_display = f"{day_prefix} ({day_name})" if day_prefix else day_name
    
    response = f"📅 <b>{group_id} - {day_display}</b>\n\n"
    
    # ⭐ ВАЖНО: Используем HTML разметку для компактности
    if isinstance(schedule_data, dict) and "lessons" in schedule_data:
        lessons = schedule_data["lessons"]
        
        if lessons:
            # Словарь для преобразования номеров пар во время
            lesson_times = {
                1: "8:30-10:00",
                2: "10:10-11:40", 
                3: "12:10-13:40",
                4: "14:00-15:30",
                5: "15:40-17:10",
                6: "17:20-18:50",
                7: "19:00-20:30",
                8: "20:40-22:10"
            }
            
            for lesson in lessons:
                lesson_num = lesson.get("lesson_num", 0)
                time_slot = lesson_times.get(lesson_num, "??:??")
                
                # ⭐ КОМПАКТНЫЙ ФОРМАТ:
                response += f"<b>🕒 {time_slot}</b>\n"
                response += f"   {lesson.get('subject', 'Предмет не указан')}\n"
                
                teacher = lesson.get('teacher', '')
                classroom = lesson.get('classroom', '')
                
                if teacher and classroom:
                    response += f"   👨‍🏫 {teacher} | 🏫 {classroom}\n"
                elif teacher:
                    response += f"   👨‍🏫 {teacher}\n"
                elif classroom:
                    response += f"   🏫 {classroom}\n"
                
                response += "\n"
        else:
            response += "🎉 <b>Занятий нет! Отдыхай!</b> 😊\n"
    else:
        response += "❌ <b>Расписание не найдено</b>\n"
    
    return response

# Команда для проверки статуса
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if await ensure_valid_token():
        status_text = "✅ Подключение к API активно\n"
        if token_expires_at:
            expires_in = token_expires_at - datetime.now()
            status_text += f"⏰ Токен истекает через: {expires_in}\n"
        status_text += f"🔑 Группы доступны: {len(get_groups_keyboard().inline_keyboard)}"
    else:
        status_text = "❌ Нет подключения к API"
    
    await message.answer(status_text)

# Команда для тестирования API
@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    """Тестируем подключение к API"""
    await message.answer("🧪 Тестируем API...")
    
    if await ensure_valid_token():
        # Пробуем получить расписание для тестовой группы
        test_group = "ISP-101"
        test_day = 1
        
        schedule_data = await get_schedule(test_group, test_day)
        
        if schedule_data:
            await message.answer(f"✅ API работает!\nТестовый запрос: группа {test_group}, день {test_day}")
        else:
            await message.answer("✅ Аутентификация работает, но расписание не найдено")
    else:
        await message.answer("❌ Ошибка аутентификации")

async def main():
    # Проверяем настройки
    if not all([BOT_TOKEN, API_USERNAME, API_PASSWORD]):
        missing = []
        if not BOT_TOKEN: missing.append("BOT_TOKEN")
        if not API_USERNAME: missing.append("API_USERNAME")
        if not API_PASSWORD: missing.append("API_PASSWORD")
        
        logger.error(f"❌ Отсутствуют переменные: {', '.join(missing)}")
        return
    
    logger.info("🚀 Запускаем бота с JWT аутентификацией...")
    
    # Пробуем аутентифицироваться при старте
    if await ensure_valid_token():
        logger.info("✅ Бот успешно запущен!")
        await dp.start_polling(bot)
    else:
        logger.error("❌ Не удалось аутентифицироваться в API")

if __name__ == "__main__":
    asyncio.run(main())