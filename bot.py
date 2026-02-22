import discord
from discord.ext import commands
import ollama
from groq import Groq
import json
import os
import asyncio
import time
from datetime import datetime
import sys
import requests

# ---------------- SETTINGS ----------------

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found")

groq_client = Groq(api_key=GROQ_API_KEY)

MODEL = "llama3.2"
GROQ_MODEL = "llama-3.1-70b-versatile"

OWNER_ID = 1474347479301361787
ALLOWED_SERVER_ID = 1474349501400612986
ALLOWED_CHANNEL_ID = 1474349502105129074

CUSTOM_PROMPT = """
You are Jarvis in a Discord server.
You understand group conversations.
You know who is speaking.
Only reply if:
- You are mentioned
- Or someone says 'jarvis'
Do not interrupt normal chat.
Be casual and natural.
"""

MEMORY_FILE = "memory.json"
LOG_FILE = "logs.json"

public_mode = True
jarvis_active = True
blacklist = set()
start_time = time.time()

# ---------------- DISCORD SETUP ----------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- LOAD MEMORY ----------------

memory = {}
channel_history = {}

if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        memory = json.load(f)

# ---------------- LOAD LOGS ----------------

logs = {
    "total_messages": 0,
    "user_messages": {},
    "daily": {},
    "model": MODEL
}

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)

# ---------------- SAVE FUNCTIONS ----------------

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=4)

def save_logs():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4)

# ---------------- READY EVENT ----------------

@bot.event
async def on_ready():
    print(f"{bot.user} is ONLINE (Hybrid Smart Mode Enabled)")

# -------------AI -----------------
OLLAMA_REMOTE_URL = "https://stubborn-gossipingly-karin.ngrok-free.dev"

async def generate_ai_response(channel_id):

    conversation = []

    for msg in channel_history[channel_id]:
        conversation.append({
            "role": "user",
            "content": f"{msg['name']}: {msg['content']}"
        })

    messages = [
        {"role": "system", "content": CUSTOM_PROMPT}
    ] + conversation

    # ---- Try Ollama ----
    try:
        response = ollama.chat(
            model=MODEL,
            messages=messages
        )

        reply = response.get("message", {}).get("content")
        if reply:
            print("🖥 Using OLLAMA")
            return reply

    except Exception as e:
        print("Ollama failed:", e)

    # ---- Try Groq ----
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",   # safe working model
            messages=messages,
            temperature=0.7
        )

        print("🌐 Using GROQ")
        return completion.choices[0].message.content

    except Exception as e:
        print("GROQ ERROR:", e)
        return f"Groq error: {str(e)}"
# ---------------- MESSAGE EVENT ----------------

@bot.event
async def on_message(message):
    global public_mode, jarvis_active

    if message.author.bot:
        return

    await bot.process_commands(message)

    if not message.guild:
        return

    if message.guild.id != ALLOWED_SERVER_ID:
        return

    if message.channel.id != ALLOWED_CHANNEL_ID:
        return

    user_id = str(message.author.id)
    username = message.author.name
    user_text = message.content.strip()

    # -------- OWNER STOP / ON --------
    if message.author.id == OWNER_ID and user_text.startswith("!owner"):
        parts = user_text.split()

        if len(parts) >= 2:

            if parts[1] == "stop":
                jarvis_active = False
                await message.channel.send("🛑 Jarvis stopped.")
                return

            if parts[1] == "on":
                jarvis_active = True
                await message.channel.send("🟢 Jarvis activated.")
                return

    if not jarvis_active:
        return

    if user_id in blacklist:
        return

    if not user_text:
        return

    # -------- Store Channel Conversation --------

    channel_id = str(message.channel.id)

    if channel_id not in channel_history:
        channel_history[channel_id] = []

    channel_history[channel_id].append({
        "name": username,
        "content": user_text
    })

    channel_history[channel_id] = channel_history[channel_id][-20:]

    # -------- Only Reply If Mentioned --------

    if bot.user not in message.mentions and "jarvis" not in user_text.lower():
        return

    # -------- Logging --------

    logs["total_messages"] += 1
    logs["user_messages"][username] = logs["user_messages"].get(username, 0) + 1
    today = str(datetime.now().date())
    logs["daily"][today] = logs["daily"].get(today, 0) + 1
    save_logs()

    # -------- AI Response --------

    try:
        async with message.channel.typing():

            reply = await generate_ai_response(channel_id)

            if len(reply) > 4000:
                reply = reply[:4000]

            embed = discord.Embed(
                title="💬 Jarvis",
                description=reply,
                color=discord.Color.blue()
            )

            embed.set_footer(
                text=f"Talking in {message.channel.name}",
                icon_url=message.author.display_avatar.url
            )

            embed.timestamp = discord.utils.utcnow()

            await message.channel.send(embed=embed)

    except Exception as e:
        print("MAIN ERROR:", e)
        await message.channel.send(f"Main error: {str(e)}")

# ---------------- RUN ----------------


bot.run(TOKEN)



