import os
import asyncio
from random import randint
from typing import Union

from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from RessoMusic import Carbon, YouTube, app
from RessoMusic.core.call import AMBOTOP
from RessoMusic.misc import db
from RessoMusic.utils.database import add_active_video_chat, is_active_chat
from RessoMusic.utils.exceptions import AssistantErr
from RessoMusic.utils.inline import aq_markup, close_markup, stream_markup
from RessoMusic.utils.pastebin import AMBOTOPBin
from RessoMusic.utils.stream.queue import put_queue, put_queue_index
from RessoMusic.utils.thumbnails import gen_thumb

# --- CONFIGURATION & DATABASE FOR CAPTIONS ---
ADMIN_ID = 7659846392  # Your Admin ID

# Create/Connect to a collection in MongoDB
captiondb = db.stream_captions

async def get_stored_caption():
    """Fetches the custom caption from MongoDB."""
    data = await captiondb.find_one({"chat_id": "GLOBAL_CAPTION"})
    if data and "text" in data:
        return data["text"]
    return None

async def save_stored_caption(html_text):
    """Upserts the custom caption into MongoDB."""
    await captiondb.update_one(
        {"chat_id": "GLOBAL_CAPTION"},
        {"$set": {"text": html_text}},
        upsert=True
    )

async def delete_stored_caption():
    """Removes the custom caption from MongoDB."""
    await captiondb.delete_one({"chat_id": "GLOBAL_CAPTION"})

async def get_caption(_, link, title, duration, user):
    """Generates the final caption string."""
    custom_html = await get_stored_caption()
    if custom_html:
        try:
            # {0}=link, {1}=title, {2}=duration, {3}=user
            return custom_html.format(link, title, duration, user)
        except Exception:
            pass # Fallback to default if format invalid
    return _["stream_1"].format(link, title, duration, user)


# --- SETSTREAM COMMAND ---
@app.on_message(filters.command("setstream") & filters.user(ADMIN_ID))
async def set_stream_template(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "**Usage:**\n"
            "`/setstream [Your Formatted Text]`\n\n"
            "**Variables:**\n"
            "{0} - Link\n"
            "{1} - Title\n"
            "{2} - Duration\n"
            "{3} - Requested By\n\n"
            "**To Reset:** `/setstream reset`"
        )
    
    query = message.text.split(None, 1)[1]

    if query.lower().strip() == "reset":
        await delete_stored_caption()
        return await message.reply_text("✅ **Stream Caption Reset to Default!**")
    
    # Extract HTML to preserve EXACT formatting (bold, links, etc.)
    full_html = message.text.html
    command_trigger = message.text.split()[0]
    # Split to get text after command
    caption_html = full_html.split(command_trigger, 1)[1].strip()
    
    await save_stored_caption(caption_html)
    await message.reply_text("✅ **Custom Stream Caption Saved!**\n\nIt will persist after restarts.")


# --- MAIN STREAM FUNCTION ---

async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return
    if forceplay:
        await AMBOTOP.force_stop_stream(chat_id)
        
    # --- PLAYLIST ---
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = await YouTube.details(search, False if spotify else True)
            except:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                if not forceplay:
                    db[chat_id] = []
                status = True if video else None
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=status, videoid=True
                    )
                except:
                    raise AssistantErr(_["play_14"])
                await AMBOTOP.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=status,
                    image=thumbnail,
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                img = await gen_thumb(vidid)
                button = stream_markup(_, chat_id)
                
                # Fetch custom caption
                cap = await get_caption(
                    _, 
                    f"https://t.me/{app.username}?start=info_{vidid}", 
                    title[:23], 
                    duration_min, 
                    user_name
                )
                
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    has_spoiler=True,
                    caption=cap,
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        if count == 0:
            return
        else:
            link = await AMBOTOPBin(msg)
            lines = msg.count("\n")
            if lines >= 17:
                car = os.linesep.join(msg.split(os.linesep)[:17])
            else:
                car = msg
            carbon = await Carbon.generate(car, randint(100, 10000000))
            upl = close_markup(_)
            return await app.send_photo(
                original_chat_id,
                photo=carbon,
                caption=_["play_21"].format(position, link),
                reply_markup=upl,
            )

    # --- YOUTUBE ---
    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        status = True if video else None
    
        current_queue = db.get(chat_id)

        if current_queue is not None and len(current_queue) >= 10:
            return await app.send_message(original_chat_id, "You can't add more than 10 songs to the queue.")

        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, videoid=True, video=status
            )
        except:
            raise AssistantErr(_["play_14"])

        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await AMBOTOP.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await gen_thumb(vidid)
            button = stream_markup(_, chat_id)
            
            # Fetch custom caption
            cap = await get_caption(
                _, 
                f"https://t.me/{app.username}?start=info_{vidid}", 
                title[:23], 
                duration_min, 
                user_name
            )

            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

    # --- SOUNDCLOUD ---
    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await AMBOTOP.join_call(chat_id, original_chat_id, file_path, video=None)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            
            # Fetch custom caption
            cap = await get_caption(
                _, 
                config.SUPPORT_GROUP, 
                title[:23], 
                duration_min, 
                user_name
            )

            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # --- TELEGRAM ---
    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await AMBOTOP.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            if video:
                await add_active_video_chat(chat_id)
            button = stream_markup(_, chat_id)
            
            # Fetch custom caption
            cap = await get_caption(
                _, 
                link, 
                title[:23], 
                duration_min, 
                user_name
            )

            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # --- LIVE ---
    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "Live Track"
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            await AMBOTOP.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail if thumbnail else None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await gen_thumb(vidid)
            button = stream_markup(_, chat_id)
            
            # Fetch custom caption
            cap = await get_caption(
                _, 
                f"https://t.me/{app.username}?start=info_{vidid}", 
                title[:23], 
                duration_min, 
                user_name
            )

            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=cap,
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

    # --- INDEX / M3U8 ---
    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"
        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
        else:
            if not forceplay:
                db[chat_id] = []
            await AMBOTOP.join_call(
                chat_id,
                original_chat_id,
                link,
                video=True if video else None,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                has_spoiler=True,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            await mystic.delete()
