import asyncio
import hmac
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiohttp import web

import config
from faq import FAQ

router = Router()
APPLY = "Оставить заявку"
MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=k) for k in FAQ], [KeyboardButton(text=APPLY)]],
    resize_keyboard=True,
)


class Lead(StatesGroup):
    name = State()
    contact = State()
    message = State()


@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(f"Здравствуйте! Сайт: {config.SITE_URL}\nВыберите раздел:", reply_markup=MENU)


@router.message(Command("cancel"))
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Отменено.", reply_markup=MENU)


@router.message(F.text == APPLY)
async def lead_start(m: Message, state: FSMContext):
    await state.set_state(Lead.name)
    await m.answer("Как вас зовут? (/cancel для отмены)", reply_markup=ReplyKeyboardRemove())


@router.message(Lead.name, F.text)
async def lead_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(Lead.contact)
    await m.answer("Телефон или email для связи?")


@router.message(Lead.contact, F.text)
async def lead_contact(m: Message, state: FSMContext):
    await state.update_data(contact=m.text)
    await state.set_state(Lead.message)
    await m.answer("Коротко опишите задачу.")


@router.message(Lead.message, F.text)
async def lead_done(m: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    await state.clear()
    user = f"@{m.from_user.username}" if m.from_user.username else f"id {m.from_user.id}"
    await bot.send_message(
        config.ADMIN_CHAT_ID,
        f"Новая заявка\nИмя: {d['name']}\nКонтакт: {d['contact']}\nЗадача: {m.text}\nTelegram: {user}",
    )
    await m.answer("Спасибо! Заявка отправлена, скоро свяжемся.", reply_markup=MENU)


@router.message(F.text.in_(FAQ.keys()))
async def faq(m: Message):
    await m.answer(FAQ[m.text])


@router.message()
async def fallback(m: Message):
    await m.answer("Выберите пункт меню.", reply_markup=MENU)


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
