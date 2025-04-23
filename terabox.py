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
from urllib.parse import urlparse
from flask import Flask, render_template
from threading import Thread
import requests
import json
import random
import string

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

# New config variable for request channel
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

# User thumbnail storage - in memory dictionary
user_thumbnails = {}

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

def format_speed(speed):
    if speed == 0:
        return "0 B/s"
    
    # Convert to appropriate unit with better precision
    if speed < 1024:
        return f"{speed:.2f} B/s"
    elif speed < 1024 * 1024:
        return f"{speed / 1024:.2f} KB/s"
    elif speed < 1024 * 1024 * 1024:
        return f"{speed / (1024 * 1024):.2f} MB/s"
    else:
        return f"{speed / (1024 * 1024 * 1024):.2f} GB/s"

def create_progress_bar(percentage):
    """Create a digital progress bar [0-100%]"""
    filled_length = int(percentage / 5)  # 20 segments for the bar
    empty_length = 20 - filled_length
    
    # Using block characters for a more digital look
    bar = '█' * filled_length + '░' * empty_length
    return f"[{bar}] {percentage:.1f}%"

# Function to get direct download link from API
async def get_direct_link(terabox_url):
    encoded_url = urllib.parse.quote(terabox_url)
    api_url = f"https://teraboxapi-phi.vercel.app/api?url={encoded_url}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        data = response.json()
        
        if data.get("status") != "success":
            return None, "API returned error status"
        
        extracted_info = data.get("Extracted Info", [])
        if not extracted_info:
            return None, "No extracted info found in API response"
        
        if not isinstance(extracted_info, list) or len(extracted_info) == 0:
            return None, "Invalid format of extracted info"
        
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

async def update_status_message(status_message, text):
    try:
        await status_message.edit_text(text)
    except Exception as e:
        logger.error(f"Failed to update status message: {e}")

