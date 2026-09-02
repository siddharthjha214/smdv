#!/bin/bash
echo "============================================="
echo "   YOUTUBE TRACKER EMERGENCY RUNNER"
echo "============================================="

# 1. Pull latest code
echo "Pulling latest code from GitHub..."
git pull origin main

# 2. Check Internet Connectivity
echo "Checking internet connectivity..."
ping -c 1 google.com > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "CRITICAL ERROR: No internet connection! Aborting."
    exit 1
fi

# 3. Source secrets
if [ -f "secrets.sh" ]; then
    echo "Loading secrets..."
    source secrets.sh
else
    echo "CRITICAL ERROR: secrets.sh not found! Aborting."
    exit 1
fi

# 4. Run bot
echo "Executing main.py..."
./venv/bin/python3 main.py

echo "============================================="
echo "Emergency run complete."
