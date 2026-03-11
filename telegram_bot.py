#!/usr/bin/env python3
"""
Random Picker Telegram Bot
- Stores categories of items (restaurants, movies, ideas, plans, etc.)
- Returns a random item from a chosen category
- Creates Google Calendar links with day-of-week scheduling

SETUP:
  pip install python-telegram-bot
  Set BOT_TOKEN below (get one from @BotFather on Telegram)
  python telegram_bot.py
"""
import os
import random
import logging
from datetime import datetime, timedelta
from urllib.parse import quote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Bot Token — replace with your token from @BotFather ──────────────────────
# ── Bot Token — replace with your token from @BotFather ──────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ── Default categories (freely edit these, or manage via commands at runtime) ─
DEFAULT_CATEGORIES = {
    "restaurants": [
        "Sushi Palace",
        "The Burger Joint",
        "Pizza Paradiso",
        "Golden Dragon (Chinese)",
        "Taco Fiesta",
        "The Italian Corner",
        "Spice Garden (Indian)",
    ],
    "movies": [
        "Inception",
        "The Grand Budapest Hotel",
        "Interstellar",
        "Parasite",
        "Everything Everywhere All at Once",
        "Spirited Away",
        "The Dark Knight",
    ],
    "ideas": [
        "Start a new hobby",
        "Read a book you've been putting off",
        "Cook a recipe from a new cuisine",
        "Go for a long walk somewhere new",
        "Call an old friend",
        "Visit a local museum",
        "Try a DIY project",
    ],
    "plans": [
        "Weekend road trip",
        "Host a game night",
        "Picnic in the park",
        "Take a day trip to a nearby city",
        "Explore a new neighborhood",
        "Attend a local event or market",
        "Spa / relaxation day at home",
    ],
}

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_categories(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Return this user's category dict, seeded from defaults on first use."""
    if "categories" not in context.user_data:
        import copy
        context.user_data["categories"] = copy.deepcopy(DEFAULT_CATEGORIES)
    return context.user_data["categories"]


def next_weekday(weekday_index: int) -> datetime:
    """Next occurrence of weekday_index (0=Mon … 6=Sun), never today."""
    today = datetime.now()
    days_ahead = weekday_index - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def make_google_calendar_link(title: str, dt: datetime) -> str:
    """Build a Google Calendar 'add event' URL for an all-day event."""
    date_str  = dt.strftime("%Y%m%d")
    next_day  = (dt + timedelta(days=1)).strftime("%Y%m%d")
    params = (
        f"action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={date_str}/{next_day}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def categories_keyboard(cats: dict) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f"{i}. {name.capitalize()}", callback_data=f"cat:{name}")]
        for i, name in enumerate(cats, 1)
    ]
    return InlineKeyboardMarkup(buttons)


def days_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(day, callback_data=f"day:{i}")]
        for i, day in enumerate(DAYS_OF_WEEK)
    ]
    return InlineKeyboardMarkup(buttons)


def resolve_category(query: str, cats: dict):
    """Match by exact name, partial name, or 1-based index. Returns key or None."""
    q = query.strip().lower()
    if q in cats:
        return q
    try:                              # numeric index
        idx = int(q) - 1
        if 0 <= idx < len(cats):
            return list(cats.keys())[idx]
    except ValueError:
        pass
    matches = [k for k in cats if q in k]  # partial match
    return matches[0] if len(matches) == 1 else None


# ─────────────────────────────────────────────────────────────────────────────
# Shared pick sender (works for both Message and CallbackQuery)
# ─────────────────────────────────────────────────────────────────────────────

async def send_pick(target, cat_name: str, items: list):
    """Send a random pick. target = Update or CallbackQuery."""
    if not items:
        text = f"The *{cat_name}* category is empty. Add items with /additem."
        chosen = ""
    else:
        chosen = random.choice(items)
        text   = f"🎯 *{cat_name.capitalize()}* pick:\n\n✨ *{chosen}*"

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Pick again",       callback_data=f"cat:{cat_name}"),
        InlineKeyboardButton("📅 Add to calendar",  callback_data=f"cal:{cat_name}:{chosen}"),
    ]])

    if isinstance(target, Update):
        await target.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await target.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


# ─────────────────────────────────────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "👋 *Welcome to the Random Picker Bot!*\n\n"
        "I can help you randomly decide where to eat, what to watch, or what to do.\n\n"
        "Here are some commands to get you started:\n"
        "📌 /list - See all your categories\n"
        "🎲 /pick - Pick a random item from a category\n"
        "➕ /additem - Add a new item to a category\n"
        "❓ /help - Show this message again"
    )
    
    # Send the message back to the user
    await update.message.reply_text(
        welcome_message, 
        parse_mode="Markdown" # This allows you to use bold (*) and italics (_)
    )

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories(context)
    if not cats:
        await update.message.reply_text("No categories yet. Use /addcategory to create one.")
        return

    lines = ["📋 *Your categories:*\n"]
    for idx, (name, items) in enumerate(cats.items(), 1):
        lines.append(f"*{idx}. {name.capitalize()}* ({len(items)} items)")
        for item in items:
            lines.append(f"   • {item}")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories(context)
    if not cats:
        await update.message.reply_text("No categories yet! Use /addcategory first.")
        return

    if context.args:
        cat = resolve_category(" ".join(context.args), cats)
        if cat:
            await send_pick(update, cat, cats[cat])
        else:
            await update.message.reply_text("Category not found. Use /list to see all categories.")
        return

    await update.message.reply_text(
        "🎲 *Pick a category:*",
        reply_markup=categories_keyboard(cats),
        parse_mode="Markdown"
    )


