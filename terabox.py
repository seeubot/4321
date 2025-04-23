from aria2p import API as Aria2API, Client as Aria2Client
import asyncio
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
import math
import json
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
import time
import urllib.parse
from urllib.parse import urlparse
from flask import Flask, render_template
from threading import Thread

load_dotenv('config.env', override=True)
logging.basicConfig(
    level=logging.INFO,  
    format="[%(asctime)s - %(name)s - %(levelname)s] %(message)s - %(filename)s:%(lineno)d"
)

logger = logging.getLogger(__name__)

logging.getLogger("pyrogram.session").setLevel(logging.ERROR)
logging.getLogger("pyrogram.connection").setLevel(logging.ERROR)
logging.getLogger("pyrogram.dispatcher").setLevel(logging.ERROR)

aria2 = Aria2API(
    Aria2Client(
        host="http://localhost",
        port=6800,
        secret=""
    )
)
options = {
    "max-tries": "50",
    "retry-wait": "3",
    "continue": "true",
    "allow-overwrite": "true",
    "min-split-size": "4M",
    "split": "10"
}

aria2.set_global_options(options)

API_ID = os.environ.get('TELEGRAM_API', '')
if len(API_ID) == 0:
    logging.error("TELEGRAM_API variable is missing! Exiting now")
    exit(1)

API_HASH = os.environ.get('TELEGRAM_HASH', '')
if len(API_HASH) == 0:
    logging.error("TELEGRAM_HASH variable is missing! Exiting now")
    exit(1)
    
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
if len(BOT_TOKEN) == 0:
    logging.error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

DUMP_CHAT_ID = os.environ.get('DUMP_CHAT_ID', '')
if len(DUMP_CHAT_ID) == 0:
    logging.error("DUMP_CHAT_ID variable is missing! Exiting now")
    exit(1)
else:
    DUMP_CHAT_ID = int(DUMP_CHAT_ID)

FSUB_ID = os.environ.get('FSUB_ID', '')
if len(FSUB_ID) == 0:
    logging.error("FSUB_ID variable is missing! Exiting now")
    exit(1)
else:
    FSUB_ID = int(FSUB_ID)

USER_SESSION_STRING = os.environ.get('USER_SESSION_STRING', '')
if len(USER_SESSION_STRING) == 0:
    logging.info("USER_SESSION_STRING variable is missing! Bot will split Files in 2Gb...")
    USER_SESSION_STRING = None

ADMIN_IDS = os.environ.get('ADMIN_IDS', '').split(',')
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]

# Dictionary to store pending requests
pending_requests = {}

app = Client("jetbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user = None
SPLIT_SIZE = 2093796556
if USER_SESSION_STRING:
    user = Client("jetu", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION_STRING)
    SPLIT_SIZE = 4241280205

VALID_DOMAINS = [
    'terabox.com', 'nephobox.com', '4funbox.com', 'mirrobox.com', 
    'momerybox.com', 'teraboxapp.com', '1024tera.com', 
    'terabox.app', 'gibibox.com', 'goaibox.com', 'terasharelink.com', 
    'teraboxlink.com', 'terafileshare.com'
]
last_update_time = 0

# Updated API URL
TERABOX_API_URL = "https://teraboxapi-phi.vercel.app/api?url="

async def is_user_member(client, user_id):
    try:
        member = await client.get_chat_member(FSUB_ID, user_id)
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"Error checking membership status for user {user_id}: {e}")
        return False
    
def is_valid_url(url):
    parsed_url = urlparse(url)
    return any(parsed_url.netloc.endswith(domain) for domain in VALID_DOMAINS)

