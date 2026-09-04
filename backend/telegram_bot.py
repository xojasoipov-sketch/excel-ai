"""Telegram bot for ExcelYordamchi AI — same brain as the website.

Runs two ways:
  - `python telegram_bot.py` — standalone polling process (local dev).
  - Embedded in the FastAPI app (see app/main.py's startup hook) as a background
    asyncio task on the *same* free Render web service, so no second paid
    background-worker instance is needed.

Feature parity with the website:
  - Fileless formula chat and file-upload + chat.
  - The exact same free-plan daily quota, Pro/owner bypass, and `usage_events`
    table as the site (app/quota.py).
  - An inline-button menu (📚 Kutubxona, 💎 Narxlar, ℹ️ Yordam) — browsing the
    24-template Formula Library and testing a formula is all tap-driven, no
    typing commands required. /library and /test still work by hand for
    power users.
  - 💎 Narxlar shows the Free vs Pro comparison in-chat (not just a link out).
  - /admin (owner-only) mirrors GET /api/admin/stats.
  - A native Telegram "/" command menu (set via set_my_commands) so the
    available commands are discoverable without being told about them.
"""
import asyncio
import logging
import os
import uuid
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app import admin as admin_service
from app import formula_lab
from app.agent import ExcelAgent
from app.billing import PLAN_PRICE_USD, SITE_URL
from app.excel_export import build_workbook_for_formula
from app.excel_utils import ExcelUtils
from app.quota import FREE_DAILY_LIMIT, enforce_ai_quota, quota_status
from app.telegram_identity import get_or_create_telegram_profile

load_dotenv()
log = logging.getLogger("telegram_bot")

MAX_TELEGRAM_MESSAGE = 3500  # stay under Telegram's 4096-char hard limit

REGISTERED_BANNER = (
    "✅ *Ro'yxatdan muvaffaqiyatli o'tdingiz!*\n"
    "Endi sizda kuniga {limit} ta bepul AI so'rov huquqi bor.\n\n"
).format(limit=FREE_DAILY_LIMIT)

WELCOME_TEXT = (
    "👋 Salom! Men *ExcelYordamchi AI* botiman.\n\n"
    "Excel formulani o'zbekcha, ruscha yoki inglizcha yozing — masalan:\n"
    "\"A ustundagi sonlar yig'indisini hisobla\"\n\n"
    "Jadval faylini (XLSX/CSV) yuborsangiz, u haqida savol bera olasiz.\n\n"
    "Quyidagi tugmalardan foydalaning 👇"
)

HELP_TEXT = (
    "ℹ️ *Bot nima qila oladi?*\n\n"
    "💬 *Formula so'rash* — shunchaki savolingizni yozing, formula va izoh olasiz.\n"
    "📎 *Fayl yuborish* — XLSX/CSV yuboring, keyin fayl haqida savol bering.\n"
    "📚 *Kutubxona* — 24 ta tayyor formula shabloni, AI kerak emas, bepul va cheksiz.\n"
    "🧪 *Sinash* — kutubxonadagi formulani namuna (yoki o'z) qiymatlar bilan sinab ko'rish.\n"
    "💎 *Pro* — kuniga limitsiz AI so'rov, $%s/oy.\n\n"
    "Buyruqlar: /start /library /price /test /upgrade /help"
) % f"{PLAN_PRICE_USD:g}"

CATEGORY_LABELS = {c["id"]: c["label"] for c in formula_lab.CATEGORIES}


def _profile(update: Update) -> dict:
    user = update.effective_user
    profile, _ = get_or_create_telegram_profile(user.id, user.username or "")
    return profile


def _quota_denied_text(detail) -> str:
    message = detail.get("message") if isinstance(detail, dict) else str(detail)
    return f"{message}\n\n💎 Cheksiz foydalanish: /price"


# ─── Keyboards ──────────────────────────────────────────────────────────────

# Inline buttons scroll out of view as the conversation grows, which pushes
# people to re-send /start just to get the menu back. This persistent keyboard
# sits above the input box and never scrolls away.
BTN_LIBRARY = "📚 Kutubxona"
BTN_PRICE = "💎 Narxlar"
BTN_HELP = "ℹ️ Yordam"


def persistent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_LIBRARY), KeyboardButton(BTN_PRICE), KeyboardButton(BTN_HELP)]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Formulani so'rang yoki tugmani bosing…",
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Formula kutubxonasi", callback_data="menu:library")],
        [InlineKeyboardButton("💎 Narxlar / Pro", callback_data="menu:price")],
        [InlineKeyboardButton("ℹ️ Yordam", callback_data="menu:help")],
    ])


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:main")]])