async def add_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories(context)
    raw = " ".join(context.args) if context.args else ""

    if "|" not in raw:
        await update.message.reply_text(
            "Usage: `/additem <category> | <item>`\n"
            "Example: `/additem restaurants | Noodle House`",
            parse_mode="Markdown"
        )
        return

    cat_part, item_part = [x.strip() for x in raw.split("|", 1)]
    cat_name = resolve_category(cat_part, cats)

    if cat_name is None:
        cat_name = cat_part.lower()
        cats[cat_name] = []
        note = f" (new category *{cat_name}* created)"
    else:
        note = ""

    if item_part in cats[cat_name]:
        await update.message.reply_text(f"'{item_part}' is already in *{cat_name}*.", parse_mode="Markdown")
        return

    cats[cat_name].append(item_part)
    await update.message.reply_text(
        f"✅ Added *{item_part}* to *{cat_name}*{note} ({len(cats[cat_name])} items total).",
        parse_mode="Markdown"
    )


async def remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories(context)
    raw = " ".join(context.args) if context.args else ""

    if "|" not in raw:
        await update.message.reply_text(
            "Usage: `/removeitem <category> | <item>`\n"
            "Example: `/removeitem restaurants | Noodle House`",
            parse_mode="Markdown"
        )
        return

    cat_part, item_part = [x.strip() for x in raw.split("|", 1)]
    cat_name = resolve_category(cat_part, cats)

    if cat_name is None:
        await update.message.reply_text(f"Category '{cat_part}' not found.")
        return
    if item_part not in cats[cat_name]:
        await update.message.reply_text(f"'{item_part}' not found in *{cat_name}*.", parse_mode="Markdown")
        return

    cats[cat_name].remove(item_part)
    await update.message.reply_text(f"🗑️ Removed *{item_part}* from *{cat_name}*.", parse_mode="Markdown")


async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories(context)
    if not context.args:
        await update.message.reply_text("Usage: `/addcategory <name>`", parse_mode="Markdown")
        return

    name = " ".join(context.args).lower().strip()
    if name in cats:
        await update.message.reply_text(f"Category *{name}* already exists.", parse_mode="Markdown")
        return

    cats[name] = []
    await update.message.reply_text(
        f"✅ Category *{name}* created!\nAdd items with: `/additem {name} | Your Item`",
        parse_mode="Markdown"
    )


async def remove_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cats = get_categories(context)
    if not context.args:
        await update.message.reply_text("Usage: `/removecategory <name or number>`", parse_mode="Markdown")
        return

    name = resolve_category(" ".join(context.args), cats)
    if name is None:
        await update.message.reply_text("Category not found. Use /list to see all categories.")
        return

    del cats[name]
    await update.message.reply_text(f"🗑️ Category *{name}* deleted.", parse_mode="Markdown")


async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = " ".join(context.args) if context.args else "My Event"
    context.user_data["pending_calendar_item"] = item
    await update.message.reply_text(
        f"📅 *{item}*\nWhich day of the week should I schedule this?",
        parse_mode="Markdown",
        reply_markup=days_keyboard()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Inline keyboard callback
# ─────────────────────────────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    cats = get_categories(context)

    # Category selected → pick random item
    if data.startswith("cat:"):
        cat_name = data[4:]
        if cat_name not in cats:
            await query.edit_message_text("Category no longer exists.")
            return
        await send_pick(query, cat_name, cats[cat_name])

    # Calendar button pressed after a pick
    elif data.startswith("cal:"):
        parts = data.split(":", 2)
        item = parts[2] if len(parts) > 2 else "Event"
        context.user_data["pending_calendar_item"] = item
        await query.edit_message_text(
            f"📅 Adding *{item}* to Google Calendar\nWhich day of the week?",
            parse_mode="Markdown",
            reply_markup=days_keyboard()
        )

    # Day selected → build calendar link
    elif data.startswith("day:"):
        day_idx  = int(data[4:])
        day_name = DAYS_OF_WEEK[day_idx]
        item     = context.user_data.get("pending_calendar_item", "Event")
        dt       = next_weekday(day_idx)
        link     = make_google_calendar_link(item, dt)
        await query.edit_message_text(
            f"✅ *{item}*\n📅 {day_name}, {dt.strftime('%b %d %Y')}\n\n"
            f"[➕ Open in Google Calendar]({link})",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )


# ─────────────────────────────────────────────────────────────────────────────
# Plain-text handler — treat messages as category name / number lookups
# ─────────────────────────────────────────────────────────────────────────────

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    cats = get_categories(context)
    cat  = resolve_category(text, cats)

    if cat:
        await send_pick(update, cat, cats[cat])
    else:
        await update.message.reply_text(
            f"🤔 I don't recognise *{text}* as a category.\n"
            "Type /list to see all categories, or /pick for an interactive menu.",
            parse_mode="Markdown"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",           start))
    app.add_handler(CommandHandler("help",            start))
    app.add_handler(CommandHandler("list",            list_categories))
    app.add_handler(CommandHandler("pick",            pick))
    app.add_handler(CommandHandler("additem",         add_item))
    app.add_handler(CommandHandler("removeitem",      remove_item))
    app.add_handler(CommandHandler("addcategory",     add_category))
    app.add_handler(CommandHandler("removecategory",  remove_category))
    app.add_handler(CommandHandler("calendar",        calendar_command))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Bot running — press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
