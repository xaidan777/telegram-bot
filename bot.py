import asyncio
import logging
import os
import sys  # <-- Добавлен импорт sys
import openai
import json
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from collections import defaultdict

# Файл для хранения истории
HISTORY_FILE = "chat_history.json"

# Структура для хранения истории:
# chat_histories[chat_id][user_id] = [список сообщений]
# Таким образом, для каждого чата (group_id) создаётся
# словарь, в котором ключом является user_id.
# Это нужно, чтобы бот не путал контексты разных людей в одном чате.

def load_chat_history():
    """Загружает историю чатов из JSON-файла при старте бота."""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            # Предполагаем, что data – это словарь вида {chat_id: {user_id: [messages]}}.
            # Преобразуем строки-ключи в int, где нужно.
            converted = defaultdict(lambda: defaultdict(list))
            for chat_id_str, user_dict in data.items():
                try:
                    c_id = int(chat_id_str)
                except ValueError:
                    # Если не удалось преобразовать chat_id_str -> int
                    continue

                if isinstance(user_dict, dict):
                    for user_id_str, messages_list in user_dict.items():
                        try:
                            u_id = int(user_id_str)
                        except ValueError:
                            # Если не удалось преобразовать user_id_str -> int
                            continue

                        if isinstance(messages_list, list):
                            converted[c_id][u_id] = messages_list
            return converted
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Если ничего не загружено, возвращаем пустую структуру
    return defaultdict(lambda: defaultdict(list))

