import asyncio
import hmac
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiohttp import web

import config
from faq import FAQ as _FAQ

router = Router()

# Переименование кнопок меню без правки faq.py
LABELS = {"Услуги": "Подобрать материал"}
FAQ = {LABELS.get(k, k): v for k, v in _FAQ.items()}

APPLY = "Оставить заявку"
CALC = "Рассчитать расход"
DOCS = "Сертификаты"
MANAGER = "Написать менеджеру"
SKIP = "Пропустить"
WORK_HOURS = "Пн–Пт 9:00–17:00"

GREETING = (
    "Здравствуйте! Это КТ ТРОН Казахстан — официальный дистрибьютор завода в Алматы. "
    "Чем помочь?"
)

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=k) for k in FAQ],
        [KeyboardButton(text=CALC), KeyboardButton(text=DOCS)],
        [KeyboardButton(text=MANAGER), KeyboardButton(text=APPLY)],
    ],
    resize_keyboard=True,
)
PHONE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
)
SKIP_KB = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=SKIP)]], resize_keyboard=True)


def link(text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


class Lead(StatesGroup):
    name = State()
    phone = State()
    details = State()
    city = State()
    photo = State()


@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(GREETING, reply_markup=MENU)
    if config.SITE_URL:
        await m.answer("Наш сайт:", reply_markup=link("Открыть kttron.kz", config.SITE_URL))


@router.message(Command("cancel"))
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Отменено.", reply_markup=MENU)


@router.message(F.text == CALC)
async def calc(m: Message):
    await m.answer("Калькулятор расхода на сайте:", reply_markup=link(CALC, config.CALC_URL))


@router.message(F.text == DOCS)
async def docs(m: Message):
    await m.answer("Сертификаты и документы:", reply_markup=link(DOCS, config.DOCS_URL))


@router.message(F.text == MANAGER)
async def manager(m: Message):
    if config.WHATSAPP_URL:
        await m.answer(
            f"Менеджер на связи в WhatsApp ({WORK_HOURS}):",
            reply_markup=link("Написать в WhatsApp", config.WHATSAPP_URL),
        )
    else:
        await m.answer(f"Нажмите «{APPLY}», и менеджер свяжется с вами.")


@router.message(F.text == APPLY)
async def lead_start(m: Message, state: FSMContext):
    await state.set_state(Lead.name)
    await m.answer("Как вас зовут? (/cancel для отмены)", reply_markup=ReplyKeyboardRemove())


@router.message(Lead.name, F.text)
async def lead_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(Lead.phone)
    await m.answer("Нажмите кнопку, чтобы отправить номер, или введите его вручную.", reply_markup=PHONE_KB)


@router.message(Lead.phone, F.contact)
async def lead_phone_contact(m: Message, state: FSMContext):
    await _ask_details(m, state, m.contact.phone_number)


@router.message(Lead.phone, F.text)
async def lead_phone_text(m: Message, state: FSMContext):
    await _ask_details(m, state, m.text)


async def _ask_details(m: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    await state.set_state(Lead.details)
    await m.answer(
        "Что нужно? Укажите материал, объект и площадь.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Lead.details, F.text)
async def lead_details(m: Message, state: FSMContext):
    await state.update_data(details=m.text)
    await state.set_state(Lead.city)
    await m.answer("Город доставки?")


@router.message(Lead.city, F.text)
async def lead_city(m: Message, state: FSMContext):
    await state.update_data(city=m.text)
    await state.set_state(Lead.photo)
    await m.answer("Можно приложить фото дефекта или объекта.", reply_markup=SKIP_KB)


@router.message(Lead.photo, F.photo)
async def lead_photo(m: Message, state: FSMContext, bot: Bot):
    await _finish(m, state, bot, m.photo[-1].file_id)


@router.message(Lead.photo, F.text == SKIP)
async def lead_skip(m: Message, state: FSMContext, bot: Bot):
    await _finish(m, state, bot, None)


@router.message(Lead.photo)
async def lead_photo_hint(m: Message):
    await m.answer(f"Отправьте фото или нажмите «{SKIP}».")


async def _finish(m: Message, state: FSMContext, bot: Bot, photo_id: str | None):
    d = await state.get_data()
    await state.clear()
    user = f"@{m.from_user.username}" if m.from_user.username else f"id {m.from_user.id}"
    text = (
        "Новая заявка\n"
        f"Имя: {d['name']}\n"
        f"Телефон: {d['phone']}\n"
        f"Что нужно: {d['details']}\n"
        f"Город: {d['city']}\n"
        f"Telegram: {user}"
    )
    if photo_id:
        await bot.send_photo(config.ADMIN_CHAT_ID, photo_id, caption=text)
    else:
        await bot.send_message(config.ADMIN_CHAT_ID, text)
    await m.answer(
        f"Спасибо! Менеджер свяжется с вами в рабочее время, {WORK_HOURS}.",
        reply_markup=MENU,
    )


@router.message(F.text.in_(FAQ.keys()))
async def faq(m: Message):
    await m.answer(FAQ[m.text])


@router.message()
async def fallback(m: Message):
    await m.answer(GREETING, reply_markup=MENU)


async def notify(request: web.Request) -> web.Response:
    """POST /notify  заголовок X-Secret, JSON {"text": "..."} -- уведомление с сайта."""
    if not hmac.compare_digest(request.headers.get("X-Secret", ""), config.NOTIFY_SECRET):
        return web.Response(status=403)
    try:
        text = str((await request.json())["text"])[:4000]
    except Exception:
        return web.Response(status=400)
    await request.app["bot"].send_message(config.ADMIN_CHAT_ID, text)
    return web.json_response({"ok": True})


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    app = web.Application()
    app["bot"] = bot
    app.add_routes([web.post("/notify", notify)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.WEBHOOK_PORT).start()
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
