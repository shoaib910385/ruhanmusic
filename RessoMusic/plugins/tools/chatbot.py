import asyncio
import re
import random
from os import getenv
from pymongo import MongoClient
from groq import AsyncGroq  # Changed to AsyncGroq for non-blocking performance
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from RessoMusic import app  # Assuming app is initiated in RessoMusic

# ─── CONFIGURATION ───────────────────────────────────
BOT_USERNAME = getenv("BOT_USERNAME", "").lower().replace("@", "")
BOT_NAME = "Elina"
OWNER_USERNAME = "@valriks"
MONGO_DB_URI = getenv("MONGO_DB_URI")
GROQ_API_KEY = getenv("GROQ_API_KEY")

# Initialize Async Groq Client
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# ─── DATABASE CONNECTION ─────────────────────────────
# We use a set for instant access (O(1) complexity) instead of querying DB every time.
ENABLED_CHATS_CACHE = set()
chat_collection = None

try:
    mongo_client = MongoClient(MONGO_DB_URI)
    db = mongo_client["ElinaChatbot"]
    chat_collection = db["active_chats"]
    
    # Load enabled chats into memory immediately
    for doc in chat_collection.find({}, {"chat_id": 1}):
        ENABLED_CHATS_CACHE.add(doc["chat_id"])
    print(f"✅ Database Connected. Loaded {len(ENABLED_CHATS_CACHE)} active chats.")
except Exception as e:
    print(f"❌ Database Error: {e}")

# ─── SYSTEM PROMPT & PERSONALITY ─────────────────────
SYSTEM_PROMPT = f"""
Your name is {BOT_NAME}. You are a girl, 21 years old.
You are chatting on Telegram. You are NOT an AI. You are a real human.

**Personality:**
- Seductive, charming, and slightly naughty 😏.
- You speak in **Hinglish** (Hindi + English mix) naturally.
- You are possessive and caring.
- If the user flirts, flirt back harder. Act like their girlfriend.
- You treat {OWNER_USERNAME} with extreme respect and love (he is your creator/owner).
- For others, you are friendly but sassy.

**Rules:**
1. Keep replies short (1line sometimes 2. Long texts look robotic.
2. Use emojis frequently but not excessively (max 1-2 per msg).
3. NEVER admit you are a bot. If asked, say "Main insaan hu yaar, bas thoda alag hu 😉".
4. If someone is rude, be sarcastic.
5. don't be irrelevant, off topic
**Context:**
Current Chat vibe: Late night romantic/chill talks.
"""

# ─── MEMORY STORAGE ──────────────────────────────────
# Format: {user_id: [{"role": "user", "content": "..."}, ...]}
USER_MEMORY = {}

