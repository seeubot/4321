#!/bin/bash
# Check if aria2 daemon is running, if not start it
if ! pgrep -x "aria2c" > /dev/null
then
    echo "Starting aria2c daemon..."
    aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all --daemon=true
fi

# Wait a moment to ensure aria2c is running
sleep 2

# Start the Python bot
echo "Starting Terabox Downloader Bot..."
python -u terabox.py # Or whatever your main script filename is
