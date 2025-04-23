import asyncio
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
import math
import json
import aiohttp
import time
import urllib.parse
from urllib.parse import urlparse
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait

load_dotenv('config.env', override=True)
logging.basicConfig(
    level=logging.INFO,  
    format="[%(asctime)s - %(name)s - %(levelname)s] %(message)s - %(filename)s:%(lineno)d"
)

logger = logging.getLogger(__name__)

logging.getLogger("pyrogram.session").setLevel(logging.ERROR)
logging.getLogger("pyrogram.connection").setLevel(logging.ERROR)
logging.getLogger("pyrogram.dispatcher").setLevel(logging.ERROR)

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

# Direct download function
async def direct_download(url, file_path, session, status_message=None):
    try:
        # Create file directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        
        # Start download with streaming to monitor progress
        async with session.get(url, timeout=60) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_progress_update = 0
            start_time = time.time()
            
            with open(file_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(1024*1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 5% or 3 seconds
                        progress = (downloaded / total_size) * 100 if total_size > 0 else 0
                        current_time = time.time()
                        if (progress - last_progress_update >= 5 or current_time - start_time >= 3) and status_message:
                            speed = downloaded / (current_time - start_time)
                            await status_message.edit_text(
                                f"⬇️ Downloading: {os.path.basename(file_path)}\n"
                                f"Progress: {progress:.2f}%\n"
                                f"Speed: {format_size(speed)}/s\n"
                                f"Downloaded: {format_size(downloaded)} / {format_size(total_size)}"
                            )
                            last_progress_update = progress
                            
            return True
    except Exception as e:
        logging.error(f"Direct download error: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        return False

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
                # Process Terabox link and send to user
                status_msg = await client.send_message(
                    user_id,
                    "⬇️ Downloading your requested video...\n\nThis may take some time depending on the file size."
                )
                
                # Download and process the Terabox link
                try:
                    await process_url(client, message, terabox_url, user_id=user_id, status_message=status_msg)
                    
                    # Mark request as fulfilled
                    pending_requests[request_id_match]["status"] = "fulfilled"
                    await message.reply_text("✅ File successfully sent to the user!")
                    
                except Exception as e:
                    logger.error(f"Failed to process Terabox link: {e}")
                    await message.reply_text(f"❌ Failed to process the link: {str(e)}")
                    await client.send_message(
                        user_id,
                        "❌ Sorry, there was an error processing your requested video. Please try again later."
                    )
            except Exception as e:
                await message.reply_text(f"❌ Failed to notify user: {str(e)}")
        else:
            await message.reply_text("❌ Invalid Terabox URL. Please provide a valid Terabox link.")
            except Exception as e:
                logger.error(f"Failed to process Terabox link: {e}")
                await message.reply_text(f"❌ Failed to process the link: {str(e)}")
                await client.send_message(
                    user_id,
                    "❌ Sorry, there was an error processing your requested video. Please try again later."
                )
        else:
            await message.reply_text("❌ Invalid Terabox URL. Please provide a valid Terabox link.")

@app.on_message(filters.text & filters.incoming & ~filters.command)
async def handle_url(client: Client, message: Message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/dailydiskwala")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return

    url = message.text.strip()
    if not is_valid_url(url):
        await message.reply_text("❌ Invalid URL. Please send a valid Terabox URL.")
        return
        
    await process_url(client, message, url)

async def process_url(client, message, url, user_id=None, status_message=None):
    """Process a Terabox URL and send the downloaded file"""
    if user_id is None:
        user_id = message.from_user.id
        
    # If no status message provided, create one
    if status_message is None:
        status_message = await client.send_message(
            user_id,
            "🔍 Processing your Terabox link... Please wait."
        )

    try:
        # Encode URL for API request
        encoded_url = urllib.parse.quote(url)
        api_url = f"{TERABOX_API_URL}{encoded_url}"
        
        # Update status
        await status_message.edit_text("🔍 Fetching file information...")
        
        # Get file info from API
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=60) as response:
                if response.status != 200:
                    await status_message.edit_text(f"❌ API Error: Status code {response.status}")
                    return
                    
                data = await response.json()
                
                if not data.get("status"):
                    error_msg = data.get("msg", "Unknown error")
                    await status_message.edit_text(f"❌ API Error: {error_msg}")
                    return
                
                file_list = data.get("file_list", [])
                if not file_list:
                    await status_message.edit_text("❌ No files found in this Terabox link.")
                    return
                
                # Process each file in the list
                for file_info in file_list:
                    file_name = file_info.get("file_name", "unknown")
                    file_size = int(file_info.get("size", 0))
                    download_url = file_info.get("direct_download_link")
                    
                    if not download_url:
                        await status_message.edit_text(f"❌ Failed to get download link for {file_name}")
                        continue
                    
                    # Update status with file info
                    await status_message.edit_text(
                        f"ℹ️ File information:\n"
                        f"Name: {file_name}\n"
                        f"Size: {format_size(file_size)}\n\n"
                        f"⬇️ Starting download..."
                    )
                    
                    # Check if file size is within limits
                    if file_size > 2 * 1024 * 1024 * 1024 and not USER_SESSION_STRING:  # 2GB limit for bot API
                        await status_message.edit_text(
                            f"❌ File size ({format_size(file_size)}) exceeds the bot's limit (2GB)."
                        )
                        continue
                    
                    # Create temporary file path
                    temp_dir = f"downloads/{user_id}"
                    os.makedirs(temp_dir, exist_ok=True)
                    file_path = os.path.join(temp_dir, file_name)
                    
                    # Download the file
                    download_success = await direct_download(
                        download_url, file_path, session, status_message
                    )
                    
                    if not download_success:
                        await status_message.edit_text("❌ Download failed. Please try again later.")
                        continue
                    
                    # Upload file to Telegram
                    await status_message.edit_text(f"⬆️ Uploading: {file_name}...")
                    
                    try:
                        if file_size > SPLIT_SIZE:  # Need to split the file
                            await split_and_upload_file(client, file_path, user_id, status_message)
                        else:
                            # Determine file type for appropriate upload method
                            if file_name.lower().endswith((".mp4", ".mkv", ".avi", ".mov")):
                                await client.send_video(
                                    chat_id=user_id,
                                    video=file_path,
                                    caption=f"📁 {file_name}\n\n💾 {format_size(file_size)}",
                                    progress=upload_progress,
                                    progress_args=(status_message, time.time())
                                )
                            else:
                                await client.send_document(
                                    chat_id=user_id,
                                    document=file_path,
                                    caption=f"📁 {file_name}\n\n💾 {format_size(file_size)}",
                                    progress=upload_progress,
                                    progress_args=(status_message, time.time())
                                )
                        
                        # Clean up the file
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            
                        await status_message.edit_text("✅ File uploaded successfully!")
                        
                    except FloodWait as e:
                        await status_message.edit_text(f"⚠️ Telegram rate limit hit. Waiting for {e.value} seconds...")
                        await asyncio.sleep(e.value)
                        await status_message.edit_text("🔄 Retrying upload...")
                        
                    except Exception as e:
                        logger.error(f"Upload error: {e}")
                        await status_message.edit_text(f"❌ Upload failed: {str(e)}")
                        
                        if os.path.exists(file_path):
                            os.remove(file_path)
    
    except Exception as e:
        logger.error(f"Process URL error: {e}")
        await status_message.edit_text(f"❌ Error: {str(e)}")

async def upload_progress(current, total, status_message, start_time):
    """Callback function to update upload progress"""
    now = time.time()
    diff = now - start_time
    
    if diff < 3:  # Update progress every 3 seconds
        return
        
    speed = current / diff if diff > 0 else 0
    progress = (current / total) * 100 if total > 0 else 0
    
    await status_message.edit_text(
        f"⬆️ Uploading...\n"
        f"Progress: {progress:.2f}%\n"
        f"Speed: {format_size(speed)}/s\n"
        f"Uploaded: {format_size(current)} / {format_size(total)}"
    )
    
    # Reset start time for next update
    return now

async def split_and_upload_file(client, file_path, user_id, status_message):
    """Split large files and upload them in parts"""
    if not USER_SESSION_STRING:
        await status_message.edit_text("❌ File too large and user session not configured for splitting.")
        return
    
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    # Calculate number of parts
    parts = math.ceil(file_size / SPLIT_SIZE)
    
    await status_message.edit_text(f"📦 File size: {format_size(file_size)}\nSplitting into {parts} parts...")
    
    # Create a directory for the split parts
    split_dir = f"downloads/{user_id}/split"
    os.makedirs(split_dir, exist_ok=True)
    
    # Split the file
    with open(file_path, "rb") as f:
        for i in range(parts):
            part_name = f"{file_name}_part{i+1}of{parts}"
            part_path = os.path.join(split_dir, part_name)
            
            with open(part_path, "wb") as part_file:
                # Read SPLIT_SIZE bytes or the remaining bytes
                bytes_left = file_size - (i * SPLIT_SIZE)
                bytes_to_read = min(SPLIT_SIZE, bytes_left)
                part_file.write(f.read(bytes_to_read))
            
            # Upload the part
            await status_message.edit_text(f"⬆️ Uploading part {i+1} of {parts}...")
            
            try:
                if user:  # Use user session for uploading if available
                    await user.send_document(
                        chat_id=DUMP_CHAT_ID,
                        document=part_path,
                        caption=f"Part {i+1} of {parts}\n{file_name}",
                        progress=upload_progress,
                        progress_args=(status_message, time.time())
                    )
                else:
                    await client.send_document(
                        chat_id=DUMP_CHAT_ID,
                        document=part_path,
                        caption=f"Part {i+1} of {parts}\n{file_name}",
                        progress=upload_progress,
                        progress_args=(status_message, time.time())
                    )
                
                # Clean up the part file
                if os.path.exists(part_path):
                    os.remove(part_path)
                    
            except Exception as e:
                logger.error(f"Upload part error: {e}")
                await status_message.edit_text(f"❌ Failed to upload part {i+1}: {str(e)}")
                return
    
    await status_message.edit_text(f"✅ All {parts} parts uploaded successfully to the dump channel!")
    await client.send_message(
        chat_id=user_id,
        text=f"⚠️ Due to file size limitations, your file was split into {parts} parts and uploaded to our dump channel.\n\nPlease check @{(await client.get_chat(DUMP_CHAT_ID)).username}"
    )

# Command for admins to get bot stats
@app.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
async def stats_command(client, message):
    # Count pending requests
    pending_count = len([req for req_id, req in pending_requests.items() if req.get("status") != "fulfilled"])
    fulfilled_count = len([req for req_id, req in pending_requests.items() if req.get("status") == "fulfilled"])
    
    # Get bot uptime
    bot_uptime = int(time.time() - bot_start_time)
    days, remainder = divmod(bot_uptime, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    stats_text = (
        "📊 **Bot Statistics**\n\n"
        f"⏱ **Uptime:** {days}d {hours}h {minutes}m {seconds}s\n"
        f"🔄 **Pending Requests:** {pending_count}\n"
        f"✅ **Fulfilled Requests:** {fulfilled_count}\n"
        f"💾 **User Session:** {'✅ Active' if USER_SESSION_STRING else '❌ Not configured'}\n"
        f"📦 **Max File Size:** {format_size(SPLIT_SIZE)}"
    )
    
    await message.reply_text(stats_text)

# Command to broadcast messages to all users who made requests
@app.on_message(filters.command("broadcast") & filters.user(ADMIN_IDS))
async def broadcast_command(client, message):
    # Check if there's a message to broadcast
    if len(message.text.split(None, 1)) < 2:
        await message.reply_text("❌ Please provide a message to broadcast.\n\nUsage: `/broadcast Your message here`")
        return
    
    broadcast_text = message.text.split(None, 1)[1]
    
    # Get unique user IDs from pending_requests
    unique_users = set()
    for req_id, req_data in pending_requests.items():
        unique_users.add(req_data["user_id"])
    
    if not unique_users:
        await message.reply_text("❌ No users found to broadcast to.")
        return
    
    # Send confirmation
    confirm_msg = await message.reply_text(
        f"⚠️ You are about to broadcast a message to {len(unique_users)} users.\n\n"
        f"Message preview:\n\n{broadcast_text}\n\n"
        f"Are you sure you want to continue?"
    )
    
    # Add confirmation buttons
    confirm_buttons = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ No", callback_data="broadcast_cancel")
        ]
    ]
    await confirm_msg.edit_reply_markup(InlineKeyboardMarkup(confirm_buttons))
    
    # Store broadcast info for callback
    global broadcast_info
    broadcast_info = {
        "text": broadcast_text,
        "users": list(unique_users),
        "admin_id": message.from_user.id
    }

@app.on_callback_query(filters.regex(r'^broadcast_(confirm|cancel)$'))
async def handle_broadcast_action(client, callback_query):
    global broadcast_info
    
    # Check if broadcast info exists
    if not broadcast_info:
        await callback_query.answer("⚠️ Broadcast info not found.", show_alert=True)
        return
    
    # Check if the user is the admin who initiated the broadcast
    if callback_query.from_user.id != broadcast_info["admin_id"]:
        await callback_query.answer("⚠️ Only the admin who initiated this broadcast can confirm or cancel it.", show_alert=True)
        return
    
    action = callback_query.data.split("_")[1]
    
    if action == "cancel":
        await callback_query.message.edit_text("❌ Broadcast cancelled.")
        broadcast_info = None
        return
    
    # Confirm broadcast
    await callback_query.message.edit_text("🔄 Broadcasting message... Please wait.")
    
    # Track success and failure
    success_count = 0
    failure_count = 0
    
    # Send message to each user
    for user_id in broadcast_info["users"]:
        try:
            await client.send_message(
                chat_id=user_id,
                text=f"📣 **Announcement from Admin**\n\n{broadcast_info['text']}"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user_id}: {e}")
            failure_count += 1
    
    # Update status
    await callback_query.message.edit_text(
        f"✅ Broadcast completed!\n\n"
        f"📊 **Stats:**\n"
        f"- ✅ Successfully sent: {success_count}\n"
        f"- ❌ Failed: {failure_count}"
    )
    
    # Clear broadcast info
    broadcast_info = None

# Initialize Flask app for web server (to keep bot alive)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Start the bot
async def start_bot():
    global bot_start_time
    bot_start_time = time.time()
    
    await app.start()
    if user:
        await user.start()
    
    logger.info("Bot started successfully!")
    await idle()
    
    await app.stop()
    if user:
        await user.stop()

if __name__ == "__main__":
    # Start Flask in a separate thread
    Thread(target=run_flask).start()
    
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    
    # Initialize broadcast info
    broadcast_info = None
    
    # Start the bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_bot())
