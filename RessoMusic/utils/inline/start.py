from pyrogram.types import InlineKeyboardButton

import config
from RessoMusic import app


def start_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_1"], url=f"https://t.me/{app.username}?startgroup=true"
            ),
            InlineKeyboardButton(text=_["S_B_2"], url=config.SUPPORT_GROUP),
        ],
    ]
    return buttons


def private_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                "˹𝐴𝑑𝑑 𝑀𝑒 𝑖𝑛 𝑌𝑜𝑢𝑟 𝐺𝑟𝑜𝑢𝑝 ˼ 🥀",
                url=f"https://t.me/{app.username}?startgroup=true",
            )
        ],
        [InlineKeyboardButton("𝑆𝑢𝑝𝑝𝑜𝑟𝑡 ", url="https://t.me/+n3up-KjYupFlYjNi"),
        InlineKeyboardButton("𝑈𝑝𝑑𝑎𝑡𝑒𝑠", url="https://t.me/elyramusicupdate"),
            #InlineKeyboardButton(text=_["S_B_7"], url=config.UPSTREAM_REPO),
        ],
        [InlineKeyboardButton("𝐻𝑒𝑙𝑝", callback_data="settings_back_helper"),
         InlineKeyboardButton("𝑀𝑦 𝐿𝑜𝑟𝑑 👑", url=f"https://t.me/ll_RUHAN_ll")

        ],
        
    ]
    return buttons






