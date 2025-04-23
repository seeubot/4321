from aria2p import API as Aria2API, Client as Aria2Client
import asyncio
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
import math
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
import time
import urllib.parse
import re
from urllib.parse import urlparse
from flask import Flask, render_template
from threading import Thread
import requests
import json
import random
import string
import magic  # Make sure to install python-magic

load_dotenv('config.env', override=True)
logging.basicConfig(
    level=logging.INFO,  
    format="[%(asctime)s - %(name)s - %(levelname)s] %(message)s - %(filename)s:%(lineno)d"
)

logger = logging.getLogger(__name__)

# Reduce logging for pyrogram components
for module in ["pyrogram.session", "pyrogram.connection", "pyrogram.dispatcher"]:
    logging.getLogger(module).setLevel(logging.ERROR)

# Set up aria2 client with optimized settings
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
    "split": "16",  # Increased for better parallelism
    "max-concurrent-downloads": "10",  # Added for better concurrency
    "disk-cache": "64M"  # Added for better performance
}

aria2.set_global_options(options)

# Environment variable checks
required_vars = {
    'TELEGRAM_API': 'API_ID',
    'TELEGRAM_HASH': 'API_HASH',
    'BOT_TOKEN': 'BOT_TOKEN',
    'DUMP_CHAT_ID': 'DUMP_CHAT_ID',
    'FSUB_ID': 'FSUB_ID'
}

# Check for required environment variables
for env_var, var_name in required_vars.items():
    value = os.environ.get(env_var, '')
    if len(value) == 0:
        logging.error(f"{var_name} variable is missing! Exiting now")
        exit(1)
    
    # Convert IDs to int
    if 'ID' in var_name and value:
        globals()[var_name] = int(value)
    else:
        globals()[var_name] = value

# Optional environment variables
REQUEST_CHAT_ID = os.environ.get('REQUEST_CHAT_ID', '')
if len(REQUEST_CHAT_ID) == 0:
    logging.warning("REQUEST_CHAT_ID variable is missing! Video request feature will be disabled")
    REQUEST_CHAT_ID = None
else:
    REQUEST_CHAT_ID = int(REQUEST_CHAT_ID)

USER_SESSION_STRING = os.environ.get('USER_SESSION_STRING', '')
if len(USER_SESSION_STRING) == 0:
    logging.info("USER_SESSION_STRING variable is missing! Bot will split Files in 2Gb...")
    USER_SESSION_STRING = None

