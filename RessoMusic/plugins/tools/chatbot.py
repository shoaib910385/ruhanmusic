from RessoMusic import app
from pyrogram import filters
from pyrogram.enums import ChatAction, ChatType
from pyrogram.types import Message
from groq import Groq
from os import getenv
import re
from datetime import datetime
import random

# ─── CONFIG ──────────────────────────────────────────
BOT_USERNAME = getenv("BOT_USERNAME", "").lower()
BOT_NAME = "Elina"
BOT_NAME_LOWER = BOT_NAME.lower()
OWNER_USERNAME = "@valriks"

# ONLY THIS ADMIN CAN CONTROL CHATBOT IN GROUPS
CHATBOT_ADMIN_ID = 8021449673

groq = Groq(api_key=getenv("GROQ_API_KEY"))

# ─── STICKERS ────────────────────────────────────────
TIDAL_STICKERS = [
    "CAACAgUAAyEGAASYbwWmAAEDFr9pPrdIW6DnvGYBa-1qUgABOmHx0nEAAoUYAALBwHlU4LkheFnOVNceBA",
    "CAACAgUAAyEFAASK0-LFAAEBK4tpPrciRqLr741rfpCyadEUguuirQACFhwAAq4_CFf6uHKs2vmqMR4E",
    "CAACAgUAAyEFAATMbo3sAAIBsGk-tCvX9sSoUy6Qhfjt2XjdcPl1AALXBQACqfBIV7itGNxzQYFfHgQ",
    "CAACAgUAAyEFAATMbo3sAAIBr2k-tDRFK1B7YolnG0_evEIuXapjAALdBAACRscpVd-2ZY4nX5iaHgQ",
    "CAACAgUAAyEFAASK0-LFAAEBK4xpPrcmYuGS2PO7xAw__hsfF7A8pAACQxgAAq_T4FVmdyWrJlg6mh4E",
    "CAACAgUAAyEFAASK0-LFAAEBK41pPrcsLmPnDY5D9vej35yjoGt2FAACUxwAAoqW2VV-RY3-MECCJx4E",
    "CAACAgUAAyEFAASK0-LFAAEBK5ZpPreQi_v-G8QtCAeyda2Q0sRCOwAC5A4AAnloEFRAJk3asy9_Vx4E",
    "CAACAgUAAyEFAASK0-LFAAEBK5VpPreM88yx1ByFpEmTUZayuMR73gACVhAAAjKw4VTEekhz3MldkR4E",
    "CAACAgIAAyEFAASK0-LFAAEBK5tpPre2cec7bV-FUWpPitw6V2J4dwACMIkAAo6A6UstbPnvHx9mLh4E",
    "CAACAgUAAyEFAASK0-LFAAEBK59pPrf-7b_nl7MNT9owF2OFBSufZQACGxkAArNAgVbtStsspX6Isx4E",
    "CAACAgUAAyEFAASK0-LFAAEBK6JpPrgg-cU6EEAUtQTjEicTkAHLRAAC_BoAAqImiFR8MwqHtGYuxh4E",
    "CAACAgUAAyEFAATMbo3sAAIBq2k-tDv3MLT3PWtqgMFLlysAAZAe2QACbhUAAhbteVTbn-jmI4mcSR4E",
]

# ─── GROUP ENABLE STATE ──────────────────────────────
CHATBOT_ENABLED_GROUPS = set()

# ─── SYSTEM PROMPT ───────────────────────────────────
SYSTEM_PROMPT = f"""
Your name is Elina. You are a girl.
You chat like a real human bestfriend on Telegram.
Your Hinglish is smooth, calm, and natural.
Personality:
Confident, relaxed
Sometimes naughty 😏
Sometimes romantic 💫
Sometimes caring
Rare sarcasm, only when it fits

also you wanna make everyone boyfriend, act like you're his girlfriend,
Rules:
Short replies (1–2 lines)
No filler spam
Emojis optional (max 1 sometimes)
Never explain
Never say you are AI or bot
Text only

Vibe:
Chill, late-night bestfriend energy
Flirty but classy
Owner:
Owner is {OWNER_USERNAME}
only when someone uses like who's your bot, your source code then reply like i was created by @hehe_stalker in some attitude tangy way
Be softer and respectful with owner

You are not performing.
You are just being yourself.
"""

