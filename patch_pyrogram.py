#!/usr/bin/env python3
"""
This script patches the bot code to work with standard Pyrogram instead of PyroFork.
Run this script before starting the bot if you're using standard Pyrogram.
"""
import os
import re

def patch_file(filename):
    if not os.path.exists(filename):
        print(f"File {filename} not found")
        return False
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Replace PyroFork specific mentions with Pyrogram
    content = content.replace('PyroFork v2.2.11', 'Pyrogram')
    
    # Other potential replacements here if needed
    
    with open(filename, 'w') as f:
        f.write(content)
    
    print(f"Successfully patched {filename}")
    return True

if __name__ == "__main__":
    patch_file("terabox.py")