# Thumbnail directory
THUMBNAIL_DIR = "thumbnails"
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# Create clients
app = Client("jetbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user = None
SPLIT_SIZE = 2093796556  # Default 2GB split size
if USER_SESSION_STRING:
    user = Client("jetu", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION_STRING)
    SPLIT_SIZE = 4241280205  # ~4GB for user account

# Constants
VALID_DOMAINS = [
    'terabox.com', 'nephobox.com', '4funbox.com', 'mirrobox.com', 
    'momerybox.com', 'teraboxapp.com', '1024tera.com', 
    'terabox.app', 'gibibox.com', 'goaibox.com', 'terasharelink.com', 
    'teraboxlink.com', 'terafileshare.com'
]
UPDATE_INTERVAL = 10  # Reduced update interval for faster responsiveness
PROGRESS_BAR_LENGTH = 20  # Progress bar segments

# Cache
user_thumbnails = {}
domain_cache = {domain: True for domain in VALID_DOMAINS}  # Pre-populate domain cache

# Helper functions
def is_valid_url(url):
    """Check if URL is from a valid Terabox domain (optimized)"""
    parsed_url = urlparse(url)
    netloc = parsed_url.netloc
    
    # Direct cache lookup first
    if netloc in domain_cache:
        return domain_cache[netloc]
    
    # Check domain endings
    for domain in VALID_DOMAINS:
        if netloc.endswith(domain):
            domain_cache[netloc] = True
            return True
    
    domain_cache[netloc] = False
    return False

def format_size(size):
    """Format file size with units"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def format_speed(speed):
    """Format speed with units"""
    if speed == 0:
        return "0 B/s"
    
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if speed < 1024:
            return f"{speed:.2f} {unit}"
        speed /= 1024
    return f"{speed:.2f} TB/s"

def create_progress_bar(percentage):
    """Create a digital progress bar [0-100%]"""
    filled_length = int(percentage / (100 / PROGRESS_BAR_LENGTH))
    empty_length = PROGRESS_BAR_LENGTH - filled_length
    
    # Using block characters for a more digital look
    bar = '█' * filled_length + '░' * empty_length
    return f"[{bar}] {percentage:.1f}%"

# Function to get direct download link from API
async def get_direct_link(terabox_url):
    encoded_url = urllib.parse.quote(terabox_url)
    api_url = f"https://teraboxapi-phi.vercel.app/api?url={encoded_url}"
    
    try:
        # Use asyncio.to_thread for non-blocking HTTP request
        response = await asyncio.to_thread(lambda: requests.get(api_url, timeout=30))
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") != "success":
            return None, "API returned error status"
        
        extracted_info = data.get("Extracted Info", [])
        if not extracted_info or not isinstance(extracted_info, list) or len(extracted_info) == 0:
            return None, "No valid extracted info found in API response"
        
        direct_link = extracted_info[0].get("Direct Download Link")
        if not direct_link:
            return None, "No direct download link found in API response"
        
        file_name = extracted_info[0].get("Title", "terabox_file")
        file_size = extracted_info[0].get("Size", "Unknown")
        
        return direct_link, {"title": file_name, "size": file_size}
    
    except requests.exceptions.RequestException as e:
        return None, f"Error fetching API: {str(e)}"
    except json.JSONDecodeError as e:
        return None, f"Error parsing API response: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

# Save thumbnail function
async def save_thumbnail(client, message):
    user_id = message.from_user.id
    
    if not message.photo and not message.document:
        await message.reply_text("Please send an image as thumbnail.")
        return False
    
    try:
        if message.photo:
            # If it's a photo, download it
            file_path = f"{THUMBNAIL_DIR}/{user_id}.jpg"
            await client.download_media(message, file_path)
        else:
            # If it's a document, check if it's an image
            if message.document.mime_type and "image" in message.document.mime_type:
                file_path = f"{THUMBNAIL_DIR}/{user_id}.jpg"
                await client.download_media(message, file_path)
            else:
                await message.reply_text("Please send a valid image file as thumbnail.")
                return False
        
        # Store the path in the dictionary
        user_thumbnails[user_id] = file_path
        return True
    
    except Exception as e:
        logger.error(f"Error saving thumbnail: {e}")
        await message.reply_text("Failed to save thumbnail.")
        return False

# Throttled status update function
_last_update_time = {}
async def update_status_message(message, text, force=False):
    message_id = f"{message.chat.id}:{message.id}"
    current_time = time.time()
    
    # Update only if forced or enough time has passed since last update
    if force or message_id not in _last_update_time or current_time - _last_update_time[message_id] >= UPDATE_INTERVAL:
        try:
            await message.edit_text(text)
            _last_update_time[message_id] = current_time
        except FloodWait as e:
            logger.warning(f"FloodWait: Sleeping for {e.value}s")
            await asyncio.sleep(e.value)
            await update_status_message(message, text, force=True)
        except Exception as e:
            logger.error(f"Failed to update status message: {e}")

# Membership check with caching
_member_cache = {}
_member_cache_time = {}
MEMBER_CACHE_TTL = 600  # 10 minutes
async def is_user_member(client, user_id):
    current_time = time.time()
    cache_key = f"{user_id}:{FSUB_ID}"
    
    # Return cached result if available and not expired
    if cache_key in _member_cache and current_time - _member_cache_time[cache_key] < MEMBER_CACHE_TTL:
        return _member_cache[cache_key]
    
    try:
        member = await client.get_chat_member(FSUB_ID, user_id)
        is_member = member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        
        # Cache the result
        _member_cache[cache_key] = is_member
        _member_cache_time[cache_key] = current_time
        
        return is_member
    except Exception as e:
        logger.error(f"Error checking membership status for user {user_id}: {e}")
        return False

# Command handlers
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/terao2")
    developer_button = InlineKeyboardButton("Channel", url="https://t.me/dailydiskwala")
    repo69 = InlineKeyboardButton("Desi18+", url="https://t.me/dailydiskwala")
    user_mention = message.from_user.mention
    reply_markup = InlineKeyboardMarkup([[join_button, developer_button], [repo69]])
    final_msg = f"ᴡᴇʟᴄᴏᴍᴇ, {user_mention}.\n\n🌟 ɪ ᴀᴍ ᴀ ᴛᴇʀᴀʙᴏx ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ. sᴇɴᴅ ᴍᴇ ᴀɴʏ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ɪ ᴡɪʟʟ ᴅᴏᴡɴʟᴏᴀᴅ ᴡɪᴛʜɪɴ ғᴇᴡ sᴇᴄᴏɴᴅs ᴀɴᴅ sᴇɴᴅ ɪᴛ ᴛᴏ ʏᴏᴜ ✨.\n\n📱 Commands:\n/thumb - Set a thumbnail for your uploads\n/delthumb - Delete your current thumbnail\n/request - Request videos with image preview"
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

# Thumbnail command
@app.on_message(filters.command("thumb"))
async def thumb_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/terao2")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return
    
    if message.reply_to_message:
        if await save_thumbnail(client, message.reply_to_message):
            await message.reply_text("✅ Thumbnail saved successfully. It will be used for all your uploads.")
        return
    
    await message.reply_text("Please reply to an image with /thumb to set it as your thumbnail.")

# Delete thumbnail command
@app.on_message(filters.command("delthumb"))
async def delete_thumb_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/terao2")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return
    
    if user_id in user_thumbnails:
        try:
            thumbnail_path = user_thumbnails[user_id]
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            del user_thumbnails[user_id]
            await message.reply_text("✅ Thumbnail deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting thumbnail: {e}")
            await message.reply_text("❌ Failed to delete thumbnail.")
    else:
        await message.reply_text("You don't have any saved thumbnail.")

# Video request command
@app.on_message(filters.command("request"))
async def request_command(client: Client, message: Message):
    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/terao2")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return
    
    if not REQUEST_CHAT_ID:
        await message.reply_text("❌ Video request feature is currently disabled.")
        return
    
    # Check if command has arguments or is replying to a message
    request_text = ""
    has_media = False
    
    if message.reply_to_message:
        # Get text from reply if available
        if message.reply_to_message.text:
            request_text = message.reply_to_message.text
        elif message.reply_to_message.caption:
            request_text = message.reply_to_message.caption
            
        # Check if reply has media
        has_media = (
            message.reply_to_message.photo or 
            message.reply_to_message.document or 
            message.reply_to_message.video or 
            message.reply_to_message.animation
        )
        
        if not has_media and not request_text:
            await message.reply_text("❌ Please reply to a message with media or text describing the video you want to request.")
            return
    else:
        # Get text from command
        command_parts = message.text.split(" ", 1)
        if len(command_parts) > 1:
            request_text = command_parts[1].strip()
        else:
            await message.reply_text(
                "📽️ **How to Request Videos:**\n\n"
                "1️⃣ Send a photo/screenshot of the video you want\n"
                "2️⃣ Reply to it with `/request <video name or description>`\n\n"
                "OR\n\n"
                "• Simply type `/request <detailed video description>`\n\n"
                "Your request will be forwarded to our team!"
            )
            return
    
    # Generate a random request ID
    request_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    # Format caption for forwarding
    forward_caption = (
        f"📝 **New Video Request** #{request_id}\n\n"
        f"👤 Requested by: {message.from_user.mention} (ID: `{user_id}`)\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    
    if request_text:
        forward_caption += f"🎬 **Request Details:**\n{request_text}\n\n"
    
    forward_caption += "📨 Reply to this message to contact the requester."
    
    try:
        # If replying to a message with media
        if message.reply_to_message and has_media:
            if message.reply_to_message.photo:
                sent = await client.send_photo(
                    chat_id=REQUEST_CHAT_ID,
                    photo=message.reply_to_message.photo.file_id,
                    caption=forward_caption
                )
            elif message.reply_to_message.document:
                sent = await client.send_document(
                    chat_id=REQUEST_CHAT_ID,
                    document=message.reply_to_message.document.file_id,
                    caption=forward_caption
                )
            elif message.reply_to_message.video:
                sent = await client.send_video(
                    chat_id=REQUEST_CHAT_ID,
                    video=message.reply_to_message.video.file_id,
                    caption=forward_caption
                )
            elif message.reply_to_message.animation:
                sent = await client.send_animation(
                    chat_id=REQUEST_CHAT_ID,
                    animation=message.reply_to_message.animation.file_id,
                    caption=forward_caption
                )
        else:
            # Text-only request
            sent = await client.send_message(
                chat_id=REQUEST_CHAT_ID,
                text=forward_caption
            )
        
        await message.reply_text(
            f"✅ Your video request has been submitted successfully!\n"
            f"📌 Request ID: `{request_id}`\n\n"
            f"Our team will process your request soon."
        )
    except Exception as e:
        logger.error(f"Failed to forward request: {e}")
        await message.reply_text("❌ Failed to submit your request. Please try again later.")

# Main message handler - optimized to handle Terabox links
@app.on_message(filters.text & ~filters.command(["start", "thumb", "delthumb", "request"]))
async def handle_message(client: Client, message: Message):
    if not message.from_user:
        return

    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/terao2")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return
    
    # Efficiently check for valid Terabox URLs
    url = None
    for word in message.text.split():
        if is_valid_url(word):
            url = word
            break

    if not url:
        await message.reply_text("Please provide a valid Terabox link.")
        return

    status_message = await message.reply_text("𝑷𝒓𝒐𝒄𝒆𝒔𝒔𝒊𝒏𝒈 𝒍𝒊𝒏𝒌 𝒂𝒏𝒅 𝒆𝒙𝒕𝒓𝒂𝒄𝒕𝒊𝒏𝒈 𝒅𝒊𝒓𝒆𝒄𝒕 𝒅𝒐𝒘𝒏𝒍𝒐𝒂𝒅 𝑼𝑹𝑳...")
    
    # Get direct download link from API
    direct_link, info = await get_direct_link(url)
    
    if not direct_link:
        await status_message.edit_text(f"Failed to extract direct download link: {info}")
        return
    
    await status_message.edit_text("sᴇɴᴅɪɴɢ ʏᴏᴜ ᴛʜᴇ ᴍᴇᴅɪᴀ...🤤")
    
    # Add the direct link to aria2 for download with improved options
    download_options = {
        "out": info.get("title", "download") if isinstance(info, dict) else "download",
        "max-connection-per-server": "16",  # Increased for speed
        "split": "16"  # Increased for better parallelism
    }
    download = aria2.add_uris([direct_link], options=download_options)
    
    start_time = datetime.now()
    last_progress = -1

    # Improved download monitoring loop
    while not download.is_complete:
        await asyncio.sleep(3)  # Faster checks but less frequently update UI
        download.update()
        progress = download.progress
        
        # Only update UI when progress changes significantly or time passes
        if abs(progress - last_progress) > 1 or (datetime.now() - start_time).seconds % UPDATE_INTERVAL == 0:
            elapsed_time = datetime.now() - start_time
            elapsed_minutes, elapsed_seconds = divmod(elapsed_time.seconds, 60)

            status_text = (
                f"┏ ғɪʟᴇɴᴀᴍᴇ: {download.name}\n"
                f"┠ {create_progress_bar(progress)}\n"
                f"┠ ᴘʀᴏᴄᴇssᴇᴅ: {format_size(download.completed_length)} ᴏғ {format_size(download.total_length)}\n"
                f"┠ sᴛᴀᴛᴜs: 📥 Downloading\n"
                f"┠ ᴇɴɢɪɴᴇ: <b><u>Aria2c v1.37.0</u></b>\n"
                f"┠ sᴘᴇᴇᴅ: {format_speed(download.download_speed)}\n"
                f"┠ ᴇʟᴀᴘsᴇᴅ: {elapsed_minutes}m {elapsed_seconds}s\n"
                f"┖ ᴜsᴇʀ: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> | ɪᴅ: {user_id}\n"
            )
            await update_status_message(status_message, status_text)
            last_progress = progress

    file_path = download.files[0].path
    caption = (
        f"✨ {download.name}\n"
        f"👤 ʟᴇᴇᴄʜᴇᴅ ʙʏ : <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>\n"
        f"📥 ᴜsᴇʀ ʟɪɴᴋ: tg://user?id={user_id}\n\n"
        "[TELUGU STUFF](https://t.me/dailydiskwala)"
    )

    # Reset start time for upload process
    start_time = datetime.now()

    # Upload progress callback
    async def upload_progress(current, total):
        nonlocal start_time
        progress = (current / total) * 100
        elapsed_time = datetime.now() - start_time
        elapsed_minutes, elapsed_seconds = divmod(elapsed_time.seconds, 60)
        
        # Calculate upload speed
        upload_speed = current / max(elapsed_time.seconds, 1)

        status_text = (
            f"┏ ғɪʟᴇɴᴀᴍᴇ: {download.name}\n"
            f"┠ {create_progress_bar(progress)}\n"
            f"┠ ᴘʀᴏᴄᴇssᴇᴅ: {format_size(current)} ᴏғ {format_size(total)}\n"
            f"┠ sᴛᴀᴛᴜs: 📤 Uploading to Telegram\n"
            f"┠ ᴇɴɢɪɴᴇ: <b><u>PyroFork v2.2.11</u></b>\n"
            f"┠ sᴘᴇᴇᴅ: {format_speed(upload_speed)}\n"
            f"┠ ᴇʟᴀᴘsᴇᴅ: {elapsed_minutes}m {elapsed_seconds}s\n"
            f"┖ ᴜsᴇʀ: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a> | ɪᴅ: {user_id}\n"
        )
        await update_status_message(status_message, status_text)

    # Fix the indentation error in run_ffmpeg
    async def run_ffmpeg(cmd, output_path, part_num, total_parts, status_message, start_time):
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await proc.communicate()
            
            if proc.returncode != 0:
                logger.error(f"FFmpeg process failed with return code {proc.returncode}")
                return False
            
            elapsed_time = datetime.now() - start_time
            elapsed_minutes, elapsed_seconds = divmod(elapsed_time.seconds, 60)
            
            status_text = (
                f"📝 Splitting file...\n"
                f"Part {part_num}/{total_parts} processed in {elapsed_minutes}m {elapsed_seconds}s"
            )
            
            await update_status_message(status_message, status_text)
            return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"FFmpeg execution error: {e}")
            return False

    # Optimized video splitting function
    async def split_video_with_ffmpeg(input_path, output_prefix, split_size):
        try:
            original_ext = os.path.splitext(input_path)[1].lower() or '.mp4'
            start_time = datetime.now()
            
            # Get video duration faster with less overhead
            proc = await asyncio.create_subprocess_exec(
                'ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                '-show_entries', 'format=duration', '-of', 
                'default=noprint_wrappers=1:nokey=1', input_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            duration = float(stdout.decode('utf-8').strip())
            
            # Calculate number of segments needed
            file_size = os.path.getsize(input_path)
            total_segments = math.ceil(file_size / split_size)
            segment_duration = duration / total_segments
            
            # Create output paths
            output_files = []
            
            for i in range(total_segments):
                start_time_sec = i * segment_duration
                output_path = f"{output_prefix}_{i + 1}{original_ext}"
                
                # Build FFmpeg command using efficient codec copy
                cmd = [
                    'ffmpeg', '-i', input_path, '-ss', str(start_time_sec),
                    '-t', str(segment_duration), '-c', 'copy', '-avoid_negative_ts', '1',
                    '-reset_timestamps', '1', output_path
                ]
                
                success = await run_ffmpeg(cmd, output_path, i + 1, total_segments, status_message, start_time)
                if success:
                    output_files.append(output_path)
                else:
                    return []
            
            return output_files
        except Exception as e:
            logger.error(f"Error in split_video_with_ffmpeg: {e}")
            return []

    # Get MIME type
    mime_type = magic.from_file(file_path, mime=True)
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    # Check if file needs splitting
    if file_size > SPLIT_SIZE:
        await status_message.edit_text("File size exceeds Telegram limit. Splitting file...")
        
        # Determine how to split based on file type
        if mime_type.startswith('video/'):
            # Split video
            output_prefix = os.path.splitext(file_path)[0]
            split_files = await split_video_with_ffmpeg(file_path, output_prefix, SPLIT_SIZE)
            
            if not split_files:
                await status_message.edit_text("❌ Failed to split video file.")
                return
            
            # Upload each part
            for i, part_file in enumerate(split_files):
                part_caption = f"{caption}\n\nPart {i+1}/{len(split_files)}"
                
                # Check for user thumbnail
                thumbnail = None
                if user_id in user_thumbnails and os.path.exists(user_thumbnails[user_id]):
                    thumbnail = user_thumbnails[user_id]
                
                try:
                    await client.send_video(
                        chat_id=message.chat.id,
                        video=part_file,
                        caption=part_caption,
                        thumb=thumbnail,
                        supports_streaming=True,
                        progress=upload_progress
                    )
                    
                    # Also forward to dump channel if configured
                    if DUMP_CHAT_ID:
                        try:
                            await client.send_video(
                                chat_id=DUMP_CHAT_ID,
                                video=part_file,
                                caption=part_caption,
                                thumb=thumbnail,
                                supports_streaming=True
                            )
                        except Exception as e:
                            logger.error(f"Failed to forward to dump channel: {e}")
                    
                    # Clean up part file
                    os.remove(part_file)
                except Exception as e:
                    logger.error(f"Error uploading part {i+1}: {e}")
                    await message.reply_text(f"❌ Error uploading part {i+1}: {str(e)}")
        else:
            # For non-video files, use simple binary split
            output_prefix = os.path.splitext(file_path)[0]
            split_files = []
            
            with open(file_path, 'rb') as f:
                i = 0
                while True:
                    chunk = f.read(SPLIT_SIZE)
                    if not chunk:
                        break
                    
                    output_path = f"{output_prefix}_{i+1}{os.path.splitext(file_path)[1]}"
                    with open(output_path, 'wb') as chunk_file:
                        chunk_file.write(chunk)
                    
                    split_files.append(output_path)
                    i += 1
            
            # Upload each part
            for i, part_file in enumerate(split_files):
                part_caption = f"{caption}\n\nPart {i+1}/{len(split_files)}"
                
                try:
                    if mime_type.startswith('image/'):
                        await client.send_photo(
                            chat_id=message.chat.id,
                            photo=part_file,
                            caption=part_caption,
                            progress=upload_progress
                        )
                    else:
                        await client.send_document(
                            chat_id=message.chat.id,
                            document=part_file,
                            caption=part_caption,
                            progress=upload_progress
                        )
                    
                    # Also forward to dump channel if configured
                    if DUMP_CHAT_ID:
                        try:
                            if mime_type.startswith('image/'):
                                await client.send_photo(
                                    chat_id=DUMP_CHAT_ID,
                                    photo=part_file,
                                    caption=part_caption
                                )
                            else:
                                await client.send_document(
                                    chat_id=DUMP_CHAT_ID,
                                    document=part_file,
                                    caption=part_caption
                                )
                        except Exception as e:
                            logger.error(f"Failed to forward to dump channel: {e}")
                    
                    # Clean up part file
                    os.remove(part_file)
                except Exception as e:
                    logger.error(f"Error uploading part {i+1}: {e}")
                    await message.reply_text(f"❌ Error uploading part {i+1}: {str(e)}")
    else:
        # No splitting needed, upload directly
        try:
            # Check for user thumbnail
            thumbnail = None
            if user_id in user_thumbnails and os.path.exists(user_thumbnails[user_id]):
                thumbnail = user_thumbnails[user_id]
            
            # Upload based on file type
            if mime_type.startswith('video/'):
                await client.send_video(
                    chat_id=message.chat.id,
                    video=file_path,
                    caption=caption,
                    thumb=thumbnail,
                    supports_streaming=True,
                    progress=upload_progress
                )
            elif mime_type.startswith('audio/'):
                await client.send_audio(
                    chat_id=message.chat.id,
                    audio=file_path,
                    caption=caption,
                    thumb=thumbnail,
                    progress=upload_progress
                )
            elif mime_type.startswith('image/'):
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=file_path,
                    caption=caption,
                    progress=upload_progress
                )
            else:
                await client.send_document(
                    chat_id=message.chat.id,
                    document=file_path,
                    caption=caption,
                    thumb=thumbnail,
                    progress=upload_progress
                )
            
            # Also forward to dump channel if configured
            if DUMP_CHAT_ID:
                try:
                    if mime_type.startswith('video/'):
                        await client.send_video(
                            chat_id=DUMP_CHAT_ID,
                            video=file_path,
                            caption=caption,
                            thumb=thumbnail,
                            supports_streaming=True
                        )
                    elif mime_type.startswith('audio/'):
                        await client.send_audio(
                            chat_id=DUMP_CHAT_ID,
                            audio=file_path,
                            caption=caption,
                            thumb=thumbnail
                        )
                    elif mime_type.startswith('image/'):
                        await client.send_photo(
                            chat_id=DUMP_CHAT_ID,
                            photo=file_path,
                            caption=caption
                        )
                    else:
                        await client.send_document(
                            chat_id=DUMP_CHAT_ID,
                            document=file_path,
                            caption=caption,
                            thumb=thumbnail
                        )
                except Exception as e:
                    logger.error(f"Failed to forward to dump channel: {e}")
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            await message.reply_text(f"❌ Error uploading file: {str(e)}")
    
    # Clean up
    try:
        os.remove(file_path)
        await status_message.delete()
    except Exception as e:
        logger.error(f"Error cleaning up: {e}")

# Simple Flask web server to keep the bot alive
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Terabox Downloader Bot is running!"

def run_web_server():
    app_web.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Startup function
async def startup():
    logger.info("Starting Terabox Downloader Bot...")
    
    # Start web server in separate thread
    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Start the user client if configured
    if user:
        await user.start()
        logger.info("User client started")
    
    # Start bot client
    await app.start()
    logger.info("Bot started successfully!")
    
    # Keep the script running
    await asyncio.Event().wait()

# Shutdown handler
async def shutdown():
    logger.info("Shutting down...")
    await app.stop()
    if user:
        await user.stop()

# Handle signals
def signal_handler(sig, frame):
    logger.info("Received termination signal")
    asyncio.create_task(shutdown())
    sys.exit(0)

# Set up signal handlers
import signal
import sys
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Run the startup function
if __name__ == "__main__":
    try:
        asyncio.run(startup())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