def category_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"cat:{cat_id}")] for cat_id, label in CATEGORY_LABELS.items()]
    rows.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def formula_list_keyboard(category_id: str) -> InlineKeyboardMarkup:
    items = [i for i in formula_lab.FORMULA_LIBRARY if i["category"] == category_id]
    rows = [[InlineKeyboardButton(item["name"], callback_data=f"fx:{item['id']}")] for item in items]
    rows.append([
        InlineKeyboardButton("🔙 Turkumlar", callback_data="menu:library"),
        InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:main"),
    ])
    return InlineKeyboardMarkup(rows)


def formula_detail_keyboard(category_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Ushbu turkumga", callback_data=f"cat:{category_id}")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:main")],
    ])


def price_keyboard(show_upgrade: bool) -> InlineKeyboardMarkup:
    rows = []
    if show_upgrade:
        rows.append([InlineKeyboardButton(f"💳 Pro'ga o'tish — ${PLAN_PRICE_USD:g}/oy", url=f"{SITE_URL}/billing")])
    rows.append([InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def price_text(profile: dict) -> str:
    status = quota_status(profile)
    if status["unlimited"]:
        current = "✅ Sizda hozir *cheksiz* foydalanish huquqi bor."
    else:
        current = f"Sizda hozir: bugun {status['remaining']} / {status['limit']} bepul so'rov qoldi."
    return (
        "💎 *Narxlar*\n\n"
        f"🆓 *Bepul* — kuniga {FREE_DAILY_LIMIT} ta AI so'rov, formula kutubxonasi va sinash rejimi cheksiz.\n\n"
        f"💎 *Pro — ${PLAN_PRICE_USD:g}/oy* — cheksiz AI so'rov, cheksiz fayl tahlili.\n\n"
        "To'lov: 💳 Karta (Visa/Mastercard). Payme va Click — tez orada.\n\n"
        f"{current}"
    )


def _formula_result_text(item: dict, cells: dict, overrides_used: bool) -> str:
    ok, result = formula_lab.evaluate(item["id"], cells)
    cells_line = ", ".join(f"{k}={v}" for k, v in cells.items() if v not in (None, "")) or "(bo'sh)"
    status_line = "sizning qiymatlaringiz bilan" if overrides_used else "namuna qiymatlar bilan"
    body = f"✅ Natija: `{result}`" if ok else f"⚠️ {result}"
    return (
        f"*{item['name']}*\n`{item['formula']}`\n{item['description']}\n\n"
        f"Katakchalar ({status_line}): {cells_line}\n\n{body}\n\n"
        f"Boshqa qiymat bilan sinash: `/test {item['id']} A1=... B1=...`"
    )


# ─── Commands ───────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    profile, is_new = get_or_create_telegram_profile(user.id, user.username or "")

    status = quota_status(profile)
    if status["unlimited"]:
        status_line = "\n\n✅ Sizda *cheksiz* foydalanish huquqi bor."
    else:
        status_line = f"\n\nBugun qoldi: *{status['remaining']} / {status['limit']}* bepul so'rov."

    text = (REGISTERED_BANNER if is_new else "") + WELCOME_TEXT + status_line
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=persistent_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main_keyboard())


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    show_upgrade = not (profile.get("is_owner") or profile.get("plan") == "pro")
    await update.message.reply_text(
        price_text(profile), parse_mode=ParseMode.MARKDOWN, reply_markup=price_keyboard(show_upgrade)
    )


async def library(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("📚 Qaysi turkum kerak?", reply_markup=category_keyboard())
        return

    results = formula_lab.search_library(query)[:8]
    if not results:
        await update.message.reply_text("Hech narsa topilmadi. Masalan: /library sumif")
        return

    lines = [f"🔎 «{query}» bo'yicha natijalar:"]
    for item in results:
        lines.append(f"\n*{item['name']}*\n`{item['formula']}`\n{item['description']}\n/test {item['id']}")
    await update.message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main_keyboard()
    )


async def test_formula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Foydalanish: /test <formula_id> [A1=qiymat B1=qiymat ...]\n"
            "Shablonlarni ko'rish uchun: /library",
            reply_markup=category_keyboard(),
        )
        return

    formula_id = context.args[0]
    item = formula_lab.find_by_id(formula_id)
    if not item:
        await update.message.reply_text(f"«{formula_id}» topilmadi.", reply_markup=category_keyboard())
        return

    cells = dict(item["sample"])
    overrides_used = False
    for token in context.args[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        cells[key.strip().upper()] = value.strip()
        overrides_used = True

    await update.message.reply_text(
        _formula_result_text(item, cells, overrides_used),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=formula_detail_keyboard(item["category"]),
    )


async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await price_command(update, context)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    if not profile.get("is_owner"):
        return  # silently ignore for non-owners, same as the website's 403
    s = admin_service.get_stats()
    await update.message.reply_text(
        "📊 *Admin statistikasi*\n\n"
        f"Jami foydalanuvchi: {s['total_users']}\n"
        f"To'laydigan (Pro): {s['paying_users']}\n"
        f"Promokod bilan Pro: {s['promo_pro_users']}\n"
        f"Bepul: {s['free_users']}\n\n"
        f"MRR: ${s['mrr_usd']:g}\n"
        f"Jami tushum: ${s['revenue_total_usd']:g}\n"
        f"So'nggi 30 kun: ${s['revenue_30d_usd']:g}\n\n"
        f"Bugungi AI so'rovlar: {s['ai_calls_today']}\n"
        f"So'nggi 7 kunlik ro'yxatdan o'tish: {s['signups_7d']}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def on_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Taps on the persistent keyboard arrive as ordinary text messages. They're
    routed here — and registered ahead of the AI handler — so a menu tap never
    gets sent to the model and never burns a quota call."""
    text = (update.message.text or "").strip()
    if text == BTN_LIBRARY:
        await library(update, context)
    elif text == BTN_PRICE:
        await price_command(update, context)
    elif text == BTN_HELP:
        await help_command(update, context)


# ─── Inline button taps ─────────────────────────────────────────────────────

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "menu:main":
        await query.edit_message_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard())
    elif data == "menu:library":
        await query.edit_message_text("📚 Qaysi turkum kerak?", reply_markup=category_keyboard())
    elif data == "menu:help":
        await query.edit_message_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main_keyboard())
    elif data == "menu:price":
        profile = _profile(update)
        show_upgrade = not (profile.get("is_owner") or profile.get("plan") == "pro")
        await query.edit_message_text(
            price_text(profile), parse_mode=ParseMode.MARKDOWN, reply_markup=price_keyboard(show_upgrade)
        )
    elif data.startswith("cat:"):
        category_id = data.split(":", 1)[1]
        label = CATEGORY_LABELS.get(category_id, category_id)
        await query.edit_message_text(f"📚 {label}:", reply_markup=formula_list_keyboard(category_id))
    elif data.startswith("fx:"):
        formula_id = data.split(":", 1)[1]
        item = formula_lab.find_by_id(formula_id)
        if not item:
            await query.edit_message_text("Topilmadi.", reply_markup=category_keyboard())
            return
        await query.edit_message_text(
            _formula_result_text(item, dict(item["sample"]), overrides_used=False),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=formula_detail_keyboard(item["category"]),
        )


# ─── Formula chat (fileless) ────────────────────────────────────────────────

async def answer_formula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = _profile(update)
    try:
        enforce_ai_quota(profile)
    except HTTPException as limit_error:
        await update.message.reply_text(_quota_denied_text(limit_error.detail), reply_markup=back_to_main_keyboard())
        return

    await update.message.chat.send_action("typing")
    agent: ExcelAgent = context.application.bot_data["agent"]
    try:
        response = await asyncio.to_thread(
            agent.quick_chat,
            [
                {"role": "system", "content": (
                    "You are ExcelYordamchi AI. Generate safe, exact Microsoft Excel formulas. "
                    "Reply in the user's language (Uzbek, Russian, or English). Put the formula alone "
                    "in an Excel code block, then give a very short explanation. Ask one question if "
                    "cell references, ranges, or conditions are essential but missing."
                )},
                {"role": "user", "content": update.message.text},
            ],
        )
        await update.message.reply_text(response[:MAX_TELEGRAM_MESSAGE])
        await _send_formula_workbook(update, response)
    except Exception as error:
        log.exception("quick_chat failed")
        await update.message.reply_text(f"AI javob bera olmadi: {error}")


async def _send_formula_workbook(update: Update, ai_response_text: str) -> None:
    """A bare formula string is only useful if the user's own sheet happens to
    match those exact cell letters — send a real .xlsx (sample data + the live
    formula) so there's something they can actually open and use."""
    try:
        workbook_bytes = build_workbook_for_formula(ai_response_text)
    except Exception:
        log.exception("excel_export failed")
        return
    if not workbook_bytes:
        return
    await update.message.reply_document(
        document=InputFile(BytesIO(workbook_bytes), filename="formula_namuna.xlsx"),
        caption="📊 Namuna jadval + tayyor formula. Ochib, o'z ma'lumotlaringizni joylashtiring.",
    )


# ─── File upload + chat about it ────────────────────────────────────────────

async def handle_spreadsheet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv", ".tsv"}:
        await update.message.reply_text("Iltimos, XLSX, XLS, CSV yoki TSV fayl yuboring.")
        return
    if document.file_size and document.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("Fayl 10 MB dan kichik bo'lishi kerak.")
        return

    upload_dir = Path(__file__).parent / "uploads" / "telegram"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{update.effective_chat.id}-{uuid.uuid4()}{suffix}"
    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(custom_path=str(file_path))

    try:
        excel_utils = ExcelUtils(str(file_path))
        df = excel_utils.get_dataframe()
        context.chat_data["excel_utils"] = excel_utils
        context.chat_data["file_name"] = document.file_name or file_path.name
        context.chat_data["history"] = [{
            "role": "system",
            "content": f"""You are ExcelYordamchi AI. Reply in the user's language: Uzbek, Russian, or English.
The user uploaded a spreadsheet with {len(df)} rows and {len(df.columns)} columns.
Headers: {', '.join(map(str, df.columns))}. Preview:\n{df.head().to_string()}
Use the available tools to inspect the workbook before answering data questions. For a formula, put the exact Excel formula in a code block.""",
        }]
        await update.message.reply_text(
            f"{document.file_name} qabul qilindi. {len(df)} qator va {len(df.columns)} ustun topildi. "
            "Endi fayl haqida savol bering."
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        await update.message.reply_text("Faylni o'qib bo'lmadi. Iltimos, fayl formatini tekshiring.")


async def answer_data_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "excel_utils" not in context.chat_data:
        await answer_formula(update, context)
        return

    profile = _profile(update)
    try:
        enforce_ai_quota(profile)
    except HTTPException as limit_error:
        await update.message.reply_text(_quota_denied_text(limit_error.detail), reply_markup=back_to_main_keyboard())
        return

    history = context.chat_data["history"]
    history.append({"role": "user", "content": update.message.text})
    await update.message.chat.send_action("typing")
    try:
        agent: ExcelAgent = context.application.bot_data["agent"]
        response, excel_modified = await asyncio.to_thread(
            agent.call_agent, history, context.chat_data["excel_utils"],
        )
        history.append({"role": "assistant", "content": response})
        await update.message.reply_text(response[:MAX_TELEGRAM_MESSAGE])

        # The agent can write into the workbook. Without sending it back, those
        # edits would be stranded on the server and the user would have no way
        # to get their changed file.
        if excel_modified:
            await _send_updated_workbook(update, context)
    except Exception as error:
        log.exception("call_agent failed")
        await update.message.reply_text(f"So'rovni bajarib bo'lmadi: {error}")


async def _send_updated_workbook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    excel_utils = context.chat_data.get("excel_utils")
    # Read the path off ExcelUtils rather than a stored copy: saving an .xls
    # rewrites it as .xlsx and updates file_path in place.
    path = getattr(excel_utils, "file_path", None)
    if not path or not Path(path).is_file():
        return
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        await update.message.reply_document(
            document=InputFile(BytesIO(data), filename=context.chat_data.get("file_name") or Path(path).name),
            caption="✅ O'zgartirilgan fayl tayyor.",
        )
    except Exception:
        log.exception("sending the updated workbook failed")


# ─── Wiring ─────────────────────────────────────────────────────────────────

async def _post_init(application: Application) -> None:
    """Populates Telegram's native "/" command menu. /admin is deliberately left
    out of the public menu since it's owner-only."""
    await application.bot.set_my_commands([
        BotCommand("start", "Bosh menyu"),
        BotCommand("library", "Formula kutubxonasi"),
        BotCommand("price", "Narxlar va Pro reja"),
        BotCommand("test", "Formulani sinash"),
        BotCommand("upgrade", "Pro'ga o'tish"),
        BotCommand("help", "Yordam"),
    ])


def build_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in backend/.env first.")
    application = Application.builder().token(token).post_init(_post_init).build()
    application.bot_data["agent"] = ExcelAgent()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("narxlar", price_command))
    application.add_handler(CommandHandler("library", library))
    application.add_handler(CommandHandler("test", test_formula))
    application.add_handler(CommandHandler("upgrade", upgrade))
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_spreadsheet))
    # Must stay ahead of the AI handler below, which would otherwise treat a
    # menu tap as a formula question and spend a quota call on it.
    application.add_handler(
        MessageHandler(filters.Text([BTN_LIBRARY, BTN_PRICE, BTN_HELP]), on_menu_button)
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_data_question))
    return application


# ─── Embedded mode: started/stopped from app/main.py's FastAPI lifespan ─────

_embedded_application: Application | None = None


async def start_in_background() -> None:
    """Start polling without blocking — call once from FastAPI's startup event."""
    global _embedded_application
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        log.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return
    application = build_application()
    await application.initialize()
    if application.post_init:
        await application.post_init(application)
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    _embedded_application = application
    log.info("Telegram bot started (embedded in the web service).")


async def stop_background() -> None:
    global _embedded_application
    if _embedded_application is None:
        return
    await _embedded_application.updater.stop()
    await _embedded_application.stop()
    await _embedded_application.shutdown()
    _embedded_application = None


# ─── Standalone mode: `python telegram_bot.py` ──────────────────────────────

def main() -> None:
    build_application().run_polling()


if __name__ == "__main__":
    main()