def format_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/dailydiskwala")
    developer_button = InlineKeyboardButton("Backup", url="https://t.me/terao2")
    repo69 = InlineKeyboardButton("Desi 18+", url="https://t.me/dailydiskwala")
    user_mention = message.from_user.mention
    reply_markup = InlineKeyboardMarkup([[join_button, developer_button], [repo69]])
    final_msg = f"ᴡᴇʟᴄᴏᴍᴇ, {user_mention}.\n\n🌟 ɪ ᴀᴍ ᴀ ᴛᴇʀᴀʙᴏx ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ. sᴇɴᴅ ᴍᴇ ᴀɴʏ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ɪ ᴡɪʟʟ ᴅᴏᴡɴʟᴏᴀᴅ ᴡɪᴛʜɪɴ ғᴇᴡ sᴇᴄᴏɴᴅs ᴀɴᴅ sᴇɴᴅ ɪᴛ ᴛᴏ ʏᴏᴜ ✨.\n\n📨 ᴜsᴇ /request ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ʀᴇǫᴜᴇsᴛ ᴀ ᴠɪᴅᴇᴏ ʙʏ sᴇɴᴅɪɴɢ ᴀɴ ɪᴍᴀɢᴇ ᴏʀ sᴄʀᴇᴇɴsʜᴏᴛ."
    video_file_id = "/app/tera.mp4"
    if os.path.exists(video_file_id):
        await client.send_video(
            chat_id=message.chat.id,
            video=video_file_id,
            caption=final_msg,
            reply_markup=reply_markup
            )
    else:
        await message.reply_text(final_msg, reply_markup=reply_markup)

