#!/bin/bash

# Check if aria2 is running
if ! pgrep -x "aria2c" > /dev/null
then
    echo "Starting aria2c daemon..."
    aria2c --enable-rpc --rpc-listen-all=true --rpc-allow-origin-all --daemon
else
    echo "aria2c is already running"
fi

# Start the bot
python terabox.py
