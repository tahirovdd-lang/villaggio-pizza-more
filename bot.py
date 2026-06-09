import os
import json
import logging
import asyncio
import re

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден в переменных окружения")

# ====== НАСТРОЙКИ VILLAGGIO ======
BOT_USERNAME = "Villaggio_pizza_more_bot"
ADMIN_ID = int(os.getenv("ADMIN_ID", "6013591658"))
WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    "https://tahirovdd-lang.github.io/villaggio-pizza-more/?v=1"
)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

WELCOME_3LANG = (
    "🇷🇺 <b>Добро пожаловать в Villaggio pizza&amp;more!</b> 👋\n"
    "Выберите любимые блюда итальянской кухни и оформите заказ — просто нажмите «Открыть» ниже.\n\n"
    "🇺🇿 <b>Villaggio pizza&amp;more ga xush kelibsiz!</b> 👋\n"
    "Sevimli italyan taomlaringizni tanlang va buyurtma bering — pastdagi «Ochish» tugmasini bosing.\n\n"
    "🇬🇧 <b>Welcome to Villaggio pizza&amp;more!</b> 👋\n"
    "Choose your favorite Italian dishes and place an order — just tap “Open” below."
)

MENU_BTN_TEXT = "Ochish / Открыть / Open"


def menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MENU_BTN_TEXT, web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
    )


async def send_welcome(message: types.Message):
    await message.answer(WELCOME_3LANG, reply_markup=menu_kb())


def safe_html(s) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    p = phone.strip()
    p = re.sub(r"[^\d+]", "", p)
    if p.startswith("998"):
        p = "+" + p
    return p


def get_first(data: dict, keys: list, default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def payment_label(val: str) -> str:
    v = str(val or "").strip().lower()

    if v in ("cash", "кэш", "кеш", "нал", "наличные", "naqd", "naqdi"):
        return "Наличные"

    if v in ("click", "klik"):
        return "Click"

    if v in ("online", "онлайн", "card", "карта", "karta", "plastik", "plastic"):
        return "Online / карта"

    return str(val or "—")


def type_label(val: str) -> str:
    v = str(val or "").strip().lower()

    if v in ("delivery", "доставка", "yetkazib berish"):
        return "Доставка"

    if v in ("pickup", "самовывоз", "takeaway", "olib ketish"):
        return "Самовывоз"

    return str(val or "—")


def build_user_link_html(from_user: types.User, data: dict) -> str:
    tg = data.get("tg") or {}
    username = tg.get("username") or from_user.username
    first_name = tg.get("first_name") or from_user.first_name or "Клиент"

    if username:
        u = safe_html(username.lstrip("@"))
        return f'👤 Клиент: <a href="https://t.me/{u}">@{u}</a>'

    return f'👤 Клиент: <a href="tg://user?id={from_user.id}">{safe_html(first_name)}</a>'


def build_phone_html(phone: str) -> str:
    p = normalize_phone(phone)
    if not p:
        return "📞 Телефон: <b>—</b>"
    return f'📞 Телефон: <a href="tel:{safe_html(p)}"><b>{safe_html(p)}</b></a>'


@dp.message(CommandStart())
async def start(message: types.Message, command: CommandObject = None):
    await send_welcome(message)


@dp.message(Command("menu"))
async def menu_cmd(message: types.Message):
    await send_welcome(message)


@dp.message(F.text == MENU_BTN_TEXT)
async def menu_button(message: types.Message):
    await send_welcome(message)


@dp.message(F.web_app_data)
async def webapp_order(message: types.Message):
    raw = message.web_app_data.data

    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    logging.info("WEBAPP DATA: %s", data)

    await message.answer(
        "✅ Заказ принят! Спасибо, что выбрали Villaggio pizza&amp;more 😊",
        reply_markup=menu_kb(),
    )

    order = data.get("order", {})
    items_list = data.get("items", [])
    customer = data.get("customer", {}) or {}

    items_lines = []

    if isinstance(items_list, list) and items_list:
        for it in items_list:
            name = (
                it.get("name_lang")
                or it.get("name_ru")
                or it.get("name")
                or it.get("id")
                or "—"
            )
            qty = it.get("qty") or 0
            price = it.get("price") or it.get("p") or ""
            if price:
                items_lines.append(
                    f"• {safe_html(name)} × <b>{safe_html(qty)}</b> — {safe_html(price)} сум"
                )
            else:
                items_lines.append(f"• {safe_html(name)} × <b>{safe_html(qty)}</b>")

    elif isinstance(order, dict) and order:
        for name, qty in order.items():
            items_lines.append(f"• {safe_html(name)} × <b>{safe_html(qty)}</b>")
    else:
        items_lines.append("• —")

    phone = (
        data.get("phone")
        or customer.get("phone")
        or data.get("phoneInput")
        or ""
    )

    address = (
        data.get("address")
        or customer.get("address")
        or data.get("addr")
        or data.get("addrInput")
        or ""
    )

    # Главное исправление: берём оплату из всех возможных названий
    payment_raw = get_first(data, [
        "payment",
        "pay",
        "paymentMethod",
        "payment_method",
        "payMethod",
        "pay_method",
        "payment_type",
        "pay_type",
    ], "")

    # Главное исправление: берём доставку/самовывоз из всех возможных названий
    type_raw = get_first(data, [
        "type",
        "order_type",
        "orderType",
        "fulfillment",
        "fulfillmentType",
        "deliveryType",
        "delivery_type",
        "receiveType",
        "receive_type",
    ], "")

    pay = payment_label(payment_raw)
    otype = type_label(type_raw)

    total = data.get("total", "—")
    total_num = data.get("total_num")
    comment = data.get("comment", "")
    order_id = data.get("order_id") or data.get("id") or "—"

    admin_text = (
        "📩 <b>НОВЫЙ ЗАКАЗ — Villaggio pizza&amp;more</b>\n\n"
        f"🧾 Заказ: <b>{safe_html(order_id)}</b>\n"
        f"{build_user_link_html(message.from_user, data)}\n"
        f"{build_phone_html(phone)}\n"
        f"🚚 Тип получения: <b>{safe_html(otype)}</b>\n"
        f"💳 Тип оплаты: <b>{safe_html(pay)}</b>\n"
        f"📍 Адрес: <b>{safe_html(address) if address else '—'}</b>\n"
    )

    if comment:
        admin_text += f"💬 Комментарий: <b>{safe_html(comment)}</b>\n"

    admin_text += "\n🍕 <b>Состав заказа:</b>\n"
    admin_text += "\n".join(items_lines)
    admin_text += "\n\n"

    if total_num is not None:
        try:
            admin_text += f"💰 Итого: <b>{safe_html(int(total_num))}</b> сум"
        except Exception:
            admin_text += f"💰 Итого: <b>{safe_html(total)}</b> сум"
    else:
        admin_text += f"💰 Итого: <b>{safe_html(total)}</b> сум"

    await bot.send_message(ADMIN_ID, admin_text)


@dp.message()
async def fallback(message: types.Message):
    await send_welcome(message)


async def main():
    logging.info("🚀 Villaggio pizza&more bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
