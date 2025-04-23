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
            await message.reply_text("❌ Invalid Terabox URL. Please provide a valid Terabox link.")async def process_url(client, message, url, user_id=None, status_message=None):
    target_chat_id = user_id if user_id else message.chat.id
    
    # Check if URL is valid
    if not is_valid_url(url):
        await client.send_message(target_chat_id, "❌ Invalid Terabox URL. Please send a valid Terabox link.")
        return

    # Show processing message if status_message not provided
    status_msg = status_message
    if not status_msg:
        status_msg = await client.send_message(target_chat_id, "⏳ Processing your link... Please wait.")
    
    try:
        # Update status message
        await status_msg.edit_text("🔍 Fetching file details...")
        
        # Make API request
        encoded_url = urllib.parse.quote(url)
        api_url = f"{TERABOX_API_URL}{encoded_url}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=60) as response:
                if response.status != 200:
                    await status_msg.edit_text(f"❌ API Error: {response.status} - {response.reason}")
                    return
                
                data = await response.json()
                
                if data.get("status") != "ok":
                    error_msg = data.get("error", "Unknown error")
                    await status_msg.edit_text(f"❌ Error: {error_msg}")
                    return
                
                file_list = data.get("list", [])
                if not file_list:
                    await status_msg.edit_text("❌ No files found in this link.")
                    return
                
                # Process each file
                for file_index, file_info in enumerate(file_list):
                    file_name = file_info.get("filename", f"file_{file_index}")
                    file_size = int(file_info.get("size", 0))
                    download_url = file_info.get("direct_link")
                    
                    if not download_url:
                        await client.send_message(
                            target_chat_id, 
                            f"❌ Failed to get download link for {file_name}"
                        )
                        continue
                    
                    # Update status
                    await status_msg.edit_text(
                        f"📥 Preparing to download:\n"
                        f"File: {file_name}\n"
                        f"Size: {format_size(file_size)}"
                    )
                    
                    # Check if file size is larger than Telegram's limit
                    if file_size > 2097152000:  # 2GB - Telegram limit for bots
                        if USER_SESSION_STRING and file_size <= SPLIT_SIZE:
                            # Can download with user account
                            await status_msg.edit_text(
                                f"📥 File size: {format_size(file_size)}\n"
                                f"Using user account to send larger file..."
                            )
                            await download_and_send_with_user(
                                user, file_name, download_url, target_chat_id, 
                                file_size, status_msg
                            )
                        else:
                            # Need to split the file
                            await status_msg.edit_text(
                                f"📥 File size: {format_size(file_size)}\n"
                                f"File is too large, splitting into parts..."
                            )
                            await split_and_download(
                                client, download_url, file_name, target_chat_id, 
                                file_size, status_msg
                            )
                    else:
                        # Regular download and send
                        await download_and_send(
                            client, download_url, file_name, target_chat_id, 
                            file_size, status_msg
                        )
        
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}")
        try:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
        except:
            await client.send_message(target_chat_id, f"❌ Error: {str(e)}")

