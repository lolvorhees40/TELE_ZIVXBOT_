#!/usr/bin/env python3
"""
Random Picker & Timetable Telegram Bot
- Stores categories of items (restaurants, movies, ideas, plans, etc.)
- Returns a random item from a chosen category
- Creates Google Calendar links with day-of-week scheduling
- NEW: Extracts courses from an uploaded timetable image via OCR
- NEW: Generates Google Calendar exam links based on Spring 2026 Schedule
"""
import sys
import os
import random
import logging
import re
import io
from datetime import datetime, timedelta
from urllib.parse import quote

# ── NEW IMPORTS FOR OCR AND IMAGE PROCESSING ─────────────────────────────────
from PIL import Image
import pytesseract

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

# IMPORTANT FOR WINDOWS USERS: Point this to your Tesseract installation!
if sys.platform == 'win32':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# ── Bot Token ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# ── Default categories ───────────────────────────────────────────────────────
DEFAULT_CATEGORIES = {
    "restaurants": [
        "Sushi Palace", "The Burger Joint", "Pizza Paradiso",
        "Golden Dragon (Chinese)", "Taco Fiesta", "The Italian Corner",
        "Spice Garden (Indian)",
    ],
    "movies": [
        "Inception", "The Grand Budapest Hotel", "Interstellar",
        "Parasite", "Everything Everywhere All at Once", "Spirited Away",
        "The Dark Knight",
    ],
    "ideas": [
        "Start a new hobby", "Read a book you've been putting off",
        "Cook a recipe from a new cuisine", "Go for a long walk somewhere new",
        "Call an old friend", "Visit a local museum", "Try a DIY project",
    ],
    "plans": [
        "Weekend road trip", "Host a game night", "Picnic in the park",
        "Take a day trip to a nearby city", "Explore a new neighborhood",
        "Attend a local event or market", "Spa / relaxation day at home",
    ],
}

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ── SPRING 2026 EXAMINATION SCHEDULE DATA ────────────────────────────────────
# Priority 1: Common Exams. Format: "COURSE_CODE": ("YYYYMMDDTHHMMSS", "YYYYMMDDTHHMMSS") [cite: 4]
COMMON_EXAMS = {
    "ARA 101": ("20260509T170000", "20260509T190000"),
    "CMP 257": ("20260509T170000", "20260509T190000"),
    "BUS 100": ("20260511T080000", "20260511T100000"),
    "PSY 101": ("20260511T080000", "20260511T100000"),
    "COE 221": ("20260511T170000", "20260511T190000"),
    "COE 251": ("20260511T170000", "20260511T190000"),
    "PHY 001": ("20260511T170000", "20260511T190000"),
    "NGN 211": ("20260512T170000", "20260512T190000"),
    "SCM 202": ("20260512T170000", "20260512T190000"),
    "ARA 102E":("20260514T170000", "20260514T190000"),
    "COE 420": ("20260514T170000", "20260514T190000"),
    "ACC 201": ("20260516T110000", "20260516T130000"),
    "FIN 201": ("20260516T110000", "20260516T130000"),
    "MTH 203": ("20260516T110000", "20260516T130000"),
    "STA 202": ("20260516T110000", "20260516T130000"),
    "CMP 305": ("20260516T140000", "20260516T160000"),
    "CMP 310": ("20260516T140000", "20260516T160000"),
    "MTH 002": ("20260516T140000", "20260516T160000"),
    "MTH 103": ("20260516T140000", "20260516T160000"),
    "ACC 202": ("20260517T080000", "20260517T100000"),
    "MTH 221": ("20260517T080000", "20260517T100000"),
    "MTH 225": ("20260517T080000", "20260517T100000"),
    "ISA 201": ("20260517T140000", "20260517T160000"),
    "MTH 001": ("20260517T140000", "20260517T160000"),
    "MTH 104": ("20260517T140000", "20260517T160000"),
    "CMP 120": ("20260519T080000", "20260519T100000"),
    "MUS 100": ("20260519T080000", "20260519T100000"),
    "MTH 102": ("20260519T080000", "20260519T100000"),
    "NGN 112A":("20260519T080000", "20260519T100000"),
    "MTH 205": ("20260519T140000", "20260519T160000"),
    "MKT 201": ("20260519T140000", "20260519T160000"),
    "NGN 112B":("20260519T140000", "20260519T160000")
}

