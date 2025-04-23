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
            await message.reply_text("❌ Invalid Terabox URL. Please provide a valid Terabox link.")
            
@app.on_message(filters.text & filters.private & ~filters.command)
async def handle_url(client, message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)
    
    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/dailydiskwala")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return
        
    url = message.text.strip()
    if is_valid_url(url):
        status_message = await message.reply_text("⏳ Processing your Terabox link...")
        await process_url(client, message, url, status_message=status_message)
    else:
        await message.reply_text("❌ Invalid URL. Please send a valid Terabox link.")

async def process_url(client, message, url, user_id=None, status_message=None):
    target_user_id = user_id if user_id else message.from_user.id
    
    try:
        # Update status message
        if status_message:
            await status_message.edit_text("🔄 Fetching file information...")
        
        # Encode URL for API
        encoded_url = urllib.parse.quote(url)
        api_url = f"{TERABOX_API_URL}{encoded_url}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url, timeout=60) as response:
                    if response.status != 200:
                        if status_message:
                            await status_message.edit_text(f"❌ API Error: HTTP {response.status}")
                        return
                        
                    response_data = await response.json()
                    
                    if not response_data.get("ok", False):
                        error_msg = response_data.get("msg", "Unknown error")
                        if status_message:
                            await status_message.edit_text(f"❌ API Error: {error_msg}")
                        return
                    
                    file_info = response_data.get("data", {})
                    file_name = file_info.get("filename", "unknown_file")
                    file_size = int(file_info.get("size", 0))
                    direct_link = file_info.get("dlink", "")
                    
                    if not direct_link:
                        if status_message:
                            await status_message.edit_text("❌ Failed to get direct download link")
                        return
                    
                    # Update status message with file info
                    if status_message:
                        await status_message.edit_text(
                            f"📦 **File Information:**\n\n"
                            f"**Name:** {file_name}\n"
                            f"**Size:** {format_size(file_size)}\n\n"
                            f"⬇️ Starting download..."
                        )
                    
                    # Check if file size is larger than limit and user session is not available
                    if file_size > SPLIT_SIZE and not user:
                        if status_message:
                            await status_message.edit_text(
                                f"❌ **File too large for me to handle!**\n\n"
                                f"**File Size:** {format_size(file_size)}\n"
                                f"**Maximum Size:** {format_size(SPLIT_SIZE)}\n\n"
                                f"Try smaller files."
                            )
                        return
                    
                    temp_dir = f"downloads/{target_user_id}/"
                    os.makedirs(temp_dir, exist_ok=True)
                    file_path = os.path.join(temp_dir, file_name)
                    
                    # Download the file
                    download_success = await direct_download(direct_link, file_path, session, status_message)
                    
                    if not download_success:
                        if status_message:
                            await status_message.edit_text("❌ Download failed. Please try again later.")
                        return
                    
                    # Update status message
                    if status_message:
                        await status_message.edit_text("✅ Download completed. Uploading to Telegram...")
                    
                    # Send the file to user
                    await send_file(client, target_user_id, file_path, status_message)
                    
                    # Clean up
                    try:
                        os.remove(file_path)
                    except:
                        pass
                        
            except aiohttp.ClientError as e:
                if status_message:
                    await status_message.edit_text(f"❌ Connection Error: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        if status_message:
            await status_message.edit_text(f"❌ An error occurred: {str(e)}")

async def send_file(client, user_id, file_path, status_message=None):
    try:
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # Check file extension for type
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Update status if needed
        if status_message:
            await status_message.edit_text(f"📤 Uploading: {file_name}\nSize: {format_size(file_size)}")
        
        # Check file size and split if necessary
        if file_size > SPLIT_SIZE:
            if user:
                # Use user session for larger files
                try:
                    # Update status
                    if status_message:
                        await status_message.edit_text(f"📤 File is large. Uploading with premium session...")
                    
                    # Send as document using user session
                    async with user:
                        sent_message = await user.send_document(
                            chat_id=user_id,
                            document=file_path,
                            caption=f"📁 **{file_name}**\n\n🔷 Size: {format_size(file_size)}\n\n✅ Powered by @dailydiskwala"
                        )
                        
                    if status_message:
                        await status_message.edit_text("✅ File uploaded successfully!")
                        
                except Exception as e:
                    logger.error(f"Error in user session upload: {e}")
                    if status_message:
                        await status_message.edit_text(f"❌ Failed to upload with premium session: {str(e)}")
                    
            else:
                # Split the file
                if status_message:
                    await status_message.edit_text(f"📂 File is too large. Splitting into parts...")
                
                # Split logic would be implemented here
                # This is a placeholder since implementing file splitting would require additional code
                await status_message.edit_text("❌ File is too large and splitting is not implemented yet.")
                return
        else:
            # File is within size limit, send directly
            if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm']:
                await client.send_video(
                    chat_id=user_id,
                    video=file_path,
                    caption=f"🎬 **{file_name}**\n\n🔷 Size: {format_size(file_size)}\n\n✅ Powered by @dailydiskwala"
                )
            elif file_ext in ['.mp3', '.wav', '.ogg', '.m4a']:
                await client.send_audio(
                    chat_id=user_id,
                    audio=file_path,
                    caption=f"🎵 **{file_name}**\n\n🔷 Size: {format_size(file_size)}\n\n✅ Powered by @dailydiskwala"
                )
            else:
                await client.send_document(
                    chat_id=user_id,
                    document=file_path,
                    caption=f"📁 **{file_name}**\n\n🔷 Size: {format_size(file_size)}\n\n✅ Powered by @dailydiskwala"
                )
                
            if status_message:
                await status_message.edit_text("✅ File uploaded successfully!")
                
    except FloodWait as e:
        if status_message:
            await status_message.edit_text(f"⚠️ Telegram FloodWait: Waiting for {e.value} seconds")
        await asyncio.sleep(e.value)
        # Retry sending
        return await send_file(client, user_id, file_path, status_message)
        
    except Exception as e:
        logger.error(f"Error sending file: {e}")
        if status_message:
            await status_message.edit_text(f"❌ Failed to upload: {str(e)}")
        raise

@app.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
async def stats_command(client, message):
    # Get bot statistics
    try:
        total_requests = len(pending_requests)
        approved_requests = sum(1 for req in pending_requests.values() if req.get("status") == "approved")
        fulfilled_requests = sum(1 for req in pending_requests.values() if req.get("status") == "fulfilled")
        rejected_requests = sum(1 for req in pending_requests.values() if req.get("status") == "rejected")
        
        await message.reply_text(
            f"📊 **Bot Statistics**\n\n"
            f"**Total Requests:** {total_requests}\n"
            f"**Approved:** {approved_requests}\n"
            f"**Fulfilled:** {fulfilled_requests}\n"
            f"**Rejected:** {rejected_requests}\n"
        )
    except Exception as e:
        await message.reply_text(f"❌ Error generating stats: {str(e)}")

@app.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = (
        "🔍 **ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛᴇʀᴀʙᴏx ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ!**\n\n"
        "📌 **ʜᴏᴡ ᴛᴏ ᴜsᴇ:**\n"
        "• Sᴇɴᴅ ᴀɴʏ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ᴅɪʀᴇᴄᴛʟʏ\n"
        "• Usᴇ /request ᴡɪᴛʜ ᴀ ᴘʜᴏᴛᴏ & ᴅᴇsᴄʀɪᴘᴛɪᴏɴ ᴛᴏ ʀᴇǫᴜᴇsᴛ ᴀ ғɪʟᴇ\n\n"
        "📜 **ᴄᴏᴍᴍᴀɴᴅs:**\n"
        "• /start - Sᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ\n"
        "• /help - Sʜᴏᴡ ᴛʜɪs ʜᴇʟᴘ ᴍᴇssᴀɢᴇ\n"
        "• /request - Rᴇǫᴜᴇsᴛ ᴀ ᴠɪᴅᴇᴏ\n\n"
        "⭐ Jᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ: @dailydiskwala"
    )
    
    await message.reply_text(help_text)

def start_flask():
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "Bot is running!"
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def main():
    print(f"Bot is Starting...")
    
    # Start Flask server in a separate thread
    flask_thread = Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start the Pyrogram client
    app.start()
    
    if user:
        user.start()
        print("User session started")
    
    # Log successful startup
    print(f"Bot Started Successfully!")
    
    # Keep the main thread alive
    idle()
    
    # Stop the clients when the script is terminated
    app.stop()
    if user:
        user.stop()

if __name__ == "__main__":
    main()
