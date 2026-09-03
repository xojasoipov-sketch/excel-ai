"""Telegram entry point for ExcelYordamchi AI. Run: python telegram_bot.py"""
import asyncio
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.agent import ExcelAgent
from app.excel_utils import ExcelUtils

load_dotenv()

SYSTEM_PROMPT = """You are ExcelYordamchi AI. Generate safe, exact Microsoft Excel formulas.
Reply in the user's language (Uzbek, Russian, or English). Put the formula alone
in an Excel code block, then give a very short explanation. Ask one question if
cell references, ranges, or conditions are essential but missing."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salom! Excel formulani o‘zbekcha, ruscha yoki inglizcha yozing.\n\n"
        "Masalan: A ustundagi sonlar yig‘indisini hisobla."
    )


async def answer_formula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = context.application.bot_data["deepseek"]
    response = await client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": update.message.text},
        ],
    )
    await update.message.reply_text(response.choices[0].message.content)


async def handle_spreadsheet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv", ".tsv"}:
        await update.message.reply_text("Iltimos, XLSX, XLS, CSV yoki TSV fayl yuboring.")
        return
    if document.file_size and document.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("Fayl 10 MB dan kichik bo‘lishi kerak.")
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
        context.chat_data["history"] = [{
            "role": "system",
            "content": f"""You are ExcelYordamchi AI. Reply in the user's language: Uzbek, Russian, or English.
The user uploaded a spreadsheet with {len(df)} rows and {len(df.columns)} columns.
Headers: {', '.join(map(str, df.columns))}. Preview:\n{df.head().to_string()}
Use the available tools to inspect the workbook before answering data questions. For a formula, put the exact Excel formula in a code block.""",
        }]
        await update.message.reply_text(
            f"{document.file_name} qabul qilindi. {len(df)} qator va {len(df.columns)} ustun topildi. Endi fayl haqida savol bering."
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        await update.message.reply_text("Faylni o‘qib bo‘lmadi. Iltimos, fayl formatini tekshiring.")


async def answer_data_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "excel_utils" not in context.chat_data:
        await answer_formula(update, context)
        return
    history = context.chat_data["history"]
    history.append({"role": "user", "content": update.message.text})
    await update.message.chat.send_action("typing")
    try:
        response, _ = await asyncio.to_thread(
            context.application.bot_data["agent"].call_agent,
            history,
            context.chat_data["excel_utils"],
        )
        history.append({"role": "assistant", "content": response})
        await update.message.reply_text(response)
    except Exception as error:
        await update.message.reply_text(f"So‘rovni bajarib bo‘lmadi: {error}")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not token or not api_key:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and DEEPSEEK_API_KEY in backend/.env first.")
    app = Application.builder().token(token).build()
    app.bot_data["deepseek"] = AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    app.bot_data["agent"] = ExcelAgent()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_spreadsheet))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer_data_question))
    app.run_polling()


if __name__ == "__main__":
    main()
