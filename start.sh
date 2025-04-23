#!/bin/bash

# Check if aria2 is running (using ps instead of pgrep)
if ! ps aux | grep "aria2c" | grep -v grep > /dev/null
then
    echo "Starting aria2c daemon..."
    aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all --daemon
else
    echo "aria2c is already running"
fi

# Add a delay before starting the bot to address potential rate limiting
echo "Waiting for 10 seconds before starting the bot..."
sleep 10

# Patch the code to work with standard Pyrogram (if needed)
if [ -f "patch_pyrogram.py" ]; then
    echo "Patching Pyrogram..."
    python patch_pyrogram.py
fi

# Start the bot with retry logic for flood wait
echo "Starting the bot..."
python terabox.py
