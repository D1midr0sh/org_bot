import time
import threading
import secrets
from telebot import TeleBot, types

from .config import settings
from .llm.yandex_provider import YandexGPTProvider
from .processor import TextProcessor
from .security import RateLimiter, sanitize
from .utils.logger import setup_logger
from .utils.json_store import user_requests_store, user_settings_store

logger = setup_logger()


def make_provider():
    return YandexGPTProvider(
        api_key=settings.yandex_api_key or None,
        iam_token=settings.yandex_iam_token or None,
        folder_id=settings.yandex_folder_id,
        model=settings.yandex_model,
        api_url=settings.yandex_api_url,
    )


provider = make_provider()
processor = TextProcessor(provider)

bot = TeleBot(settings.telegram_token, parse_mode='HTML')
rl = RateLimiter()

# Ephemeral cache for inline explanations
EXPL_CACHE: dict[str, dict] = {}
EXPL_CACHE_MAX = 800

def _cache_expl(payload: dict) -> str:
    # Drop oldest items if too many
    if len(EXPL_CACHE) >= EXPL_CACHE_MAX:
        # naive cleanup: remove ~10% oldest by insertion order
        for k in list(EXPL_CACHE.keys())[: int(EXPL_CACHE_MAX * 0.1) or 1]:
            EXPL_CACHE.pop(k, None)
    token = secrets.token_urlsafe(8)
    payload['ts'] = time.time()
    EXPL_CACHE[token] = payload
    return token

STYLE_KB = types.InlineKeyboardMarkup()
STYLE_KB.add(
    types.InlineKeyboardButton("Стиль: авто", callback_data="style:auto"),
    types.InlineKeyboardButton("строгий", callback_data="style:strict"),
    types.InlineKeyboardButton("разговорный", callback_data="style:conversational"),
    types.InlineKeyboardButton("официальный", callback_data="style:formal"),
)


@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    bot.reply_to(message, "Пришлите текст до 500 символов — предложу русские замены заимствований. Есть инлайн: введите @имябота + текст.")


@bot.message_handler(commands=['style'])
def cmd_style(message):
    bot.reply_to(message, "Выберите стилевой режим:", reply_markup=STYLE_KB)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith('style:'))
def on_style_set(callback_query):
    style = callback_query.data.split(':', 1)[1]
    uid = str(callback_query.from_user.id)
    user_settings = user_settings_store.get() or {}
    prefs = user_settings.get(uid, {})
    prefs['style'] = style
    user_settings[uid] = prefs
    user_settings_store.set(user_settings)
    bot.answer_callback_query(callback_query.id, f"Стиль: {style}")


@bot.message_handler(content_types=['text'])
def on_text(message):
    user_id = message.from_user.id
    text = message.text or ''

    if len(text) > 500:
        bot.reply_to(message, "Пожалуйста, не больше 500 символов.")
        return

    if not rl.allowed(user_id):
        bot.reply_to(message, "Слишком часто. Попробуйте чуть позже.")
        return

    clean = sanitize(text)

    # User style preference
    prefs = user_settings_store.get() or {}
    style = prefs.get(str(user_id), {}).get('style', settings.style_mode)

    t0 = time.time()
    try:
        result = processor.process(clean, style=style)
        best = result['best']
        alts = result['alternatives']
        expl = result['explanation']

        resp = f"<b>Вариант:</b> {best}"
        if alts:
            resp += "\n<b>Альтернативы:</b>\n- " + "\n- ".join(alts)
        # Add buttons: show original and explanation
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("Оригинал", callback_data=f"orig:{message.message_id}"),
            types.InlineKeyboardButton("Пояснение", callback_data=f"explain:{message.message_id}")
        )
        bot.reply_to(message, resp, reply_markup=kb)

        # Save request for learning
        user_requests = user_requests_store.get() or {}
        arr = user_requests.get(str(user_id), [])
        arr.append({
            'input': text,
            'output': best,
            'alts': alts,
            't_ms': int((time.time()-t0)*1000),
        })
        # keep last 50
        arr = arr[-50:]
        user_requests[str(user_id)] = arr
        user_requests_store.set(user_requests)
    except Exception as e:
        logger.exception("processing failed")
        bot.reply_to(message, "Не удалось обработать запрос. Попробуйте позже.")


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith('orig:'))
def on_orig(callback_query):
    msg = callback_query.message
    original = msg.reply_to_message.text if msg and msg.reply_to_message else ''
    if not original:
        bot.answer_callback_query(callback_query.id, "Нет исходного текста.")
        return
    bot.answer_callback_query(callback_query.id, text=(original[:190] + '…' if len(original) > 190 else original), show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith('explain:'))
def on_explain(callback_query):
    # Recompute explanation quickly
    msg = callback_query.message
    original = msg.reply_to_message.text if msg and msg.reply_to_message else ''
    if not original:
        bot.answer_callback_query(callback_query.id, "Нет исходного текста.")
        return
    try:
        result = processor.process(original)
        expl = result.get('explanation') or 'Модель не предоставила пояснения.'
        bot.answer_callback_query(callback_query.id, text=(expl[:190] + '…' if len(expl) > 190 else expl), show_alert=True)
    except Exception:
        bot.answer_callback_query(callback_query.id, "Не удалось получить пояснение.")