# Priority 2: Regular Exams mapping based on class timing. [cite: 22]
# Format: ("DAYS", "START_TIME") -> ("YYYYMMDDTHHMMSS", "YYYYMMDDTHHMMSS")
REGULAR_EXAMS = {
    ("MW", "08:00"): ("20260516T170000", "20260516T190000"),
    ("MW", "09:30"): ("20260511T110000", "20260511T130000"),
    ("MW", "11:00"): ("20260517T110000", "20260517T130000"),
    ("MW", "12:30"): ("20260509T110000", "20260509T130000"),
    ("MW", "14:00"): ("20260511T140000", "20260511T160000"),
    ("MW", "15:30"): ("20260516T080000", "20260516T100000"),
    ("MW", "17:00"): ("20260517T170000", "20260517T190000"),
    ("TR", "08:00"): ("20260512T140000", "20260512T160000"),
    ("TR", "09:30"): ("20260514T140000", "20260514T160000"),
    ("TR", "11:00"): ("20260514T110000", "20260514T130000"),
    ("TR", "12:30"): ("20260519T110000", "20260519T130000"),
    ("TR", "14:00"): ("20260509T140000", "20260509T160000"),
    ("TR", "15:30"): ("20260512T110000", "20260512T130000"),
    ("TR", "17:00"): ("20260509T080000", "20260509T100000")
}


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
    """Build a Google Calendar 'add event' URL for an ALL-DAY event."""
    date_str  = dt.strftime("%Y%m%d")
    next_day  = (dt + timedelta(days=1)).strftime("%Y%m%d")
    params = (
        f"action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={date_str}/{next_day}"
    )
    return f"https://calendar.google.com/calendar/render?{params}"