@app.on_message(filters.text & ~filters.command)
async def handle_message(client: Client, message: Message):
    if message.text.startswith('/'):
        return
    if not message.from_user:
        return

    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/terao2")
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

    status_message = await message.reply_text("𝑷𝒓𝒐𝒄𝒆𝒔𝒔𝒊𝒏𝒈 𝒍𝒊𝒏𝒌 𝒂𝒏𝒅 𝒆𝒙𝒕𝒓𝒂𝒄𝒕𝒊𝒏𝒈 𝒅𝒊𝒓𝒆𝒄𝒕 𝒅𝒐𝒘𝒏𝒍𝒐𝒂𝒅 𝑼𝑹𝑳...")
    
    # Get direct download link from API
    direct_link, info = await get_direct_link(url)
    
    if not direct_link:
        await status_message.edit_text(f"Failed to extract direct download link: {info}")
        return
    
    await status_message.edit_text("sᴇɴᴅɪɴɢ ʏᴏᴜ ᴛʜᴇ ᴍᴇᴅɪᴀ...🤤")
    
    # Add the direct link to aria2 for download
    download = aria2.add_uris([direct_link])
    
    start_time = datetime.now()

    while not download.is_complete:
        await asyncio.sleep(15)
        download.update()
        progress = download.progress

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
        while True:
            try:
                await update_status_message(status_message, status_text)
                break
            except FloodWait as e:
                logger.error(f"Flood wait detected! Sleeping for {e.value} seconds")
                await asyncio.sleep(e.value)

    file_path = download.files[0].path
    caption = (
        f"✨ {download.name}\n"
        f"👤 ʟᴇᴇᴄʜᴇᴅ ʙʏ : <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>\n"
        f"📥 ᴜsᴇʀ ʟɪɴᴋ: tg://user?id={user_id}\n\n"
        "[TELUGU STUFF](https://t.me/dailydiskwala)"
    )

    last_update_time = time.time()
    UPDATE_INTERVAL = 15

    async def update_status(message, text):
        nonlocal last_update_time
        current_time = time.time()
        if current_time - last_update_time >= UPDATE_INTERVAL:
            try:
                await message.edit_text(text)
                last_update_time = current_time
            except FloodWait as e:
                logger.warning(f"FloodWait: Sleeping for {e.value}s")
                await asyncio.sleep(e.value)
                await update_status(message, text)
            except Exception as e:
                logger.error(f"Error updating status: {e}")

    async def upload_progress(current, total):
        progress = (current / total) * 100
        elapsed_time = datetime.now() - start_time
        elapsed_minutes, elapsed_seconds = divmod(elapsed_time.seconds, 60)
        
        # Calculate upload speed
        upload_speed = current / elapsed_time.seconds if elapsed_time.seconds > 0 else 0

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
        await update_status(status_message, status_text)

    async def split_video_with_ffmpeg(input_path, output_prefix, split_size):
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
                if current_time - last_progress_update >= UPDATE_INTERVAL:
                    elapsed = datetime.now() - start_time
                    progress_percentage = ((i) / parts) * 100
                    
                    status_text = (
                        f"✂️ Splitting {os.path.basename(input_path)}\n"
                        f"{create_progress_bar(progress_percentage)}\n"
                        f"Part {i+1}/{parts}\n"
                        f"Elapsed: {elapsed.seconds // 60}m {elapsed.seconds % 60}s"
                    )
                    await update_status(status_message, status_text)
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

    async def handle_upload():
        file_size = os.path.getsize(file_path)
        
        # Get user's thumbnail if exists
        thumbnail = user_thumbnails.get(user_id, None)
        
        if file_size > SPLIT_SIZE:
            await update_status(
                status_message,
                f"✂️ Splitting {download.name} ({format_size(file_size)})"
            )
            
            split_files = await split_video_with_ffmpeg(
                file_path,
                os.path.splitext(file_path)[0],
                SPLIT_SIZE
            )
            
            try:
                for i, part in enumerate(split_files):
                    part_caption = f"{caption}\n\nPart {i+1}/{len(split_files)}"
                    await update_status(
                        status_message,
                        f"📤 Uploading part {i+1}/{len(split_files)}\n"
                        f"{create_progress_bar((i/len(split_files))*100)}\n"
                        f"{os.path.basename(part)}"
                    )
                    
                    if USER_SESSION_STRING:
                        sent = await user.send_video(
                            DUMP_CHAT_ID, part, 
                            caption=part_caption,
                            thumb=thumbnail,  # Use the saved thumbnail
                            progress=upload_progress
                        )
                        await app.copy_message(
                            message.chat.id, DUMP_CHAT_ID, sent.id
                        )
                    else:
                        sent = await client.send_video(
                            DUMP_CHAT_ID, part,
                            caption=part_caption,
                            thumb=thumbnail,  # Use the saved thumbnail
                            progress=upload_progress
                        )
                        await client.send_video(
                            message.chat.id, sent.video.file_id,
                            caption=part_caption
                        )
                    os.remove(part)
            finally:
                for part in split_files:
                    try: os.remove(part)
                    except: pass
        else:
            await update_status(
                status_message,
                f"📤 Uploading {download.name}\n"
                f"{create_progress_bar(0)}\n"
                f"Size: {format_size(file_size)}"
            )
            
            if USER_SESSION_STRING:
                sent = await user.send_video(
                    DUMP_CHAT_ID, file_path,
                    caption=caption,
                    thumb=thumbnail,  # Use the saved thumbnail
                    progress=upload_progress
                )
                await app.copy_message(
                    message.chat.id, DUMP_CHAT_ID, sent.id
                )
            else:
                sent = await client.send_video(
                    DUMP_CHAT_ID, file_path,
                    caption=caption,
                    thumb=thumbnail,  # Use the saved thumbnail
                    progress=upload_progress
                )
                await client.send_video(
                    message.chat.id, sent.video.file_id,
                    caption=caption
                )
        if os.path.exists(file_path):
            os.remove(file_path)

    start_time = datetime.now()
    await handle_upload()

    try:
        await status_message.delete()
        await message.delete()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

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