async def download_and_send(client, download_url, file_name, chat_id, file_size, status_msg):
    try:
        temp_dir = f"downloads/{chat_id}"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file_name)
        
        async with aiohttp.ClientSession() as session:
            # Download the file
            success = await direct_download(download_url, file_path, session, status_msg)
            if not success:
                await status_msg.edit_text("❌ Download failed. Please try again later.")
                return
            
            # Update status
            await status_msg.edit_text(f"✅ Download completed! Sending to Telegram...")
            
            # Determine file type and send accordingly
            file_ext = os.path.splitext(file_name)[1].lower()
            
            try:
                # Send file based on extension
                if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm']:
                    # Send as video
                    await client.send_video(
                        chat_id=chat_id,
                        video=file_path,
                        caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}",
                        progress=progress_callback,
                        progress_args=(status_msg, "Uploading", file_name)
                    )
                elif file_ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
                    # Send as audio
                    await client.send_audio(
                        chat_id=chat_id,
                        audio=file_path,
                        caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}",
                        progress=progress_callback,
                        progress_args=(status_msg, "Uploading", file_name)
                    )
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    # Send as photo
                    await client.send_photo(
                        chat_id=chat_id,
                        photo=file_path,
                        caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}"
                    )
                else:
                    # Send as document
                    await client.send_document(
                        chat_id=chat_id,
                        document=file_path,
                        caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}",
                        progress=progress_callback,
                        progress_args=(status_msg, "Uploading", file_name)
                    )
                
                await status_msg.edit_text("✅ File sent successfully!")
                
            except FloodWait as e:
                await status_msg.edit_text(f"⚠️ Telegram FloodWait: Waiting for {e.value} seconds")
                await asyncio.sleep(e.value)
                await status_msg.edit_text("⏳ Retrying upload...")
                await client.send_document(
                    chat_id=chat_id,
                    document=file_path,
                    caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}"
                )
                await status_msg.edit_text("✅ File sent successfully!")
                
            except Exception as e:
                logger.error(f"Error sending file: {e}")
                await status_msg.edit_text(f"❌ Failed to send file: {str(e)}")
                
            finally:
                # Clean up downloaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
    except Exception as e:
        logger.error(f"Error in download_and_send: {str(e)}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def download_and_send_with_user(user_client, file_name, download_url, chat_id, file_size, status_msg):
    try:
        temp_dir = f"downloads/{chat_id}"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file_name)
        
        async with aiohttp.ClientSession() as session:
            # Download the file
            await status_msg.edit_text("⬇️ Downloading large file using user account...")
            success = await direct_download(download_url, file_path, session, status_msg)
            if not success:
                await status_msg.edit_text("❌ Download failed. Please try again later.")
                return
            
            # Update status
            await status_msg.edit_text(f"✅ Download completed! Sending to Telegram...")
            
            # Send file using user account
            file_ext = os.path.splitext(file_name)[1].lower()
            
            try:
                # Send to dump channel first
                if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm']:
                    # Send as video
                    dump_msg = await user_client.send_video(
                        chat_id=DUMP_CHAT_ID,
                        video=file_path,
                        caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}",
                        progress=progress_callback,
                        progress_args=(status_msg, "Uploading to Dump Channel", file_name)
                    )
                    # Forward to user
                    await dump_msg.forward(chat_id)
                else:
                    # Send as document
                    dump_msg = await user_client.send_document(
                        chat_id=DUMP_CHAT_ID,
                        document=file_path,
                        caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}",
                        progress=progress_callback,
                        progress_args=(status_msg, "Uploading to Dump Channel", file_name)
                    )
                    # Forward to user
                    await dump_msg.forward(chat_id)
                
                await status_msg.edit_text("✅ File sent successfully!")
                
            except FloodWait as e:
                await status_msg.edit_text(f"⚠️ Telegram FloodWait: Waiting for {e.value} seconds")
                await asyncio.sleep(e.value)
                await status_msg.edit_text("⏳ Retrying upload...")
                await user_client.send_document(
                    chat_id=DUMP_CHAT_ID,
                    document=file_path,
                    caption=f"📂 Filename: {file_name}\n💾 Size: {format_size(file_size)}"
                )
                await status_msg.edit_text("✅ File sent successfully!")
                
            except Exception as e:
                logger.error(f"Error sending file with user: {e}")
                await status_msg.edit_text(f"❌ Failed to send file: {str(e)}")
                
            finally:
                # Clean up downloaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
    except Exception as e:
        logger.error(f"Error in download_and_send_with_user: {str(e)}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def split_and_download(client, download_url, file_name, chat_id, file_size, status_msg):
    try:
        temp_dir = f"downloads/{chat_id}/split_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Calculate number of parts
        part_size = 2000 * 1024 * 1024  # ~2GB chunks
        total_parts = math.ceil(file_size / part_size)
        
        await status_msg.edit_text(f"File will be split into {total_parts} parts")
        
        file_parts = []
        
        async with aiohttp.ClientSession() as session:
            for part_num in range(total_parts):
                start_byte = part_num * part_size
                end_byte = min((part_num + 1) * part_size - 1, file_size - 1)
                
                part_file = f"{file_name}.part{part_num+1:03d}"
                part_path = os.path.join(temp_dir, part_file)
                
                await status_msg.edit_text(
                    f"⬇️ Downloading part {part_num+1}/{total_parts}\n"
                    f"Range: {format_size(start_byte)} - {format_size(end_byte)}"
                )
                
                # Add range header for partial download
                headers = {"Range": f"bytes={start_byte}-{end_byte}"}
                
                try:
                    # Download part
                    async with session.get(download_url, headers=headers) as response:
                        with open(part_path, 'wb') as f:
                            # Download with progress tracking
                            total_downloaded = 0
                            part_size = end_byte - start_byte + 1
                            last_update_time = time.time()
                            
                            async for chunk in response.content.iter_chunked(1024*1024):  # 1MB chunks
                                if chunk:
                                    f.write(chunk)
                                    total_downloaded += len(chunk)
                                    
                                    # Update progress every 3 seconds
                                    current_time = time.time()
                                    if current_time - last_update_time >= 3:
                                        progress = (total_downloaded / part_size) * 100
                                        await status_msg.edit_text(
                                            f"⬇️ Downloading part {part_num+1}/{total_parts}\n"
                                            f"Progress: {progress:.2f}%\n"
                                            f"Downloaded: {format_size(total_downloaded)} / {format_size(part_size)}"
                                        )
                                        last_update_time = current_time
                    
                    file_parts.append(part_path)
                    
                    # Update message
                    await status_msg.edit_text(
                        f"✅ Part {part_num+1}/{total_parts} downloaded.\n"
                        f"Sending to Telegram..."
                    )
                    
                    # Send part
                    await client.send_document(
                        chat_id=chat_id,
                        document=part_path,
                        caption=f"📂 {file_name} - Part {part_num+1}/{total_parts}\n"
                               f"💾 Size: {format_size(os.path.getsize(part_path))}",
                        progress=progress_callback,
                        progress_args=(status_msg, f"Uploading Part {part_num+1}", part_file)
                    )
                    
                except Exception as e:
                    logger.error(f"Error downloading part {part_num+1}: {e}")
                    await status_msg.edit_text(f"❌ Error downloading part {part_num+1}: {str(e)}")
                    return
        
        # All parts sent successfully
        await status_msg.edit_text(
            f"✅ All {total_parts} parts have been sent successfully.\n\n"
            f"To rejoin the parts on your computer, use:\n"
            f"- Windows: copy /b file.part* combinedfile\n"
            f"- Linux/Mac: cat file.part* > combinedfile"
        )
        
        # Clean up
        for part in file_parts:
            if os.path.exists(part):
                os.remove(part)
        
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
            
    except Exception as e:
        logger.error(f"Error in split_and_download: {str(e)}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def progress_callback(current, total, status_msg, action, filename):
    try:
        if total:
            percent = current * 100 / total
            progress_bar = "▓" * int(percent/5) + "░" * (20 - int(percent/5))
            
            # Calculate speed and ETA
            elapsed_time = time.time() - progress_callback.start_time
            speed = current / elapsed_time if elapsed_time > 0 else 0
            eta = (total - current) / speed if speed > 0 else 0
            
            # Format ETA
            eta_mins = int(eta // 60)
            eta_secs = int(eta % 60)
            
            await status_msg.edit_text(
                f"**{action}:** `{filename}`\n\n"
                f"**Progress:** {current}/{total} ({percent:.1f}%)\n"
                f"[{progress_bar}]\n"
                f"**Speed:** {format_size(speed)}/s\n"
                f"**ETA:** {eta_mins}m {eta_secs}s"
            )
    except Exception as e:
        # Don't crash on progress update errors
        logger.error(f"Progress callback error: {str(e)}")

# Initialize progress_callback.start_time
progress_callback.start_time = time.time()

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
    
    if is_valid_url(url):
        await process_url(client, message, url)
    else:
        await message.reply_text(
            "❌ Invalid URL! Please send a valid Terabox link.\n\n"
            "Supported domains: terabox.com, nephobox.com, 4funbox.com, mirrobox.com, "
            "momerybox.com, teraboxapp.com, 1024tera.com, terabox.app, gibibox.com, "
            "goaibox.com, terasharelink.com, teraboxlink.com, terafileshare.com"
        )

# Flask server to keep the bot alive on hosting platforms
app_server = Flask(__name__)

@app_server.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app_server.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Commands for admin use
@app.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
async def stats_command(client, message):
    # Get bot statistics
    try:
        # Count number of pending requests
        pending_count = len(pending_requests)
        
        # Get bot uptime
        uptime = time.time() - bot_start_time
        days = int(uptime // (24 * 3600))
        uptime %= (24 * 3600)
        hours = int(uptime // 3600)
        uptime %= 3600
        minutes = int(uptime // 60)
        
        # System stats
        import psutil
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        stats_text = (
            "📊 **Bot Statistics**\n\n"
            f"**Uptime:** {days}d {hours}h {minutes}m\n"
            f"**Pending Requests:** {pending_count}\n"
            f"**CPU Usage:** {cpu_usage}%\n"
            f"**RAM Usage:** {ram_usage}%\n"
            f"**Disk Usage:** {disk_usage}%\n"
        )
        
        await message.reply_text(stats_text)
    except Exception as e:
        await message.reply_text(f"Error getting statistics: {str(e)}")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_IDS))
async def broadcast_command(client, message):
    # Broadcast message to all users who have pending requests
    if len(message.text.split(" ", 1)) < 2:
        await message.reply_text("Usage: /broadcast <message>")
        return
        
    broadcast_text = message.text.split(" ", 1)[1]
    
    if not broadcast_text:
        await message.reply_text("Please provide a message to broadcast.")
        return
        
    # Get unique user IDs from pending requests
    unique_users = set(req["user_id"] for req in pending_requests.values())
    
    success_count = 0
    fail_count = 0
    
    progress_msg = await message.reply_text("Broadcasting message...")
    
    for user_id in unique_users:
        try:
            await client.send_message(
                chat_id=user_id,
                text=f"📢 **Broadcast Message from Admin**\n\n{broadcast_text}"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            fail_count += 1
    
    await progress_msg.edit_text(
        f"✅ Broadcast completed!\n\n"
        f"Successfully sent: {success_count}\n"
        f"Failed: {fail_count}"
    )

# Record bot start time for uptime tracking
bot_start_time = time.time()

async def main():
    await app.start()
    if user:
        await user.start()
    logger.info("Bot started successfully!")
    
    # Keep the bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run the bot
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped!")