def make_google_calendar_link_exam(title: str, dt_start: str, dt_end: str) -> str:
    """Build a precise Google Calendar 'add event' URL using EXACT datetimes for exams."""
    params = (
        f"action=TEMPLATE"
        f"&text={quote(title + ' Final Exam')}"
        f"&dates={dt_start}/{dt_end}"
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
    try:
        idx = int(q) - 1
        if 0 <= idx < len(cats):
            return list(cats.keys())[idx]
    except ValueError:
        pass
    matches = [k for k in cats if q in k]
    return matches[0] if len(matches) == 1 else None


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Image Upload Handler for Timetable OCR
# ─────────────────────────────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Downloads an uploaded image, runs OCR, and attempts to find exam links."""
    await update.message.reply_text("📸 Analyzing your timetable... Give me a moment.")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        img = Image.open(io.BytesIO(image_bytes))
        extracted_text = pytesseract.image_to_string(img)
        
        if not extracted_text.strip():
            await update.message.reply_text("I couldn't read any text from that image. Try a clearer picture!")
            return

        # Match course codes like INE 331, MTH 203, MCE 216 — but NOT room codes
        # Room codes have 3-4 chars but are followed by 3-4 digit numbers (e.g. ESB 1014, NAB1 006)
        # Valid course codes: 3-4 letters, space, exactly 3 digits optionally followed by one letter
        course_pattern = re.compile(r'\b([A-Z]{2,4})\s+(\d{3}[A-Z]?)\b')
        
        # Match times like "9:30 am", "12:30 pm", "11:00 am"
        time_pattern = re.compile(r'(\d{1,2}:\d{2})\s*(am|pm)', re.IGNORECASE)
        
        # Match day columns from OCR — look for Monday/Tuesday etc. OR MW/TR patterns
        day_pattern = re.compile(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Mon|Tue|Wed|Thu|Fri|MW|TR|MWF)\b', re.IGNORECASE)

        # Room number pattern to exclude — 3-4 letters followed by 4-digit number
        room_pattern = re.compile(r'\b([A-Z]{2,4})\s*(\d{4})\b')
        room_codes = {f"{m[0]} {m[1]}" for m in room_pattern.findall(extracted_text)}
        # Also catch rooms like "NAB1 006", "SBA 1107" — 4+ digit rooms
        room_codes2 = set(re.findall(r'\b(?:ESB|NAB|ERB|SBA|NAB1)[^\n]*', extracted_text))

        all_course_matches = course_pattern.findall(extracted_text)
        
        # Filter out room codes — rooms tend to have 4-digit numbers, courses have 3-digit
        KNOWN_ROOM_PREFIXES = {'ESB', 'NAB', 'ERB', 'SBA', 'LIB', 'AUD', 'LAB', 'GYM', 'CLS'}
        detected_courses = []
        for prefix, num in all_course_matches:
            if prefix in KNOWN_ROOM_PREFIXES:
                continue  # skip room codes
            if len(num) == 4:
                continue  # 4-digit = room number, not course
            course_code = f"{prefix} {num}"
            # Strip section numbers like -01, -17 that OCR might merge
            detected_courses.append(course_code)

        detected_courses = list(dict.fromkeys(detected_courses))  # deduplicate, preserve order

        if not detected_courses:
            await update.message.reply_text(
                "I read the image but couldn't detect any course codes.\n\n"
                f"Debug - Raw OCR snippet:\n`{extracted_text[:300]}`",
                parse_mode="Markdown"
            )
            return

        # Extract all times found
        times_found = time_pattern.findall(extracted_text)
        
        # Convert "9:30 am" -> "09:30", "12:30 pm" -> "12:30", "3:30 pm" -> "15:30"
        def to_24h(t, meridiem):
            h, m = map(int, t.split(':'))
            if meridiem.lower() == 'pm' and h != 12:
                h += 12
            if meridiem.lower() == 'am' and h == 12:
                h = 0
            return f"{h:02d}:{m:02d}"

        times_24h = [to_24h(t, mer) for t, mer in times_found]

        # Detect if timetable is MW or TR based on day names present in OCR
        has_monday = bool(re.search(r'\b(Monday|Mon)\b', extracted_text, re.IGNORECASE))
        has_tuesday = bool(re.search(r'\b(Tuesday|Tue)\b', extracted_text, re.IGNORECASE))

        results_message = "🎓 *Your Spring 2026 Final Exams:*\n\n"
        found_any = False

        for course in detected_courses:
            # Priority 1: Common exam
            if course in COMMON_EXAMS:
                start_dt, end_dt = COMMON_EXAMS[course]
                link = make_google_calendar_link_exam(course, start_dt, end_dt)
                results_message += f"🏆 *{course}* (Common Exam)\n[📅 Add to Google Calendar]({link})\n\n"
                found_any = True
                continue

            # Priority 2: Match by timing
            matched = False
            for time_24h in times_24h:
                # Format to HH:MM
                time_str = time_24h  # already "09:30" etc.
                
                # Try both MW and TR
                for day_key in [("MW", time_str), ("TR", time_str)]:
                    if day_key in REGULAR_EXAMS:
                        start_dt, end_dt = REGULAR_EXAMS[day_key]
                        link = make_google_calendar_link_exam(course, start_dt, end_dt)
                        day_label = "Mon/Wed" if day_key[0] == "MW" else "Tue/Thu"
                        results_message += (
                            f"📘 *{course}* ({day_label} {time_str})\n"
                            f"[📅 Add to Google Calendar]({link})\n\n"
                        )
                        matched = True
                        found_any = True
                        break
                if matched:
                    break

            if not matched:
                results_message += f"❓ *{course}* — couldn't match to exam schedule.\n\n"

        if not found_any:
            results_message += "No courses could be matched to the Spring 2026 exam schedule."

        await update.message.reply_text(
            results_message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await update.message.reply_text(f"❌ Error: {type(e).__name__}: {e}")


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
    get_categories(context)
    await update.message.reply_text(
        "👋 *Random Picker & Timetable Bot*\n\n"
        "*Commands:*\n"
        "• /pick — pick from a category (interactive)\n"
        "• /list — show all categories & items\n"
        "• /additem `<category> | <item>` — add an item\n"
        "• /removeitem `<category> | <item>` — remove an item\n"
        "• /addcategory `<name>` — create a new category\n"
        "• /removecategory `<name>` — delete a category\n"
        "• /calendar `<event name>` — get a Google Calendar link\n\n"
        "📸 *NEW: Send a Photo of your timetable to generate Spring 2026 Final Exam dates!*\n\n"
        "*Quick pick:* just type a category name or number anytime! 🎲",
        parse_mode="Markdown"
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
# Plain-text handler
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

    # Register the photo handler for the OCR feature
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    logger.info("Bot running — press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
