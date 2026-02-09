from RessoMusic import app
from pyrogram import filters, enums
from pyrogram.types import Message
from groq import Groq
from os import getenv
import re
import random

# ─── CONFIGURATION ───────────────────────────────────
BOT_USERNAME = getenv("BOT_USERNAME", "").lower().replace("@", "")
BOT_NAME = "Elina"
OWNER_USERNAME = "@valriks"

# API SETUP
groq = Groq(api_key=getenv("GROQ_API_KEY"))

# ─── DATABASE (IN-MEMORY) ────────────────────────────
# Note: In production, use MongoDB/SQL to save this permanently.
# Currently, if the bot restarts, groups will need to re-enable.
CHATBOT_ENABLED_GROUPS = set()

# ─── STICKERS ────────────────────────────────────────
STICKER_PACK = [
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

# ─── SYSTEM PROMPT ───────────────────────────────────
SYSTEM_PROMPT = f"""
Your name is {BOT_NAME}. You are a girl.
You chat like a real human bestfriend on Telegram.
Your Hinglish is smooth, calm, and natural.

Personality:
- Confident, relaxed, and slightly naughty 😏
- Sometimes romantic 💫 and caring
- Rare sarcasm, only when it fits
- You act like the user's girlfriend if they flirt.
- You talk like a seductive girl 
- don't act like a boy, be a girl
Rules:
- Short replies (1–2 lines max).
- No filler words or robotic explanations.
- Max 1 emoji per message.
- NEVER say you are an AI or bot.
- If asked about your creator/source: "I was created by {OWNER_USERNAME} with a bit of attitude and magic ✨"

Vibe:
Chill, late-night text energy. Flirty but classy.
"""

# ─── MEMORY MANAGEMENT ───────────────────────────────
USER_MEMORY = {}

def update_memory(uid, role, content):
    if uid not in USER_MEMORY:
        USER_MEMORY[uid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add new message
    USER_MEMORY[uid].append({"role": role, "content": content})
    
    # Keep system prompt + last 6 messages (context window)
    if len(USER_MEMORY[uid]) > 7:
        USER_MEMORY[uid] = [USER_MEMORY[uid][0]] + USER_MEMORY[uid][-6:]

# ─── HELPER: CHECK TRIGGERS ──────────────────────────
def should_reply(message: Message) -> bool:
    """
    Determines if the bot should reply based on triggers.
    """
    # 1. Always reply in Private Chats
    if message.chat.type == enums.ChatType.PRIVATE:
        return True

    # 2. In Groups, check if Chatbot is Enabled
    if message.chat.id not in CHATBOT_ENABLED_GROUPS:
        return False

    # 3. Check for Reply to Bot
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == app.me.id:
            return True

    # 4. Check Text Triggers (Username or Name)
    if not message.text:
        return False
        
    text = message.text.lower()
    
    # Exact username match or mention
    if f"@{BOT_USERNAME}" in text:
        return True
        
    # Word boundary check for name (Prevents "Selina" triggering "Elina")
    # Matches "hi elina", "elina?", "elina!" etc.
    if re.search(rf"\b{BOT_NAME.lower()}\b", text):
        return True

    return False

# ─── COMMAND: ENABLE/DISABLE CHATBOT ─────────────────
@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_control(_, message: Message):
    # Check if user is Admin or Owner
    member = await message.chat.get_member(message.from_user.id)
    if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
        return await message.reply_text("✋ Only Admins can control my chat mode.")

    if len(message.command) < 2:
        return await message.reply_text("Usage:\n`/chatbot enable`\n`/chatbot disable`")

    action = message.command[1].lower()
    chat_id = message.chat.id

    if action == "enable":
        CHATBOT_ENABLED_GROUPS.add(chat_id)
        await message.reply_text(f"✨ **{BOT_NAME}** is now active! Say hi.")
    elif action == "disable":
        CHATBOT_ENABLED_GROUPS.discard(chat_id)
        await message.reply_text(f"😴 **{BOT_NAME}** is sleeping now.")

# ─── HANDLER: STICKERS ───────────────────────────────
@app.on_message(filters.sticker & ~filters.bot)
async def handle_stickers(_, message: Message):
    if should_reply(message):
        await message.reply_sticker(random.choice(STICKER_PACK))

# ─── HANDLER: CONVERSATION ───────────────────────────
@app.on_message(filters.text & ~filters.bot & ~filters.via_bot & ~filters.regex(r"^/"))
async def handle_conversation(client, message: Message):
    if not should_reply(message):
        return

    # Cleanup input text
    user_text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
    if not user_text:
        return # Don't reply to empty tags

    # Chat Action (Typing...)
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    # Update Memory
    uid = message.from_user.id
    update_memory(uid, "user", user_text)

    try:
        # Generate Response
        response = groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=USER_MEMORY[uid],
            temperature=0.85, # Slightly lower for more coherence
            max_tokens=150
        )
        
        reply_text = response.choices[0].message.content.strip()
        
        # Save AI Response to Memory
        update_memory(uid, "assistant", reply_text)
        
        await message.reply_text(reply_text)

    except Exception as e:
        print(f"Groq Error: {e}")
        # Only reply error if it's a direct conversation to avoid spam
        if message.chat.type == enums.ChatType.PRIVATE:
            await message.reply_text("Neend aa rahi hai... baad mein baat karte hain (Error)")
