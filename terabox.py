from aria2p import API as Aria2API, Client as Aria2Client
import asyncio
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
import math
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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

# Request channel configuration
REQUEST_CHANNEL_ID = os.environ.get('REQUEST_CHANNEL_ID', '')
if len(REQUEST_CHANNEL_ID) == 0:
    logging.warning("REQUEST_CHANNEL_ID variable is missing! Video requests will not be stored.")
    REQUEST_CHANNEL_ID = None
else:
    REQUEST_CHANNEL_ID = int(REQUEST_CHANNEL_ID)

# Admin users who can approve requests
ADMIN_USERS = os.environ.get('ADMIN_USERS', '')
if len(ADMIN_USERS) == 0:
    logging.warning("ADMIN_USERS variable is missing! No users will be able to approve requests.")
    ADMIN_USERS = []
else:
    try:
        ADMIN_USERS = [int(admin.strip()) for admin in ADMIN_USERS.split(',')]
        logging.info(f"Admin users: {ADMIN_USERS}")
    except ValueError:
        logging.error("ADMIN_USERS format is incorrect. Should be comma-separated user IDs.")
        ADMIN_USERS = []

# User session handling with error management
USER_SESSION_STRING = os.environ.get('USER_SESSION_STRING', '')
if len(USER_SESSION_STRING) == 0:
    logging.info("USER_SESSION_STRING variable is missing! Bot will split Files in 2Gb...")
    USER_SESSION_STRING = None
    user = None
    SPLIT_SIZE = 2093796556
else:
    try:
        user = Client("jetu", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION_STRING)
        SPLIT_SIZE = 4241280205
    except Exception as e:
        logging.error(f"Error initializing user client: {e}")
        logging.info("Falling back to bot-only mode. Files will be split at 2GB.")
        USER_SESSION_STRING = None
        user = None
        SPLIT_SIZE = 2093796556