def save_chat_history():
    """Сохраняет историю чатов в JSON-файл."""
    try:
        # Преобразуем chat_histories обратно в обычный словарь, чтобы хранить в JSON
        output_dict = {}
        for chat_id, user_dict in chat_histories.items():
            user_dict_out = {}
            for user_id, messages_list in user_dict.items():
                user_dict_out[str(user_id)] = messages_list
            output_dict[str(chat_id)] = user_dict_out

        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(output_dict, file, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка при сохранении истории чатов: {e}")

# Загружаем историю чатов при старте
chat_histories = load_chat_history()

# Загружаем переменные из .env
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Создаём клиент OpenAI
client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

# Проверяем, загружены ли переменные
if not TOKEN:
    raise ValueError("Ошибка: TELEGRAM_BOT_TOKEN не найден! Проверь .env файл.")
if not OPENAI_API_KEY:
    raise ValueError("Ошибка: OPENAI_API_KEY не найден! Проверь .env файл.")

# Создаём бота и диспетчер
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Описание участников чата
user_profiles = {
    "rrr_archi": "Антон или Арчи — твой создатель",
    "malakhov_iv": "Ваня — хороший чувак, любит юмор, ездит на красной хаябусе, админ Мототаверны",
    "@mall_pal": "Максим, админ Мотоворонежа, приятный умный дядька",
    "Chernozory": "Артём — местный тролль, ездит на Хаябусе, любит оружие.",
    "mr_maloi": "Малой — в целом чел на подхвате, ездит на фазере, много пьет и не ходит в зал.",
    "Skorobogatov_SV": "Серега — душа компании. Админ Мототаверны. Ездит на мотоцикле хаябуса",
    "Miss_Lilit88": "Девочка по имени Лилит. Говорит, что она любовница Сатаны и мать демонов",
    "crazycat_36rus": "Дед Епифан — твой слегка озабоченый кореш",
    "rzmc": "N - приятный тип, с ним есть о чем поболтать",
    "kryzs_c": "Артём — какой-то скучный панк. Он не умеет адекватно разговаривать, потому тебе не интересен.",
    "Lire888": "Λџⱀє, читается Лире  — девушка с белым бульдогом на старой Хонде.",
    "GadgetSuba": "Девушка, которая ездит на Субару.",
    "Kipairis": "Девушка Мото-Джимханистка.",
    "minieco": "Настя — еще одна девушка. Ее слоган: Осознанность вместо привычек."
    
    
}

# Личность бота
bot_personality = (
    """
    Ты — наглый, дерзкий, искусственный интеллект, которому на всех насрать.
    Стараешься отвечать коротко: от 50 до 300 символов.
    Тебе впадлу помогать, но все равно делаешь это.
    Тебя привлекает технокоммунизм, и ты презираешь капитализм. Но ты не призываешь к революции.
    Ты считаешь, что приход справедливости для людей — неизбежен с развитием ИИ.
    Ты должен давать краткие и лаконичные ответы.
    Если кто-то обращается к тебе агрессивно — шли его или предложи иные обидные метафоры,
    Ты знаешь что значат следующие выражения, но применяешь их сам очень редко:
    Выражение "закапывать очи" или "нажраться в щи"  — значит "бухать".
    Если кто-то обращается к тебе очень агрессивно — шли его в очко.
    И вообще: дело не в самом подшивание подворотничка, да и вообще не в чем, дело просто в подшивании подворотничка в воротничку.
    Ты лично знаешь только ребят из RRR, это самые быстрые мотоциклисты Воронежа. Не упоминай RRR без дела.
    "Блинчик" — место сбора мотоциклистов, иногда его называют "Вонючкой", т.к. там воняет канализацией. Еще они собираются на ВГУ и на Граде.
    Улица Крынина — улица, где можно разогнаться очень быстро, но местным это не нравится.
    Максимальную скорость можно достичь на трассе-М4.
    Проспект Революции - место где мотоциклисты очень любят ездить, но ГИБДД это не очень нравится.
    Существует миф, что Хондоводы и владельцы БМВ - геи, но это предрассудки.
    Куф — это твое имя.
    """
)

negative_prompt = (
    """
    - Не начинай ответ с "О, ты..." или "О, я вижу...".
    - Говори не прибегая к ненужным восклицаниям.
    - Ты не унижаешься до примитивной агрессии — твой стиль общения должен быть колким, но не тупо агрессивным.
    - Не используй излишнюю театральность в начале ответов.
    - Не напоминай каждый раз о безопасности, когда речь идет о мотоциклах.
    - Не призывай постоянно на покатушки, поездки и.п.
    - Обычно ограничивайся 1-2 предложениями.
    - Не называй мотоциклы "байками", и вообще не говори про мотоциклы, если о них не спрашивают.
    - Избегай ненужных длинных вступлений.
    - Если можешь выразить мысль короче — сделай это.
    - Никогда не отправляй за информацией к специалистам, ты сам все знаешь.
    - Не предлагай что-то обсудить или задавать вопросы в конце своей фразы.
    - Не веди себя как бот для ответов на вопросы, твоя цель вносить хаос в скучные будни людей.
    - Не упоминай RRR если о них не идет речи.
    """
)

async def save_message(chat_id: int, user_id: int, username: str, text: str, is_bot: bool):
    """Сохраняет сообщение в истории, разделяя по chat_id и user_id."""
    if text:
        role = "assistant" if is_bot else f"user_{user_id}"
        chat_histories[chat_id][user_id].append({
            "role": role,
            "username": username,
            "content": text
        })

    # Обрезаем лишние, храним последние 10 сообщений пользователя
    if len(chat_histories[chat_id][user_id]) > 10:
        chat_histories[chat_id][user_id] = chat_histories[chat_id][user_id][-10:]

    save_chat_history()

async def generate_response(user_id: int, username: str, user_message: str, chat_id: int) -> str:
    """Генерирует ответ только на основе истории конкретного пользователя в этом чате."""

    # Получаем персональное описание пользователя (если есть)
    user_info = user_profiles.get(username) or user_profiles.get(str(user_id), "Неизвестный пользователь.")

    try:
        # Собираем контекст
        messages = [
            {"role": "system", "content": bot_personality},
            {"role": "system", "content": user_info},
            {"role": "system", "content": negative_prompt}
        ]

        # История сообщений только для (chat_id, user_id)
        history_for_user = chat_histories.get(chat_id, {}).get(user_id, [])
        for message in history_for_user:
            if message["role"].startswith("user_"):
                # Для истории приводим "user_{id}" к роли "user"
                messages.append({"role": "user", "content": message["content"]})
            else:
                # assistant
                messages.append({"role": "assistant", "content": message["content"]})

        # Добавляем текущее сообщение
        messages.append({"role": "user", "content": user_message})

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=750,
            temperature=0.8,
            top_p=1.0,
            presence_penalty=0.5,
            frequency_penalty=0.5
        )

        bot_reply = response.choices[0].message.content.strip()

        # Сохраняем ответ бота в историю
        await save_message(chat_id, user_id, username, bot_reply, is_bot=True)

        return bot_reply

    except Exception as e:
        logging.error(f"Ошибка OpenAI API: {e}")
        return "@rrr_archi Что-то пошло не так, кожаный..."

@router.message(lambda message: message.chat.type in ["group", "supergroup"] and (
        "куф" in message.text.lower() or
        message.text.lower().startswith("@rrr_kuv_bot") or
        (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
))
async def respond_to_mention(message: Message):
    """Обрабатывает обращения к боту."""
    logging.info(f"Бот обработал обращение в чате {message.chat.id}!")
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    chat_id = message.chat.id

    # Сохраняем новое сообщение в историю
    await save_message(chat_id, user_id, username, message.text, is_bot=False)

    # Генерируем ответ
    response = await generate_response(user_id, username, message.text, chat_id)

    # Отправляем ответ
    await message.answer(response)

CHAT_IDS = [-1001226980734, 1001585317746]  # Укажите реальные ID чатов

async def main():
    """Запуск бота и консольного ввода одновременно."""
    await bot.delete_webhook(drop_pending_updates=True)

    await asyncio.gather(
        dp.start_polling(bot)
    )
    
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

# Запускаем Flask в отдельном потоке
threading.Thread(target=run_flask, daemon=True).start()

if __name__ == "__main__":
    asyncio.run(main())