# Админские команды словаря/статистики удалены для упрощения


@bot.inline_handler(func=lambda q: True)
def inline_query(query):
    text = query.query or ''
    try:
        if not text.strip():
            # Show hint when user typed @bot but no text
            results = [
                types.InlineQueryResultArticle(
                    id='hint',
                    title='Введите текст для замены англицизмов',
                    description='Например: хочу апгрейднуть ноут',
                    input_message_content=types.InputTextMessageContent(
                        'Введите текст для замены англицизмов'
                    ),
                )
            ]
            bot.answer_inline_query(
                query.id,
                results,
                cache_time=0,
                is_personal=True,
                switch_pm_text='Открыть чат с ботом',
                switch_pm_parameter='start',
            )
            return

        if len(text) > 500:
            text = text[:500]
        # Compute with an 8s deadline and answer once
        result_holder = {}
        done = threading.Event()

        def worker(qtext: str):
            t0 = time.time()
            try:
                r = processor.process(qtext)
                result_holder['result'] = r
                result_holder['dt'] = time.time() - t0
            except Exception:
                logger.exception('inline worker failed')
            finally:
                done.set()

        th = threading.Thread(target=worker, args=(text,), daemon=True)
        th.start()
        finished = done.wait(timeout=8.0)
        if finished and 'result' in result_holder:
            r = result_holder['result']
            best = r['best']
            alts = r['alternatives']
            expl = r.get('explanation') or ''
            token = _cache_expl({'original': text, 'explanation': expl})
            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("Оригинал", callback_data=f"iorig:{token}"),
                types.InlineKeyboardButton("Пояснение", callback_data=f"iexpl:{token}")
            )
            results = [
                types.InlineQueryResultArticle(
                    id='best',
                    title='Вариант',
                    description=best,
                    input_message_content=types.InputTextMessageContent(best),
                    reply_markup=kb,
                )
            ]
            for i, alt in enumerate(alts[:4], start=1):
                results.append(types.InlineQueryResultArticle(
                    id=f'alt{i}',
                    title=f'Альтернатива {i}',
                    description=alt,
                    input_message_content=types.InputTextMessageContent(alt),
                    reply_markup=kb,
                ))
            bot.answer_inline_query(query.id, results, cache_time=0, is_personal=True)
            try:
                logger.info("inline processed in %.2fs", result_holder.get('dt', 0.0))
            except Exception:
                pass
        else:
            # Timeout fallback to avoid Telegram 10s limit
            fallback = [
                types.InlineQueryResultArticle(
                    id='timeout',
                    title='Долго думаю…',
                    description='Нажмите, чтобы открыть чат с ботом',
                    input_message_content=types.InputTextMessageContent(
                        'Откройте чат с ботом — так быстрее'
                    ),
                )
            ]
            bot.answer_inline_query(
                query.id,
                fallback,
                cache_time=0,
                is_personal=True,
                switch_pm_text='Открыть чат с ботом',
                switch_pm_parameter='start',
            )
    except Exception as e:
        logger.exception('inline_query failed')
        try:
            fallback = [
                types.InlineQueryResultArticle(
                    id='error',
                    title='Не успел обработать запрос',
                    description='Откройте чат с ботом — там всё получится',
                    input_message_content=types.InputTextMessageContent(
                        'Откройте чат с ботом — там всё получится'
                    ),
                )
            ]
            bot.answer_inline_query(query.id, fallback, cache_time=0, is_personal=True,
                                    switch_pm_text='Открыть чат с ботом', switch_pm_parameter='start')
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith('iexpl:'))
def on_inline_explain(callback_query):
    token = callback_query.data.split(':', 1)[1]
    item = EXPL_CACHE.get(token)
    if not item:
        bot.answer_callback_query(callback_query.id, "Данные недоступны. Попробуйте ещё раз позже.")
        return
    original = item.get('original') or ''
    expl = item.get('explanation') or 'Модель не предоставила пояснения.'
    bot.answer_callback_query(callback_query.id, text=(expl[:190] + '…' if len(expl) > 190 else expl), show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith('iorig:'))
def on_inline_original(callback_query):
    token = callback_query.data.split(':', 1)[1]
    item = EXPL_CACHE.get(token)
    if not item:
        bot.answer_callback_query(callback_query.id, "Данные недоступны. Попробуйте ещё раз позже.")
        return
    original = item.get('original') or ''
    bot.answer_callback_query(callback_query.id, text=(original[:190] + '…' if len(original) > 190 else original), show_alert=True)


def run():
    logger.info("Starting bot...")
    # Ensure polling mode is clean (no webhook leftovers)
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    bot.infinity_polling(timeout=25, long_polling_timeout=20, allowed_updates=['message','inline_query','callback_query'])


if __name__ == '__main__':
    run()