app = Client("jetbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Track client connection state
app._is_connected = False
if user:
    user._is_connected = False

VALID_DOMAINS = [
    'terabox.com', 'nephobox.com', '4funbox.com', 'mirrobox.com', 
    'momerybox.com', 'teraboxapp.com', '1024tera.com', 
    'terabox.app', 'gibibox.com', 'goaibox.com', 'terasharelink.com', 
    'teraboxlink.com', 'terafileshare.com'
]
last_update_time = 0

# Dictionary to store pending requests data
pending_requests = {}

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
    join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/jetmirror")
    developer_button = InlineKeyboardButton("ᴅᴇᴠᴇʟᴏᴘᴇʀ ⚡️", url="https://t.me/rtx5069")
    repo69 = InlineKeyboardButton("ʀᴇᴘᴏ 🌐", url="https://github.com/Hrishi2861/Terabox-Downloader-Bot")
    user_mention = message.from_user.mention
    reply_markup = InlineKeyboardMarkup([[join_button, developer_button], [repo69]])
    final_msg = f"ᴡᴇʟᴄᴏᴍᴇ, {user_mention}.\n\n🌟 ɪ ᴀᴍ ᴀ ᴛᴇʀᴀʙᴏx ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ʙᴏᴛ. sᴇɴᴅ ᴍᴇ ᴀɴʏ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ɪ ᴡɪʟʟ ᴅᴏᴡɴʟᴏᴀᴅ ᴡɪᴛʜɪɴ ғᴇᴡ sᴇᴄᴏɴᴅs ᴀɴᴅ sᴇɴᴅ ɪᴛ ᴛᴏ ʏᴏᴜ ✨.\n\n✨ ᴜsᴇ /request ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ʀᴇǫᴜᴇsᴛ ᴠɪᴅᴇᴏs ʙʏ sᴇɴᴅɪɴɢ sᴄʀᴇᴇɴsʜᴏᴛs."
    video_file_id = "/app/Jet-Mirror.mp4"
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
    if not message.from_user:
        return

    user_id = message.from_user.id
    is_member = await is_user_member(client, user_id)

    if not is_member:
        join_button = InlineKeyboardButton("ᴊᴏɪɴ ❤️🚀", url="https://t.me/jetmirror")
        reply_markup = InlineKeyboardMarkup([[join_button]])
        await message.reply_text("ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴍʏ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴍᴇ.", reply_markup=reply_markup)
        return

    if not REQUEST_CHANNEL_ID:
        await message.reply_text("ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ ғᴇᴀᴛᴜʀᴇ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴅɪsᴀʙʟᴇᴅ.")
        return

    if message.reply_to_message and message.reply_to_message.photo:
        # User is replying to a photo with the command
        photo = message.reply_to_message.photo
        photo_file_id = photo.file_id
        request_text = message.text.replace("/request", "").strip()
        
        if not request_text:
            await message.reply_text("ᴘʟᴇᴀsᴇ ᴀᴅᴅ ᴀ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ ᴏғ ᴛʜᴇ ᴠɪᴅᴇᴏ ʏᴏᴜ'ʀᴇ ʀᴇǫᴜᴇsᴛɪɴɢ.")
            return
        
        # Create a random request ID
        request_id = f"req_{int(time.time())}_{user_id}"
        
        # Create approve button
        approve_button = InlineKeyboardButton(
            "✅ ᴀᴘᴘʀᴏᴠᴇ & sᴇɴᴅ", 
            callback_data=f"approve_{request_id}"
        )
        reply_markup = InlineKeyboardMarkup([[approve_button]])
        
        # Forward the request to the admin channel
        try:
            caption = (
                f"📝 ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ | ɪᴅ: {request_id}\n\n"
                f"👤 ᴜsᴇʀ: <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>\n"
                f"🆔 ᴜsᴇʀ ɪᴅ: {user_id}\n\n"
                f"ᴅᴇsᴄʀɪᴘᴛɪᴏɴ: {request_text}"
            )
            
            admin_msg = await client.send_photo(
                chat_id=REQUEST_CHANNEL_ID,
                photo=photo_file_id,
                caption=caption,
                reply_markup=reply_markup
            )
            
            # Store request data for later use
            pending_requests[request_id] = {
                "user_id": user_id,
                "admin_msg_id": admin_msg.id,
                "description": request_text,
                "photo_id": photo_file_id,
                "timestamp": time.time()
            }
            
            await message.reply_text("✅ ʏᴏᴜʀ ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ sᴜʙᴍɪᴛᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ. ᴡᴇ'ʟʟ ᴛʀʏ ᴛᴏ ᴘʀᴏᴠɪᴅᴇ ᴛʜᴇ ᴠɪᴅᴇᴏ ᴀs sᴏᴏɴ ᴀs ᴘᴏssɪʙʟᴇ.")
        except Exception as e:
            logger.error(f"Error forwarding request: {e}")
            await message.reply_text("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ ᴡʜɪʟᴇ sᴜʙᴍɪᴛᴛɪɴɢ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")
    else:
        await message.reply_text("ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀɴ ɪᴍᴀɢᴇ/sᴄʀᴇᴇɴsʜᴏᴛ ᴡɪᴛʜ /request ᴀɴᴅ ᴀᴅᴅ ᴀ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ ᴏғ ᴛʜᴇ ᴠɪᴅᴇᴏ ʏᴏᴜ'ʀᴇ ʟᴏᴏᴋɪɴɢ ғᴏʀ.")

@app.on_callback_query(filters.regex(r"^approve_"))
async def approve_request(client: Client, callback: CallbackQuery):
    # Check if user is admin
    if callback.from_user.id not in ADMIN_USERS:
        await callback.answer("ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ ʀᴇǫᴜᴇsᴛs.", show_alert=True)
        return
    
    # Extract request ID from callback data
    request_id = callback.data.replace("approve_", "")
    
    # Check if request exists
    if request_id not in pending_requests:
        await callback.answer("ᴛʜɪs ʀᴇǫᴜᴇsᴛ ɴᴏ ʟᴏɴɢᴇʀ ᴇxɪsᴛs ᴏʀ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ᴘʀᴏᴄᴇssᴇᴅ.", show_alert=True)
        return
    
    request_data = pending_requests[request_id]
    user_id = request_data["user_id"]
    
    # Update the message to indicate approval
    await callback.edit_message_caption(
        caption=f"{callback.message.caption}\n\n✅ ᴀᴘᴘʀᴏᴠᴇᴅ ʙʏ: {callback.from_user.mention}",
        reply_markup=None
    )
    
    # Ask admin to send the terabox link
    await callback.message.reply_text(
        f"ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ ғᴏʀ ᴛʜɪs ʀᴇǫᴜᴇsᴛ ({request_id})."
    )
    
    # Set a flag to track the next message from this admin
    client.pending_link_request = {
        "admin_id": callback.from_user.id,
        "request_id": request_id
    }
    
    await callback.answer("ʀᴇǫᴜᴇsᴛ ᴀᴘᴘʀᴏᴠᴇᴅ. ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ.")

async def update_status_message(status_message, text):
    try:
        await status_message.edit_text(text)
    except Exception as e:
        logger.error(f"Failed to update status message: {e}")

@app.on_message(filters.text)
async def handle_message(client: Client, message: Message):
    if message.text.startswith('/'):
        return
    if not message.from_user:
        return

    user_id = message.from_user.id

    # Check if this is a response to a request for a terabox link from an admin
    if hasattr(client, 'pending_link_request') and client.pending_link_request and client.pending_link_request['admin_id'] == user_id:
        request_id = client.pending_link_request['request_id']
        
        if request_id in pending_requests:
            request_data = pending_requests[request_id]
            url = None
            
            # Find terabox URL in message
            for word in message.text.split():
                if is_valid_url(word):
                    url = word
                    break
            
            if not url:
                await message.reply_text("ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ᴛᴇʀᴀʙᴏx ʟɪɴᴋ.")
                return
            
            # Clear the pending request
            del client.pending_link_request
            
            # Process the URL for the original requester
            await message.reply_text(f"ᴘʀᴏᴄᴇssɪɴɢ ʟɪɴᴋ ғᴏʀ ʀᴇǫᴜᴇsᴛ {request_id}...")
            
            # Notify user that their request has been approved
            try:
                await client.send_message(
                    chat_id=request_data["user_id"],
                    text=f"✅ ʏᴏᴜʀ ᴠɪᴅᴇᴏ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ᴀᴘᴘʀᴏᴠᴇᴅ! ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ɴᴏᴡ..."
                )
            except Exception as e:
                logger.error(f"Error notifying user {request_data['user_id']}: {e}")
            
            # Process the URL for download
            await process_download(client, url, message, target_user_id=request_data["user_id"])
            
            # Remove from pending requests
            del pending_requests[request_id]
            return
    
    # Regular URL processing path
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

    await process_download(client, url, message)

async def process_download(client, url, message, target_user_id=None):
    # If target_user_id is not provided, use the message sender
    if target_user_id is None:
        target_user_id = message.from_user.id
    
    encoded_url = urllib.parse.quote(url)
    # Updated API URL
    final_url = f"https://teraboxapi-phi.vercel.app/api?url={encoded_url}"

    download = aria2.add_uris([final_url])
    status_message = await message.reply_text("⏳ ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ᴍᴇᴅɪᴀ...")

    start_time = datetime.now()

    while not download.is_complete:
        await asyncio.sleep(15)
        download.update()
        progress = download.progress

        # Simplified progress bar
        progress_bar = "■" * int(progress / 10) + "□" * (10 - int(progress / 10))
        
        status_text = (
            f"📥 ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ: {download.name}\n"
            f"{progress_bar} {progress:.1f}%\n"
            f"sɪᴢᴇ: {format_size(download.completed_length)}/{format_size(download.total_length)}"
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
        f"👤 ʟᴇᴇᴄʜᴇᴅ ʙʏ : <a href='tg://user?id={target_user_id}'>{message.from_user.first_name}</a>\n"
        f"📥 ᴜsᴇʀ ʟɪɴᴋ: tg://user?id={target_user_id}\n\n"
        "[ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴊᴇᴛ-ᴍɪʀʀᴏʀ ❤️🚀](https://t.me/JetMirror)"
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
        
        # Simplified upload progress bar
        progress_bar = "■" * int(progress / 10) + "□" * (10 - int(progress / 10))
        
        status_text = (
            f"📤 ᴜᴘʟᴏᴀᴅɪɴɢ: {download.name}\n"
            f"{progress_bar} {progress:.1f}%"
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
                    status_text = f"✂️ sᴘʟɪᴛᴛɪɴɢ ᴠɪᴅᴇᴏ: ᴘᴀʀᴛ {i+1}/{parts}"
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
        
        if file_size > SPLIT_SIZE:
            await update_status(
                status_message,
                f"✂️ sᴘʟɪᴛᴛɪɴɢ ᴠɪᴅᴇᴏ..."
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
                        f"📤 ᴜᴘʟᴏᴀᴅɪɴɢ ᴘᴀʀᴛ {i+1}/{len(split_files)}"
                    )
                    
                    if USER_SESSION_STRING and user._is_connected:
                        sent = await user.send_video(
                            DUMP_CHAT_ID, part, 
                            caption=part_caption,
                            progress=upload_progress
                        )
                        await app.copy_message(
                            target_user_id, DUMP_CHAT_ID, sent.id
                        )
                    else:
                        sent = await client.send_video(
                            target_user_id, part,
                            caption=part_caption,
                            progress=upload_progress
                        )
                    
                    # Delete part file after upload
                    try:
                        os.remove(part)
                    except Exception as e:
                        logger.error(f"Error removing part file: {e}")
            except Exception as e:
                logger.error(f"Upload error: {e}")
                await update_status(
                    status_message,
                    f"❌ ᴇʀʀᴏʀ ᴜᴘʟᴏᴀᴅɪɴɢ sᴘʟɪᴛ ғɪʟᴇ: {str(e)}"
                )
        else:
            try:
                if USER_SESSION_STRING and user._is_connected:
                    sent = await user.send_video(
                        DUMP_CHAT_ID, file_path,
                        caption=caption,
                        progress=upload_progress
                    )
                    await app.copy_message(
                        target_user_id, DUMP_CHAT_ID, sent.id
                    )
                else:
                    sent = await client.send_video(
                        target_user_id, file_path,
                        caption=caption,
                        progress=upload_progress
                    )
            except FloodWait as e:
                logger.warning(f"FloodWait: Sleeping for {e.value}s")
                await asyncio.sleep(e.value)
                return await handle_upload()
            except Exception as e:
                # For files not recognized as video, send as document
                logger.warning(f"Error sending as video: {e}")
                try:
                    if USER_SESSION_STRING and user._is_connected:
                        sent = await user.send_document(
                            DUMP_CHAT_ID, file_path,
                            caption=caption,
                            progress=upload_progress
                        )
                        await app.copy_message(
                            target_user_id, DUMP_CHAT_ID, sent.id
                        )
                    else:
                        sent = await client.send_document(
                            target_user_id, file_path,
                            caption=caption,
                            progress=upload_progress
                        )
                except Exception as doc_e:
                    logger.error(f"Error sending as document: {doc_e}")
                    await update_status(
                        status_message,
                        f"❌ ᴇʀʀᴏʀ ᴜᴘʟᴏᴀᴅɪɴɢ ғɪʟᴇ: {str(doc_e)}"
                    )
                    return

        # Clean up
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error removing file: {e}")

        end_time = datetime.now()
        time_taken = (end_time - start_time).total_seconds()
        
        await update_status(
            status_message,
            f"✅ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ᴜᴘʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ɪɴ {time_taken:.1f} sᴇᴄᴏɴᴅs."
        )

    await handle_upload()

# Initialize Flask app for web interface
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return render_template('index.html')

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Ensure proper client connection and disconnection
async def start_clients():
    global app, user
    
    try:
        await app.start()
        app._is_connected = True
        logger.info("Bot client started successfully")
        
        if user:
            try:
                await user.start()
                user._is_connected = True
                logger.info("User client started successfully")
            except Exception as e:
                logger.error(f"Failed to start user client: {e}")
                user = None
    except Exception as e:
        logger.error(f"Failed to start bot client: {e}")
        exit(1)

async def stop_clients():
    global app, user
    
    if app and app._is_connected:
        await app.stop()
        app._is_connected = False
        logger.info("Bot client stopped")
    
    if user and user._is_connected:
        await user.stop()
        user._is_connected = False
        logger.info("User client stopped")

async def main():
    # Start the web server in a separate thread
    web_thread = Thread(target=run_flask)
    web_thread.daemon = True
    web_thread.start()
    
    # Start clients
    await start_clients()
    
    try:
        # Keep the main task running
        await asyncio.Future()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Received shutdown signal")
    finally:
        # Clean shutdown
        await stop_clients()

if __name__ == "__main__":
    asyncio.run(main())