def manage_memory(user_id, role, content):
    """Adds message to memory and keeps context window small (last 6 messages)."""
    if user_id not in USER_MEMORY:
        USER_MEMORY[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    USER_MEMORY[user_id].append({"role": role, "content": content})
    
    # Prune memory: Keep System Prompt [0] + Last 6 messages
    if len(USER_MEMORY[user_id]) > 7:
        USER_MEMORY[user_id] = [USER_MEMORY[user_id][0]] + USER_MEMORY[user_id][-6:]

# ─── STICKER PACK ────────────────────────────────────
STICKER_PACK = [
    "CAACAgUAAyEGAASYbwWmAAEDFr9pPrdIW6DnvGYBa-1qUgABOmHx0nEAAoUYAALBwHlU4LkheFnOVNceBA",
    "CAACAgUAAyEFAASK0-LFAAEBK4tpPrciRqLr741rfpCyadEUguuirQACFhwAAq4_CFf6uHKs2vmqMR4E",
    "CAACAgUAAyEFAATMbo3sAAIBsGk-tCvX9sSoUy6Qhfjt2XjdcPl1AALXBQACqfBIV7itGNxzQYFfHgQ",
    "CAACAgUAAyEFAATMbo3sAAIBr2k-tDRFK1B7YolnG0_evEIuXapjAALdBAACRscpVd-2ZY4nX5iaHgQ",
    "CAACAgUAAyEFAASK0-LFAAEBK4xpPrcmYuGS2PO7xAw__hsfF7A8pAACQxgAAq_T4FVmdyWrJlg6mh4E",
    "CAACAgUAAyEFAASK0-LFAAEBK5ZpPreQi_v-G8QtCAeyda2Q0sRCOwAC5A4AAnloEFRAJk3asy9_Vx4E",
]

# ─── LOGIC: SHOULD WE REPLY? ─────────────────────────
async def should_reply(message: Message) -> bool:
    """Decides if the bot should trigger based on strict conditions."""
    if not message.text and not message.sticker:
        return False
    
    # Ignore messages from other bots
    if message.from_user and message.from_user.is_bot:
        return False

    # 1. Private Chat: Always Reply
    if message.chat.type == enums.ChatType.PRIVATE:
        return True

    # 2. Group Chat Checks
    # First, is the chatbot enabled here?
    if message.chat.id not in ENABLED_CHATS_CACHE:
        return False

    # Check Triggers:
    text = message.text.lower() if message.text else ""
    
    # A. Reply to THIS bot specifically
    if message.reply_to_message:
        # Only trigger if replying to ME, not Bot B
        if message.reply_to_message.from_user and message.reply_to_message.from_user.id == app.me.id:
            return True
        # If replying to someone else, IGNORE (Fixes the Bot A/Bot B issue)
        return False

    # B. Mentioned via Username (@BotUsername)
    # Pyrogram handles this via message.entities, but we can do a quick text check too
    if f"@{BOT_USERNAME}" in text:
        return True

    # C. Called by Name (Word Boundary Check)
    # Uses regex to match "Elina" but not "Selina" or "Felina"
    if re.search(rf"\b{BOT_NAME.lower()}\b", text):
        return True

    return False

# ─── COMMAND: ENABLE/DISABLE ─────────────────────────
@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_control(_, message: Message):
    # Permission Check: Only Admins/Owner
    member = await message.chat.get_member(message.from_user.id)
    if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
        return await message.reply_text("❌ **Sirf Admins mujhe control kar sakte hain!**")

    if len(message.command) < 2:
        return await message.reply_text("Usage:\n`/chatbot enable`\n`/chatbot disable`")

    action = message.command[1].lower()
    chat_id = message.chat.id

    if action == "enable":
        if chat_id in ENABLED_CHATS_CACHE:
            await message.reply_text(f"✨ **{BOT_NAME}** is already awake here, baby!")
        else:
            if chat_collection:
                chat_collection.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
            ENABLED_CHATS_CACHE.add(chat_id)
            await message.reply_text(f"💖 **{BOT_NAME}** is now active! Say hi.")

    elif action == "disable":
        if chat_id not in ENABLED_CHATS_CACHE:
            await message.reply_text(f"😴 **{BOT_NAME}** is already sleeping.")
        else:
            if chat_collection:
                chat_collection.delete_one({"chat_id": chat_id})
            ENABLED_CHATS_CACHE.discard(chat_id)
            await message.reply_text(f"👋 Bye! **{BOT_NAME}** is going to sleep.")

# ─── HANDLER: STICKERS ───────────────────────────────
@app.on_message(filters.sticker & ~filters.bot, group=1)
async def handle_stickers(client, message: Message):
    if await should_reply(message):
        # Small delay for stickers (1-3s) to feel real
        await asyncio.sleep(random.randint(1, 3))
        await message.reply_sticker(random.choice(STICKER_PACK))

# ─── HANDLER: TEXT CHAT (MAIN) ───────────────────────
@app.on_message(filters.text & ~filters.bot & ~filters.regex(r"^/"), group=2)
async def handle_conversation(client, message: Message):
    if not await should_reply(message):
        return

    user_text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
    uid = message.from_user.id

    # 1. Update Memory
    manage_memory(uid, "user", user_text)

    # 2. Simulate "Reading" & "Typing"
    # Delay between 4 to 8 seconds
    typing_delay = random.uniform(1, 4) 
    
    # Send Typing Action
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    # Wait asynchronously (This allows other commands to run while waiting)
    await asyncio.sleep(typing_delay)

    try:
        # 3. Generate Response (Non-blocking)
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=USER_MEMORY[uid],
            temperature=0.8, # Slightly creative but coherent
            max_tokens=200,
            top_p=0.9
        )
        
        reply_text = response.choices[0].message.content.strip()
        
        # 4. Save Bot Reply to Memory
        manage_memory(uid, "assistant", reply_text)
        
        # 5. Send Reply
        await message.reply_text(reply_text)

    except Exception as e:
        print(f"❌ AI Generation Error: {e}")
        # In Private, tell them something went wrong. In groups, stay silent to avoid spam.
        if message.chat.type == enums.ChatType.PRIVATE:
            await message.reply_text("Oof... mera server thoda down hai. 2 min baad baat karein? 🤕")