@app.on_message(filters.command("request"))
async def request_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/dailydiskwala")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return

    # Parse command arguments
    command_parts = message.text.split(None, 1)
    
    # Check if there's any text attached to the command
    if len(command_parts) == 1:
        await message.reply_text(
            "📢 **ʜᴏᴡ ᴛᴏ ʀᴇǫᴜᴇsᴛ ᴀ ᴠɪᴅᴇᴏ:**\n\n"
            "1️⃣ sᴇɴᴅ /request ᴄᴏᴍᴍᴀɴᴅ ᴡɪᴛʜ ᴀ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ\n"
            "2️⃣ ᴀᴛᴛᴀᴄʜ ᴀɴ ɪᴍᴀɢᴇ ᴏʀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ᴛʜᴇ ᴠɪᴅᴇᴏ\n\n"
            "ᴇxᴀᴍᴘʟᴇ: `/request ᴘʟᴇᴀsᴇ ғɪɴᴅ ᴛʜɪs ᴍᴏᴠɪᴇ` + ɪᴍᴀɢᴇ"
        )
        return
    
    # Get the description text
    description = command_parts[1].strip()
    
    # Check if there's a photo attached to the message
    if message.photo:
        # Get the highest resolution photo
        photo = message.photo[-1]
        photo_file_id = photo.file_id
        
        # Generate a unique request ID
        request_id = f"{user_id}_{int(time.time())}"
        
        # Store the request in pending_requests
        pending_requests[request_id] = {
            "user_id": user_id,
            "description": description,
            "photo_id": photo_file_id,
            "username": message.from_user.username or "Unknown",
            "first_name": message.from_user.first_name or "Unknown",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Send confirmation to user
        await message.reply_text(
            "✅ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ sᴜʙᴍɪᴛᴛᴇᴅ!\n\n"
            "ᴏᴜʀ ᴀᴅᴍɪɴs ᴡɪʟʟ ʀᴇᴠɪᴇᴡ ɪᴛ ᴀɴᴅ ɢᴇᴛ ʙᴀᴄᴋ ᴛᴏ ʏᴏᴜ ɪғ ᴛʜᴇ ᴠɪᴅᴇᴏ ɪs ғᴏᴜɴᴅ."
        )
        
        # Forward the request to admins
        admin_buttons = [
            [
                InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f"approve_{request_id}"),
                InlineKeyboardButton("❌ ʀᴇᴊᴇᴄᴛ", callback_data=f"reject_{request_id}")
            ],
            [
                InlineKeyboardButton("💬 ᴍᴇssᴀɢᴇ ᴜsᴇʀ", callback_data=f"message_{request_id}")
            ]
        ]
        admin_markup = InlineKeyboardMarkup(admin_buttons)
        
        # Notify all admins about the request
        for admin_id in ADMIN_IDS:
            try:
                await client.send_photo(
                    chat_id=admin_id,
                    photo=photo_file_id,
                    caption=(
                        f"📨 **ɴᴇᴡ ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ**\n\n"
                        f"**ғʀᴏᴍ:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
                        f"**ᴜsᴇʀ ɪᴅ:** `{user_id}`\n"
                        f"**ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:** {description}\n\n"
                        f"**ʀᴇǫᴜᴇsᴛ ɪᴅ:** `{request_id}`"
                    ),
                    reply_markup=admin_markup
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    else:
        # No photo attached
        await message.reply_text(
            "❌ ᴘʟᴇᴀsᴇ ᴀᴛᴛᴀᴄʜ ᴀɴ ɪᴍᴀɢᴇ ᴏʀ sᴄʀᴇᴇɴsʜᴏᴛ ᴏғ ᴛʜᴇ ᴠɪᴅᴇᴏ ʏᴏᴜ'ʀᴇ ʀᴇǫᴜᴇsᴛɪɴɢ."
        )

@app.on_callback_query(filters.regex(r'^(approve|reject|message)_'))
async def handle_request_action(client, callback_query):
    # Check if the user is an admin
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("⚠️ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴘᴇʀғᴏʀᴍ ᴛʜɪs ᴀᴄᴛɪᴏɴ.", show_alert=True)
        return
    
    # Parse the callback data
    action, request_id = callback_query.data.split("_", 1)
    
    # Check if the request exists
    if request_id not in pending_requests:
        await callback_query.answer("⚠️ ᴛʜɪs ʀᴇǫᴜᴇsᴛ ɴᴏ ʟᴏɴɢᴇʀ ᴇxɪsᴛs.", show_alert=True)
        return
    
    request_data = pending_requests[request_id]
    user_id = request_data["user_id"]
    
    if action == "approve":
        # Admin is approving the request
        await callback_query.message.edit_caption(
            callback_query.message.caption + "\n\n✅ **ᴀᴘᴘʀᴏᴠᴇᴅ** ʙʏ ᴀᴅᴍɪɴ.",
            reply_markup=None
        )
        
        # Ask admin to provide the Terabox link
        await client.send_message(
            callback_query.from_user.id,
            f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ғᴏʀ ᴛʜɪs ʀᴇǫᴜᴇsᴛ.\n\n"
            f"**ʀᴇǫᴜᴇsᴛ ɪᴅ:** `{request_id}`\n\n"
            f"ʀᴇᴘʟʏ ᴛᴏ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪᴛʜ ᴛʜᴇ ʟɪɴᴋ."
        )
        
        # Update the request status
        pending_requests[request_id]["status"] = "approved"
        pending_requests[request_id]["approver_id"] = callback_query.from_user.id
        
        await callback_query.answer("✅ ʀᴇǫᴜᴇsᴛ ᴀᴘᴘʀᴏᴠᴇᴅ. ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ.")
        
    elif action == "reject":
        # Admin is rejecting the request
        await callback_query.message.edit_caption(
            callback_query.message.caption + "\n\n❌ **ʀᴇᴊᴇᴄᴛᴇᴅ** ʙʏ ᴀᴅᴍɪɴ.",
            reply_markup=None
        )
        
        # Notify the user
        try:
            await client.send_message(
                user_id,
                "❌ ʏᴏᴜʀ ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ʀᴇᴊᴇᴄᴛᴇᴅ.\n\n"
                "ᴘᴏssɪʙʟᴇ ʀᴇᴀsᴏɴs:\n"
                "- ᴛʜᴇ ᴠɪᴅᴇᴏ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ ғᴏᴜɴᴅ\n"
                "- ɪɴsᴜғғɪᴄɪᴇɴᴛ ɪɴғᴏʀᴍᴀᴛɪᴏɴ ᴘʀᴏᴠɪᴅᴇᴅ\n"
                "- ᴛʜᴇ ᴠɪᴅᴇᴏ ɪs ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ"
            )
        except Exception as e:
            logger.error(f"Failed to notify user about rejection: {e}")
        
        # Remove the request from pending_requests
        del pending_requests[request_id]
        
        await callback_query.answer("❌ ʀᴇǫᴜᴇsᴛ ʀᴇᴊᴇᴄᴛᴇᴅ ᴀɴᴅ ᴜsᴇʀ ɴᴏᴛɪғɪᴇᴅ.")
        
    elif action == "message":
        # Admin wants to message the user
        await client.send_message(
            callback_query.from_user.id,
            f"ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴛʜᴇ ᴍᴇssᴀɢᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ sᴇɴᴅ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ.\n\n"
            f"**ʀᴇǫᴜᴇsᴛ ɪᴅ:** `{request_id}`\n\n"
            f"ʀᴇᴘʟʏ ᴛᴏ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪᴛʜ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ."
        )
        
        # Update the request status
        pending_requests[request_id]["status"] = "messaging"
        pending_requests[request_id]["admin_id"] = callback_query.from_user.id
        
        await callback_query.answer("✏️ ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ.")

@app.on_message(filters.reply & filters.private & filters.user(ADMIN_IDS))
async def handle_admin_reply(client, message):
    # Check if the message is a reply
    if not message.reply_to_message:
        return
    
    # Check if the replied-to message contains a request ID
    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    request_id_match = None
    
    for line in replied_text.split("\n"):
        if "ʀᴇǫᴜᴇsᴛ ɪᴅ:" in line:
            request_id_match = line.split("`")[1] if len(line.split("`")) > 1 else None
            break
    
    if not request_id_match or request_id_match not in pending_requests:
        return
    
    request_data = pending_requests[request_id_match]
    user_id = request_data["user_id"]
    
    # Check the status of the request
    if "status" in request_data and request_data["status"] == "messaging":
        # Admin is sending a message to the user
        try:
            await client.send_message(
                user_id,
                f"📨 **ᴍᴇssᴀɢᴇ ғʀᴏᴍ ᴀᴅᴍɪɴ ʀᴇɢᴀʀᴅɪɴɢ ʏᴏᴜʀ ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ:**\n\n{message.text}"
            )
            await message.reply_text("✅ ᴍᴇssᴀɢᴇ sᴇɴᴛ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ.")
        except Exception as e:
            await message.reply_text(f"❌ ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴍᴇssᴀɢᴇ: {str(e)}")
    
    elif "status" in request_data and request_data["status"] == "approved":
        # Admin is providing the Terabox link
        terabox_url = message.text.strip()
        
        if is_valid_url(terabox_url):
            await message.reply_text("✅ ᴘʀᴏᴄᴇssɪɴɢ ᴛʜᴇ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ᴀɴᴅ sᴇɴᴅɪɴɢ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ...")
            
            # Notify the user that their request is being processed
            try:
                await client.send_message(
                    user_id,
                    "🎉 ɢᴏᴏᴅ ɴᴇᴡs! ᴡᴇ ғᴏᴜɴᴅ ᴛʜᴇ ᴠɪᴅᴇᴏ ʏᴏᴜ ʀᴇǫᴜᴇsᴛᴇᴅ ᴀɴᴅ ɪᴛ's ʙᴇɪɴɢ ᴘʀᴏᴄᴇssᴇᴅ ɴᴏᴡ.\n\n"
                    "ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴡʜɪʟᴇ ɪ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ᴜᴘʟᴏᴀᴅ ɪᴛ ғᴏʀ ʏᴏᴜ."
                )
            except Exception as e:
                logger.error(f"Failed to send processing notification: {e}")
            
            # Process the Terabox link
            try:
                await process_terabox_link(client, user_id, terabox_url, is_request=True)
                
                # Delete the request since it's been fulfilled
                del pending_requests[request_id_match]
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                await message.reply_text(f"❌ ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ᴛʜᴇ ʟɪɴᴋ: {str(e)}")
                
                # Notify the user about the failure
                try:
                    await client.send_message(
                        user_id,
                        "❌ sᴏʀʀʏ, ᴛʜᴇʀᴇ ᴡᴀs ᴀɴ ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛᴇᴅ ᴠɪᴅᴇᴏ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user about processing error: {e}")
        else:
            await message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ.")

async def update_status_message(status_message, text):
    try:
        await status_message.edit_text(text)
    except Exception as e:
        logger.error(f"Failed to update status message: {e}")

async def process_terabox_link(client, user_id, url, message=None, is_request=False):
    status_message = None
    if message:
        status_message = await message.reply_text("sᴇɴᴅɪɴɢ ʏᴏᴜ ᴛʜᴇ ᴍᴇᴅɪᴀ...🤤")

    start_time = datetime.now()
    
    try:
        # Use the new API endpoint
        encoded_url = urllib.parse.quote(url)
        api_url = f"{TERABOX_API_URL}{encoded_url}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    error_text = f"API Error: Status code {response.status}"
                    if status_message:
                        await status_message.edit_text(error_text)
                    else:
                        await client.send_message(user_id, error_text)
                    return
                
                data = await response.json()
                
                if data.get("status") != "success" or not data.get("Extracted Info"):
                    error_text = f"Failed to extract download info: {data.get('status', 'Unknown error')}"
                    if status_message:
                        await status_message.edit_text(error_text)
                    else:
                        await client.send_message(user_id, error_text)
                    return
                
                file_info = data["Extracted Info"][0]
                direct_download_link = file_info.get("Direct Download Link")
                file_size = file_info.get("Size", "Unknown size")
                file_title = file_info.get("Title", "Unknown title")
                
                if not direct_download_link:
                    error_text = "Failed to get direct download link from API"
                    if status_message:
                        await status_message.edit_text(error_text)
                    else:
                        await client.send_message(user_id, error_text)
                    return
                
                # Download the file using aria2
                download = aria2.add_uris([direct_download_link])
                
                if status_message:
                    await status_message.edit_text("sᴛᴀʀᴛɪɴɢ ᴅᴏᴡɴʟᴏᴀᴅ...")
                
                last_update_time = time.time()
                UPDATE_INTERVAL = 15
                
                while not download.is_complete:
                    await asyncio.sleep(15)
                    download.update()
                    progress = download.progress
                    
                    elapsed_time = datetime.now() - start_time
                    elapsed_minutes, elapsed_seconds = divmod(elapsed_time.seconds, 60)
                    
                    status_text = (
                        f"┏ ғɪʟᴇɴᴀᴍᴇ: {download.name}\n"
                        f"┠ [{'★' * int(progress / 10)}{'☆' * (10 - int(progress / 10))}] {progress:.2f}%\n"
                        f"┠ ᴘʀᴏᴄᴇssᴇᴅ: {format_size(download.completed_length)} ᴏғ {format_size(download.total_length)}\n"
                        f"┠ sᴛᴀᴛᴜs: 📥 Downloading\n"
                        f"┠ ᴇɴɢɪɴᴇ: <b><u>Aria2c v1.37.0</u></b>\n"
                        f"┠ sᴘᴇᴇᴅ: {format_size(download.download_speed)}/s\n"
                        f"┠ ᴇᴛᴀ: {download.eta} | ᴇʟᴀᴘsᴇᴅ: {elapsed_minutes}m {elapsed_seconds}s\n"
                        f"┖ ᴜsᴇʀ: <a href='tg://user?id={user_id}'>{message.from_user.first_name if message else 'User'}</a> | ɪᴅ: {user_id}\n"
                    )
                    
                    current_time = time.time()
                    if current_time - last_update_time >= UPDATE_INTERVAL and status_message:
                        try:
                            await update_status_message(status_message, status_text)
                            last_update_time = current_time
                        except FloodWait as e:
                            logger.error(f"Flood wait detected! Sleeping for {e.value} seconds")
                            await asyncio.sleep(e.value)
                
                file_path = download.files[0].path
                
                # Create caption
                caption = (
                    f"✨ {download.name}\n"
                    f"👤 ʟᴇᴇᴄʜᴇᴅ ʙʏ : <a href='tg://user?id={user_id}'>{message.from_user.first_name if message else 'User'}</a>\n"
                    f"📥 ᴜsᴇʀ ʟɪɴᴋ: tg://user?id={user_id}\n\n"
                    "[ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴊᴇᴛ-ᴍɪʀʀᴏʀ ❤️🚀](https://t.me/JetMirror)"
                )
                
                await handle_upload(client, user_id, file_path, caption, status_message, message)
                
                if status_message:
                    try:
                        await status_message.delete()
                    except Exception as e:
                        logger.error(f"Failed to delete status message: {e}")
                
                if message and not is_request:
                    try:
                        await message.delete()
                    except Exception as e:
                        logger.error(f"Failed to delete original message: {e}")
    
    except Exception as e:
        error_message = f"Error processing Terabox link: {str(e)}"
        logger.error(error_message)
        if status_message:
            await status_message.edit_text(error_message)
        else:
            await client.send_message(user_id, error_message)

async def update_progress_status(message, text):
    global last_update_time
    current_time = time.time()
    UPDATE_INTERVAL = 15
    
    if current_time - last_update_time >= UPDATE_INTERVAL:
        try:
            await message.edit_text(text)
            last_update_time = current_time
        except FloodWait as e:
            logger.warning(f"FloodWait: Sleeping for {e.value}s")
            await asyncio.sleep(e.value)
            await update_progress_status(message, text)
        except Exception as e:
            logger.error(f"Error updating status: {e}")

async def upload_progress(current, total, start_time, status_message, user_id, message):
    progress = (current / total) * 100
    elapsed_time = datetime.now() - start_time
    elapsed_minutes, elapsed_seconds = divmod(elapsed_time.seconds, 60)
    
    if not status_message:
        return
    
    file_name = getattr(message, 'file_name', 'Uploading file')
    
    status_text = (
        f"┏ ғɪʟᴇɴᴀᴍᴇ: {file_name}\n"
        f"┠ [{'★' * int(progress / 10)}{'☆' * (10 - int(progress / 10))}] {progress:.2f}%\n"
        f"┠ ᴘʀᴏᴄᴇssᴇᴅ: {format_size(current)} ᴏғ {format_size(total)}\n"
        f"┠ sᴛᴀᴛᴜs: 📤 Uploading to Telegram\n"
        f"┠ ᴇɴɢɪɴᴇ: <b><u>PyroFork v2.2.11</u></b>\n"
        f"┠ sᴘᴇᴇᴅ: {format_size(current / elapsed_time.seconds if elapsed_time.seconds > 0 else 0)}/s\n"
        f"┠ ᴇʟᴀᴘsᴇᴅ: {elapsed_minutes}m {elapsed_seconds}s\n"
        f"┖ ᴜsᴇʀ: <a href='tg://user?id={user_id}'>{message.from_user.first_name if hasattr(message, 'from_user') else 'User'}</a> | ɪᴅ: {user_id}\n"
    )
    await update_progress_status(status_message, status_text)

async def split_video_with_ffmpeg(input_path, output_prefix, split_size, status_message):
    try:
        original_ext = os.path.splitext(input_path)[1].lower() or '.mp4'
        start_time = datetime.now()
        last_progress_update = time.time()
        
        proc = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        total_duration = float(stdout.decode().strip())
        
        file_size = os.path.getsize(input_path)
        parts = math.ceil(file_size / split_size)
        
        if parts == 1:
            return [input_path]
        
        duration_per_part = total_duration / parts
        split_files = []
        
        for i in range(parts):
            current_time = time.time()
            if current_time - last_progress_update >= 15:
                elapsed = datetime.now() - start_time
                status_text = (
                    f"✂️ Splitting {os.path.basename(input_path)}\n"
                    f"Part {i+1}/{parts}\n"
                    f"Elapsed: {elapsed.seconds // 60}m {elapsed.seconds % 60}s"
                )
                if status_message:
                    await update_status_message(status_message, status_text)
                last_progress_update = current_time
            
            output_path = f"{output_prefix}.{i+1:03d}{original_ext}"
            cmd = [
                'xtra', '-y', '-ss', str(i * duration_per_part),
                '-i', input_path, '-t', str(duration_per_part),
                '-c', 'copy', '-map', '0',
                '-avoid_negative_ts', 'make_zero',
                output_path
            ]
            
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            split_files.append(output_path)
        
        return split_files
    except Exception as e:
        logger.error(f"Split error: {e}")
        raise

async def handle_upload(client, user_id, file_path, caption, status_message=None, message=None):
    file_size = os.path.getsize(file_path)
    
    if file_size > SPLIT_SIZE:
        if status_message:
            await update_status_message(
                status_message,
                f"✂️ Splitting {os.path.basename(file_path)} ({format_size(file_size)})"
            )
        
        split_files = await split_video_with_ffmpeg(
            file_path,
            os.path.splitext(file_path)[0],
            SPLIT_SIZE,
            status_message
        )
        
        try:
            for i, part in enumerate(split_files):
                part_caption = f"{caption}\n\nPart {i+1}/{len(split_files)}"
                if status_message:
                    await update_status_message(
                        status_message,
                        f"📤 Uploading part {i+1}/{len(split_files)}\n"
                        f"{os.path.basename(part)}"
                    )
                
                start_time = datetime.now()
                
                if USER_SESSION_STRING:
                    sent = await user.send_video(
                        DUMP_CHAT_ID, part, 
                        caption=part_caption,
                        progress=lambda current, total: upload_progress(
                            current, total, start_time, status_message, user_id, message
                        )
                    )
                    await app.copy_message(
                        user_id, DUMP_CHAT_ID, sent.id
                    )
                else:
                    sent = await client.send_video(
                        DUMP_CHAT_ID, part,
                        caption=part_caption,
                        progress=lambda current, total: upload_progress(
                            current, total, start_time, status_message, user_id, message
                        )
                    )
                    await client.send_video(
                        user_id, sent.video.file_id,
                        caption=part_caption
                    )
                os.remove(part)
        finally:
            for part in split_files:
                try: os.remove(part)
                except: pass
    else:
        if status_message:
            await update_status_message(
                status_message,
                f"📤 Uploading {os.path.basename(file_path)}\n"
                f"Size: {format_size(file_size)}"
            )
        
        start_time = datetime.now()
        
        if USER_SESSION_STRING:
            sent = await user.send_video(
                DUMP_CHAT_ID, file_path,
                caption=caption,
                progress=lambda current, total: upload_progress(
                    current, total, start_time, status_message, user_id, message
                )
            )
            await app.copy_message(
                user_id, DUMP_CHAT_ID, sent.id
            )
        else:
            sent = await client.send_video(
                DUMP_CHAT_ID, file_path,
                caption=caption,
                progress=lambda current, total: upload_progress(
                    current, total, start_time, status_message, user_id, message
                )
            )
            await client.send_video(
                user_id, sent.video.file_id,
                caption=caption
            )
    
    if os.path.exists(file_path):
        os.remove(file_path)

@app.on_message(filters.text)
async def handle_message(client: Client, message: Message):
    if message.text.startswith('/'):
        return
    if not message.from_user:
        return

    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/jetmirror")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return
    
    url = None
    for word in message.text.split():
        if is_valid_url(word):
            url = word
            break

    if not url:
        await message.reply_text("Please provide a valid Terabox link.")
        return

    await process_terabox_link(client, user_id, url, message)

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return render_template("index.html")

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def keep_alive():
    Thread(target=run_flask).start()

async def start_user_client():
    if user:
        await user.start()
        logger.info("User client started.")

def run_user():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_user_client())

if __name__ == "__main__":
    keep_alive()

    if user:
        logger.info("Starting user client...")
        Thread(target=run_user).start()

    logger.info("Starting bot client...")
    app.run()