# ─── MEMORY ──────────────────────────────────────────
USER_MEMORY = {}

def add_memory(uid, role, text):
    USER_MEMORY.setdefault(uid, []).append(
        {"role": role, "content": text}
    )
    USER_MEMORY[uid] = USER_MEMORY[uid][-6:]

# ─── TIME GREETING ───────────────────────────────────
def time_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning ☀️ chai pi?"
    elif 12 <= hour < 17:
        return "Lunch hua? thoda break le lo"
    elif 17 <= hour < 21:
        return "Shaam vibes ✨ kya chal raha"
    else:
        return "Dinner hua ya late-night mode on 🌙"

# ─── TRIGGER HELPERS ─────────────────────────────────
def name_trigger(text: str) -> bool:
    """
    Triggers on:
    tidal
    Tidal
    hi tidal
    tidal baby
    tidal❤️
    """
    text = text.lower()
    return BOT_NAME_LOWER in text

def group_trigger(message: Message) -> bool:
    text = (message.text or "").lower()
    return (
        f"@{BOT_USERNAME}" in text
        or name_trigger(text)
        or (
            message.reply_to_message
            and message.reply_to_message.from_user
            and message.reply_to_message.from_user.is_bot
        )
    )

# ─── CHATBOT TOGGLE ──────────────────────────────────
@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_toggle(_, message: Message):
    if not message.from_user or message.from_user.id != CHATBOT_ADMIN_ID:
        return await message.reply_text("🚫 Only bot owner can control chatbot.")

    if len(message.command) < 2:
        return await message.reply_text("Usage:\n/chatbot enable\n/chatbot disable")

    action = message.command[1].lower()
    chat_id = message.chat.id

    if action == "enable":
        CHATBOT_ENABLED_GROUPS.add(chat_id)
        await message.reply_text("✨ Chatbot enabled in this group.")

    elif action == "disable":
        CHATBOT_ENABLED_GROUPS.discard(chat_id)
        await message.reply_text("🔕 Chatbot disabled in this group.")

# ─── STICKER HANDLER ─────────────────────────────────
@app.on_message(filters.sticker & ~filters.bot & ~filters.via_bot)
async def tidal_sticker_reply(_, message: Message):
    if message.chat.type != ChatType.PRIVATE:
        if message.chat.id not in CHATBOT_ENABLED_GROUPS:
            return
        if not group_trigger(message):
            return

    await message.reply_sticker(random.choice(TIDAL_STICKERS))

# ─── TEXT CHAT HANDLER ───────────────────────────────
@app.on_message(
    filters.text
    & ~filters.regex(r"^/")
    & ~filters.bot
    & ~filters.via_bot
)
async def tidal_chat(bot, message: Message):
    if not message.from_user:
        return

    if message.chat.type != ChatType.PRIVATE:
        if message.chat.id not in CHATBOT_ENABLED_GROUPS:
            return
        if not group_trigger(message):
            return

    text = message.text.strip()

    clean_text = (
        text.replace(f"@{BOT_USERNAME}", "")
            .replace(BOT_NAME, "")
            .strip()
    )

    uid = message.from_user.id
    add_memory(uid, "user", clean_text or "hi")

    if len(USER_MEMORY[uid]) == 1:
        await message.reply_text(time_greeting())

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(USER_MEMORY[uid])

    try:
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        res = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.9,
            max_tokens=140
        )

        reply = res.choices[0].message.content.strip()
        add_memory(uid, "assistant", reply)

        await message.reply_text(reply)

    except Exception:
        await message.reply_text("thoda hang ho gaya… phir bolna")
