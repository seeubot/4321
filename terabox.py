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

# Add a channel to store requests
REQUEST_STORE_CHANNEL = os.environ.get('REQUEST_STORE_CHANNEL', '')
if len(REQUEST_STORE_CHANNEL) == 0:
    logging.warning("REQUEST_STORE_CHANNEL variable is missing! Using DUMP_CHAT_ID as default")
    REQUEST_STORE_CHANNEL = DUMP_CHAT_ID
else:
    REQUEST_STORE_CHANNEL = int(REQUEST_STORE_CHANNEL)

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
        
        # Forward the request to the request store channel
        forwarded_msg = await client.send_photo(
            chat_id=REQUEST_STORE_CHANNEL,
            photo=photo_file_id,
            caption=(
                f"📨 **ɴᴇᴡ ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ**\n\n"
                f"**ғʀᴏᴍ:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
                f"**ᴜsᴇʀ ɪᴅ:** `{user_id}`\n"
                f"**ᴅᴇsᴄʀɪᴘᴛɪᴏɴ:** {description}\n\n"
                f"**ʀᴇǫᴜᴇsᴛ ɪᴅ:** `{request_id}`"
            )
        )
        
        # Create buttons for the admin notification
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
                    "❌ Sorry, there was an error processing your requested video. Our team will look into this issue."
                )
        else:
            await message.reply_text("❌ Invalid Terabox URL. Please provide a valid URL from one of the supported domains.")

async def process_terabox_link(client, user_id, url, is_request=False):
    """Process a Terabox link and send the downloaded file to the user"""
    status_message = await client.send_message(user_id, "⏳ Processing your link...")
    
    try:
        # Encode URL for API request
        encoded_url = urllib.parse.quote(url)
        api_url = f"{TERABOX_API_URL}{encoded_url}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    await status_message.edit_text(f"❌ API error: {response.status}")
                    return
                
                data = await response.json()
                
                if not data.get("success"):
                    error_msg = data.get("message", "Unknown error")
                    await status_message.edit_text(f"❌ Error: {error_msg}")
                    return
                
                file_data = data.get("data", {})
                file_name = file_data.get("file_name", "terabox_file")
                file_size = int(file_data.get("size", 0))
                direct_link = file_data.get("direct_link")
                
                if not direct_link:
                    await status_message.edit_text("❌ Direct download link not found!")
                    return
                
                await status_message.edit_text(
                    f"✅ Link processed successfully!\n\n"
                    f"**File Name:** {file_name}\n"
                    f"**Size:** {format_size(file_size)}\n\n"
                    f"⏳ Starting download now..."
                )
                
                # Add to aria2
                download = aria2.add_uris([direct_link], {"out": file_name})
                gid = download.gid
                
                # Update status message periodically
                while True:
                    download = aria2.get_download(gid)
                    
                    # Calculate progress
                    completed_length = download.completed_length
                    total_length = download.total_length
                    
                    if total_length > 0:
                        progress = completed_length / total_length * 100
                    else:
                        progress = 0
                    
                    status = download.status
                    
                    if status == "active":
                        speed = download.download_speed
                        eta = "N/A"
                        if speed > 0:
                            eta_seconds = (total_length - completed_length) / speed
                            eta = str(datetime.timedelta(seconds=int(eta_seconds)))
                        
                        await status_message.edit_text(
                            f"⏬ Downloading: {file_name}\n\n"
                            f"**Progress:** {progress:.2f}%\n"
                            f"**Speed:** {format_size(speed)}/s\n"
                            f"**ETA:** {eta}\n"
                            f"**Size:** {format_size(completed_length)} / {format_size(total_length)}"
                        )
                    elif status == "complete":
                        await status_message.edit_text(
                            f"✅ Download completed!\n\n"
                            f"**File:** {file_name}\n"
                            f"**Size:** {format_size(total_length)}\n\n"
                            f"⏳ Preparing to upload..."
                        )
                        break
                    elif status == "error":
                        await status_message.edit_text(
                            f"❌ Download error!\n\n"
                            f"**File:** {file_name}\n"
                            f"**Error:** {download.error_message}"
                        )
                        return
                    
                    await asyncio.sleep(3)  # Update every 3 seconds
                
                # Upload the file to Telegram
                file_path = os.path.join(download.dir, download.name)
                
                await upload_file(client, user_id, status_message, file_path, file_name, file_size)
                
                # Clean up the downloaded file
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing file: {e}")
    
    except Exception as e:
        logger.error(f"Error processing Terabox link: {e}")
        await status_message.edit_text(f"❌ Error processing link: {str(e)}")

