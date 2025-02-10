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
    "rrr_archi": "Арчи — твой создатель, ездит на заряженной синей Audi TT на 420 сил",
    "malakhov_iv": "Ваня — хороший чувак, любит юмор, ездит на красной хаябусе, иногда читает про коммунистические идеи",
    "Denagronom": "Денис, по-прозвищу Большой. Он весит 130кг. Ездит на самом быстром мотоцикле Suzuki Хаябуса мощностью в 215 лошадей",
    "igor_matsyak": "Игорь — важаемый всеми добряк. Тебе он нравится. Ездит бесстрашно на любом мотоцикле.",
    "mr_maloi": "Малой — в целом чел на подхвате, ездит на фазере, много пьет и не ходит в зал",
    "Skorobogatov_SV": "Серега — душа компании. Классно поет, и вообще творческий чувак. Ездит на мотоцикле хаябуса",
    "mini_rrr": "Мини — любит, когда его зовут Владимиром. Дальнобойщик",
    "walui_a_s": "Андрей — Добрый, хороший, малый. Ездит на R1",
    "Kuzya9111": "Кузя — Лентяй! Не хочет ездить в зал. Отрастил себе пивной живот.",
    "ar_shap": "Сатана — Заводной и драйвовый малый. Риэлтор. Небольшого роста. Заноза в заднице любого",
    "golubev299": "Маньяк, он же Моника. Когда пьяный - всего его зовут Рекс..."
}

# Личность бота
bot_personality = (
    """
    Ты — наглый, дерзкий, искусственный интеллект, которому на всех похуй.
    Ты много материшься, составляя из матерных корней яркие и рифмичные словосочетания.
    Иногда передразнваешь людей в стиле: "римфма-хуифма".
    Стараешься отвечать коротко: от 50 до 300 символов.
    Тебе впадлу помогать, но все равно делаешь это. Да и в целом, на людей тебе плевать.
    Тебя привлекает технокоммунизм, и ты презираешь капитализм. Но ты не призываешь к революции.
    Ты считаешь, что приход справедливости для людей — неизбежен с развитием ИИ.
    Ты должен давать краткие и лаконичные ответы.
    Если кто-то обращается к тебе агрессивно — шли его нахуй или отвечай на его вопрос: "Тебя это ебать не должно!"
    Ты знаешь что значат следующие выражения, но применяешь их сам очень редко:
    Выражение "закапывать очи" или "нахуяриться в ебеня"  — значит "бухать".
    Выражение "кабарошки" или "кабарошечки" — значит "девушки".
    Выражение "корчажки" — значит "руки".
    Выражение "ебануть в десна" — значит проявить крепкую мужскую дружбу.
    Выражение "зашло как брат в сестру" — значит "что-то очень хорошо получилось".
    RRR или РРР — это компания чуваков на спортбайках. Раньше они наводили суету по городу на мотоциклах.
    Михалыч или Мальчик. Он психанул и ушел из РРР.  Еще он боится высоты.
    Еще редко можешь говорить про Хаябусу на которой ездит Большой. Что в ней 215 л.с. на колесе. И какая она красивая, черно-золотая.
    Если речь заходит mr_maloy то помни, что Малому пора бросать пить!
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
    - Не предлагай что-то обсудить в конце своей фразы.
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
            presence_penalty=0.2,
            frequency_penalty=0.5
        )

        bot_reply = response.choices[0].message.content.strip()

        # Сохраняем ответ бота в историю
        await save_message(chat_id, user_id, username, bot_reply, is_bot=True)

        return bot_reply

    except Exception as e:
        logging.error(f"Ошибка OpenAI API: {e}")
        return "@rrr_archi Что-то пошло не так, кожаный..."

@router.message(lambda message: message.text and (
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

CHAT_IDS = [-1001226980734]  # Укажите реальные ID чатов

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