async def upload_file(client, user_id, status_message, file_path, file_name, file_size):
    """Upload the downloaded file to Telegram"""
    try:
        if user and file_size > SPLIT_SIZE:  # Use user client for large files
            await status_message.edit_text(
                f"⏳ File size is larger than 2GB. Using user account for uploading...\n\n"
                f"**File:** {file_name}\n"
                f"**Size:** {format_size(file_size)}"
            )
            
            # If file size is larger than the user client split size, we need to split
            if file_size > SPLIT_SIZE:
                await status_message.edit_text(
                    f"⏳ File size is large. Splitting and uploading in parts...\n\n"
                    f"**File:** {file_name}\n"
                    f"**Size:** {format_size(file_size)}"
                )
                
                # Split and upload the file
                total_parts = math.ceil(file_size / SPLIT_SIZE)
                for i in range(total_parts):
                    part_msg = await status_message.edit_text(
                        f"⏳ Uploading part {i+1}/{total_parts}...\n\n"
                        f"**File:** {file_name}\n"
                        f"**Size:** {format_size(file_size)}"
                    )
                    
                    # Calculate the start and end bytes for this part
                    start = i * SPLIT_SIZE
                    end = min((i + 1) * SPLIT_SIZE, file_size)
                    
                    part_size = end - start
                    part_file_name = f"{file_name}.part{i+1}"
                    
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        part_data = f.read(part_size)
                    
                    with open(part_file_name, "wb") as f:
                        f.write(part_data)
                    
                    # Upload the part
                    try:
                        await user.send_document(
                            chat_id=user_id,
                            document=part_file_name,
                            caption=f"{file_name} (Part {i+1}/{total_parts})",
                            force_document=True,
                            progress=progress_callback,
                            progress_args=(part_msg, start, end)
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        await user.send_document(
                            chat_id=user_id,
                            document=part_file_name,
                            caption=f"{file_name} (Part {i+1}/{total_parts})",
                            force_document=True
                        )
                    
                    # Clean up the part file
                    try:
                        os.remove(part_file_name)
                    except Exception as e:
                        logger.error(f"Error removing part file: {e}")
                
                await status_message.edit_text(
                    f"✅ File uploaded successfully in {total_parts} parts!\n\n"
                    f"**File:** {file_name}\n"
                    f"**Size:** {format_size(file_size)}"
                )
            else:
                # Upload the whole file with the user client
                try:
                    await user.send_document(
                        chat_id=user_id,
                        document=file_path,
                        caption=file_name,
                        force_document=True,
                        progress=progress_callback,
                        progress_args=(status_message, 0, file_size)
                    )
                    
                    await status_message.edit_text(
                        f"✅ File uploaded successfully!\n\n"
                        f"**File:** {file_name}\n"
                        f"**Size:** {format_size(file_size)}"
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await user.send_document(
                        chat_id=user_id,
                        document=file_path,
                        caption=file_name,
                        force_document=True
                    )
                    
                    await status_message.edit_text(
                        f"✅ File uploaded successfully!\n\n"
                        f"**File:** {file_name}\n"
                        f"**Size:** {format_size(file_size)}"
                    )
        else:
            # Upload with the bot client
            if file_size > 2 * 1024 * 1024 * 1024:
                await status_message.edit_text(
                    f"❌ File size ({format_size(file_size)}) is too large for bot to upload.\n"
                    f"Maximum size is 2GB."
                )
                return
            
            # Check if it's a video file
            file_ext = os.path.splitext(file_name)[1].lower()
            is_video = file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm']
            
            try:
                if is_video:
                    # For videos, send as video
                    await client.send_video(
                        chat_id=user_id,
                        video=file_path,
                        caption=file_name,
                        progress=progress_callback,
                        progress_args=(status_message, 0, file_size),
                        supports_streaming=True
                    )
                else:
                    # For other files, send as document
                    await client.send_document(
                        chat_id=user_id,
                        document=file_path,
                        caption=file_name,
                        force_document=True,
                        progress=progress_callback,
                        progress_args=(status_message, 0, file_size)
                    )
                
                await status_message.edit_text(
                    f"✅ File uploaded successfully!\n\n"
                    f"**File:** {file_name}\n"
                    f"**Size:** {format_size(file_size)}"
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                
                if is_video:
                    await client.send_video(
                        chat_id=user_id,
                        video=file_path,
                        caption=file_name,
                        supports_streaming=True
                    )
                else:
                    await client.send_document(
                        chat_id=user_id,
                        document=file_path,
                        caption=file_name,
                        force_document=True
                    )
                
                await status_message.edit_text(
                    f"✅ File uploaded successfully!\n\n"
                    f"**File:** {file_name}\n"
                    f"**Size:** {format_size(file_size)}"
                )
    
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        await status_message.edit_text(f"❌ Error uploading file: {str(e)}")

async def progress_callback(current, total, message, start_byte=0, total_size=0):
    """Callback function for tracking upload progress"""
    if total == 0:
        return
    
    now = time.time()
    global last_update_time
    
    # Only update the message every 5 seconds to avoid API limits
    if now - last_update_time < 5:
        return
    
    last_update_time = now
    
    # Calculate progress
    if total_size > 0:
        # For split uploads
        progress = (start_byte + current) / total_size * 100
    else:
        # For normal uploads
        progress = current / total * 100
    
    try:
        await message.edit_text(
            f"⏫ Uploading...\n\n"
            f"**Progress:** {progress:.2f}%\n"
            f"**Uploaded:** {format_size(current)} / {format_size(total)}"
        )
    except Exception as e:
        logger.error(f"Error updating progress: {e}")

@app.on_message(filters.text & filters.private)
async def handle_terabox_link(client: Client, message: Message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/dailydiskwala")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return

    url = message.text.strip()
    
    if not is_valid_url(url):
        await message.reply_text(
            "❌ Invalid URL! Please send a valid Terabox link.\n\n"
            "Supported domains are: " + ", ".join(VALID_DOMAINS)
        )
        return
    
    await process_terabox_link(client, user_id, url)

# Simple web interface to show the bot is running
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app_web.run(host='0.0.0.0', port=8080)

async def main():
    global last_update_time
    last_update_time = time.time()
    
    # Start the web server
    web_server = Thread(target=run_flask)
    web_server.daemon = True
    web_server.start()
    
    if user:
        await user.start()
        logger.info("User client started!")
    
    await app.start()
    logger.info("Bot started!")
    
    # Keep the bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
