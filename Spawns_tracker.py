import discord
from discord.ext import commands, tasks
import os
import json
import re
import asyncio
from datetime import datetime
from huggingface_hub import HfApi, hf_hub_download
import shutil

# --- CONFIGURATION ---
DATASET_REPO = "DiscordBOTNHIHUN/P2AURA-FARMER"
HF_TOKEN = os.getenv("HF_TOKEN")
SPAWN_FILE = "spawn_counts.json"
POKETWO_ID = 716390085896962058
P2_ASSISTANT_IDS = [854233015475109888, 1459494731775217860, 1307910235737948252]
POKENAME_BOT_ID = 874910942490677270
DEVELOPER_IDS = [1378954077462986772]  # Only you can use .reset

# Custom emojis (replace with your actual emoji IDs)
EMOJI_SHIELD = "<:Role_Admin_White:1490432406988132352>"
EMOJI_WARNING = "<:IMG_20260616_005310:1516161318166593718>"
EMOJI_TROPHY = "<:952396trophie:1516160170756145293>"
EMOJI_CHART = "<:1423statistics:1516152761786302665>"
EMOJI_RESET = "<:87929developerglow:1516154803028361256>"
EMOJI_TIME = "<:79071_starrymoon:1515635746008989826>"
EMOJI_LIVE = "<:emoji_1738170667573:1492147995741786122>"

# Medal emojis (replace with your actual emoji IDs)
MEDAL_1ST = "<a:76245medalla:1516152753750282270>"
MEDAL_2ND = "<a:78330medalsilver:1516152758523396288>"
MEDAL_3RD = "<a:720660medalbronze:1516152756325454036>"

# Store live leaderboard messages for editing
live_messages = {}

# --- HF functions ---
hf_api = HfApi()

def sync_from_hub():
    try:
        path = hf_hub_download(
            repo_id=DATASET_REPO,
            filename=SPAWN_FILE,
            repo_type="dataset",
            token=HF_TOKEN
        )
        shutil.copy(path, f"./{SPAWN_FILE}")
        print(f"✅ [HUB] Synced {SPAWN_FILE}")
        return True
    except Exception as e:
        print(f"⚠️ [HUB] {SPAWN_FILE} not found (first run): {e}")
        return False

def save_to_hub():
    try:
        hf_api.upload_file(
            path_or_fileobj=SPAWN_FILE,
            path_in_repo=SPAWN_FILE,
            repo_id=DATASET_REPO,
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"☁️ [HUB] {SPAWN_FILE} backed up.")
    except Exception as e:
        print(f"❌ [HUB] Backup failed: {e}")

# --- Data management (per-server) ---
def load_data():
    if os.path.exists(SPAWN_FILE):
        with open(SPAWN_FILE, 'r') as f:
            return json.load(f)
    return {"servers": {}, "global": {"total_spawns": 0, "started": None}}

def save_data(data):
    with open(SPAWN_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    save_to_hub()

def get_server_data(guild_id, guild_name):
    data = load_data()
    guild_id_str = str(guild_id)
    if guild_id_str not in data["servers"]:
        data["servers"][guild_id_str] = {
            "name": guild_name,
            "counts": {},
            "total_spawns": 0,
            "last_spawn": None
        }
        save_data(data)
    return data, data["servers"][guild_id_str]

def record_spawn(guild_id, guild_name, pokemon_name):
    data, server = get_server_data(guild_id, guild_name)
    pokemon = pokemon_name.strip().capitalize()
    
    server["counts"][pokemon] = server["counts"].get(pokemon, 0) + 1
    server["total_spawns"] += 1
    server["last_spawn"] = datetime.now().isoformat()
    
    data["global"]["total_spawns"] = data["global"].get("total_spawns", 0) + 1
    if data["global"].get("started") is None:
        data["global"]["started"] = datetime.now().isoformat()
    
    save_data(data)
    print(f"[{guild_name}] Recorded spawn: {pokemon} (#{server['total_spawns']})")
    
    # Trigger live leaderboard updates
    asyncio.create_task(update_live_leaderboards(guild_id))
    
    return server

def get_top_10(server_data):
    counts = server_data.get("counts", {})
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]

def extract_pokemon_name(text):
    """Extract Pokémon name from various naming bot formats."""
    # Format 1: "Pikachu: 99.98%" or "Pikachu 🐍: 99.26%"
    match = re.search(r'^([A-Za-z\s\-\.\'’]+)[\s:🐍✨🌟]', text)
    if match:
        return match.group(1).strip()
    
    # Format 2: "Best name: Pikachu"
    match = re.search(r'Best name:\s*([A-Za-z\s\-\.\'’]+)', text)
    if match:
        return match.group(1).strip()
    
    # Format 3: Just the name at start of line
    match = re.search(r'^([A-Za-z\s\-\.\'’]+)$', text.strip())
    if match:
        return match.group(1).strip()
    
    return None

async def update_live_leaderboards(guild_id):
    """Update all live leaderboard messages for a guild."""
    if guild_id not in live_messages:
        return
    
    data, server = get_server_data(guild_id, "")
    top_list = get_top_10(server)
    
    embed = create_leaderboard_embed(server, top_list)
    
    for channel_id, message_id in live_messages[guild_id].items():
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed)
        except Exception as e:
            print(f"Failed to update live leaderboard: {e}")

def create_leaderboard_embed(server, top_list):
    """Create the leaderboard embed."""
    embed = discord.Embed(
        title=f"{EMOJI_LIVE} LIVE Leaderboard {EMOJI_LIVE}",
        description=f"**{server.get('name', 'Unknown Server')}**\nTotal spawns tracked: **{server.get('total_spawns', 0)}**",
        color=0x2C2C2C,
        timestamp=datetime.now()
    )
    
    if not top_list:
        embed.add_field(name=f"{EMOJI_CHART}", value="No spawns recorded yet.", inline=False)
    else:
        for i, (name, count) in enumerate(top_list, 1):
            if i == 1:
                medal = MEDAL_1ST
            elif i == 2:
                medal = MEDAL_2ND
            elif i == 3:
                medal = MEDAL_3RD
            else:
                medal = f"✨ `{i:2d}`"
            
            embed.add_field(
                name=f"{medal} {name}",
                value=f"**{count}** spawns",
                inline=False
            )
    
    if server.get("last_spawn"):
        last = datetime.fromisoformat(server["last_spawn"])
        embed.set_footer(
            text=f" Updates every 10s | Last spawn: {last.strftime('%H:%M:%S')}",
            icon_url=bot.user.display_avatar.url
        )
    else:
        embed.set_footer(text="🔄 Updates every 10 seconds", icon_url=bot.user.display_avatar.url)
    
    return embed

# --- Discord bot setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_ready():
    sync_from_hub()
    print(f"✅ Spawn Tracker online as {bot.user.name}")
    print(f"🎯 Tracking {len(bot.guilds)} servers")
    live_updater.start()

@bot.event
async def on_message(message):
    # Only track messages from naming bots
    if message.author.id not in P2_ASSISTANT_IDS and message.author.id != POKENAME_BOT_ID:
        await bot.process_commands(message)
        return
    
    if message.guild is None:
        await bot.process_commands(message)
        return
    
    # Extract Pokémon name from message
    pokemon = extract_pokemon_name(message.content)
    if pokemon:
        record_spawn(message.guild.id, message.guild.name, pokemon)
    
    await bot.process_commands(message)

@tasks.loop(seconds=10)
async def live_updater():
    """Update all live leaderboards every 10 seconds."""
    for guild_id, channels in live_messages.items():
        data, server = get_server_data(guild_id, "")
        top_list = get_top_10(server)
        embed = create_leaderboard_embed(server, top_list)
        
        for channel_id, message_id in channels.items():
            try:
                channel = bot.get_channel(channel_id)
                if channel:
                    msg = await channel.fetch_message(message_id)
                    await msg.edit(embed=embed)
            except Exception as e:
                print(f"Live update error: {e}")

@bot.command(name="top")
async def show_top(ctx):
    """Show top 10 spawned Pokémon in this server."""
    data, server = get_server_data(ctx.guild.id, ctx.guild.name)
    top_list = get_top_10(server)
    
    if not top_list:
        embed = discord.Embed(
            title=f"{EMOJI_CHART} Spawn Leaderboard",
            description="No spawns recorded yet in this server.",
            color=0x2C2C2C,
            timestamp=datetime.now()
        )
        embed.set_footer(text="P2 Spawn Tracker", icon_url=bot.user.display_avatar.url)
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"{EMOJI_TROPHY} Top 10 Spawned Pokémon",
        description=f"**{ctx.guild.name}**\nTotal spawns tracked: **{server['total_spawns']}**",
        color=0x2C2C2C,
        timestamp=datetime.now()
    )
    
    for i, (name, count) in enumerate(top_list, 1):
        if i == 1:
            medal = MEDAL_1ST
        elif i == 2:
            medal = MEDAL_2ND
        elif i == 3:
            medal = MEDAL_3RD
        else:
            medal = f"✨ `{i:2d}`"
        
        embed.add_field(
            name=f"{medal} {name}",
            value=f"**{count}** spawns",
            inline=False
        )
    
    if server.get("last_spawn"):
        last = datetime.fromisoformat(server["last_spawn"])
        embed.set_footer(
            text=f"Last spawn: {last.strftime('%Y-%m-%d %H:%M:%S')}",
            icon_url=bot.user.display_avatar.url
        )
    else:
        embed.set_footer(text="P2 Spawn Tracker", icon_url=bot.user.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name="live")
async def live_leaderboard(ctx):
    """Start a live-updating leaderboard in this channel."""
    if ctx.guild.id not in live_messages:
        live_messages[ctx.guild.id] = {}
    
    # Check if already has a live leaderboard in this channel
    if ctx.channel.id in live_messages[ctx.guild.id]:
        await ctx.send("⚠️ Live leaderboard already exists in this channel!")
        return
    
    data, server = get_server_data(ctx.guild.id, ctx.guild.name)
    top_list = get_top_10(server)
    embed = create_leaderboard_embed(server, top_list)
    
    msg = await ctx.send(embed=embed)
    live_messages[ctx.guild.id][ctx.channel.id] = msg.id
    
    await ctx.send(f"{EMOJI_LIVE} Live leaderboard started! Updates every 10 seconds. Type `.stop_live` to stop.")

@bot.command(name="stop_live")
async def stop_live(ctx):
    """Stop the live leaderboard in this channel."""
    if ctx.guild.id in live_messages and ctx.channel.id in live_messages[ctx.guild.id]:
        del live_messages[ctx.guild.id][ctx.channel.id]
        await ctx.send(f"{EMOJI_SHIELD} Live leaderboard stopped in this channel.")
    else:
        await ctx.send("No live leaderboard running in this channel.")

@bot.command(name="stats")
async def show_stats(ctx):
    """Show detailed spawn statistics for this server."""
    data, server = get_server_data(ctx.guild.id, ctx.guild.name)
    
    if server['total_spawns'] == 0:
        embed = discord.Embed(
            title=f"{EMOJI_SHIELD} Server Statistics",
            description="No spawn data recorded yet.",
            color=0x2C2C2C,
            timestamp=datetime.now()
        )
        embed.set_footer(text="P2 Spawn Tracker")
        await ctx.send(embed=embed)
        return
    
    unique_count = len(server.get("counts", {}))
    top_list = get_top_10(server)
    top_name, top_count = top_list[0] if top_list else ("None", 0)
    top_percentage = (top_count / server['total_spawns']) * 100 if server['total_spawns'] > 0 else 0
    
    embed = discord.Embed(
        title=f"{EMOJI_CHART} Spawn Statistics",
        description=f"**{ctx.guild.name}**",
        color=0x2C2C2C,
        timestamp=datetime.now()
    )
    
    embed.add_field(name=f"{EMOJI_SHIELD} Total Spawns", value=f"**{server['total_spawns']}**", inline=True)
    embed.add_field(name=f"{EMOJI_TROPHY} Unique Pokémon", value=f"**{unique_count}**", inline=True)
    embed.add_field(name=f"🏆 Most Common", value=f"**{top_name}** ({top_count} times, {top_percentage:.1f}%)", inline=False)
    
    if server.get("last_spawn"):
        last = datetime.fromisoformat(server["last_spawn"])
        embed.add_field(name=f"{EMOJI_TIME} Last Spawn", value=f"<t:{int(last.timestamp())}:R>", inline=False)
    
    embed.set_footer(text="P2 Spawn Tracker", icon_url=bot.user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="reset")
async def reset_server_stats(ctx):
    """Reset spawn statistics for this server (Developer only)."""
    if ctx.author.id not in DEVELOPER_IDS:
        embed = discord.Embed(
            title=f"{EMOJI_WARNING} Permission Denied",
            description="Only the bot developer can reset spawn statistics.",
            color=0x2C2C2C
        )
        await ctx.send(embed=embed)
        return
    
    data = load_data()
    guild_id_str = str(ctx.guild.id)
    
    if guild_id_str in data["servers"]:
        del data["servers"][guild_id_str]
        save_data(data)
        
        embed = discord.Embed(
            title=f"{EMOJI_RESET} Statistics Reset",
            description=f"Spawn data for **{ctx.guild.name}** has been cleared.",
            color=0x2C2C2C,
            timestamp=datetime.now()
        )
        embed.set_footer(text="P2 Spawn Tracker", icon_url=bot.user.display_avatar.url)
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title=f"{EMOJI_SHIELD} No Data",
            description=f"No spawn data found for **{ctx.guild.name}**.",
            color=0x2C2C2C
        )
        await ctx.send(embed=embed)

@bot.command(name="global")
async def global_stats(ctx):
    """Show global statistics across all servers (Developer only)."""
    if ctx.author.id not in DEVELOPER_IDS:
        return
    
    data = load_data()
    total = data["global"].get("total_spawns", 0)
    started = data["global"].get("started")
    
    embed = discord.Embed(
        title=" __Global Spawn Statistics__ ",
        color=0x2C2C2C,
        timestamp=datetime.now()
    )
    
    embed.add_field(name=f"{EMOJI_CHART}Total Spawns", value=f"**{total}**", inline=True)
    embed.add_field(name=" Servers Tracked", value=f"**{len(data['servers'])}**", inline=True)
    
    if started:
        start_dt = datetime.fromisoformat(started)
        embed.add_field(name="⏱️ Tracking Since", value=f"<t:{int(start_dt.timestamp())}:D>", inline=False)
    
    embed.set_footer(text="P2 Spawn Tracker", icon_url=bot.user.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="servers")
async def list_tracked_servers(ctx):
    """List all servers the bot is tracking (Developer only)."""
    if ctx.author.id not in DEVELOPER_IDS:
        return
    
    data = load_data()
    servers = data.get("servers", {})
    
    if not servers:
        await ctx.send("No servers are being tracked yet.")
        return
    
    server_list = []
    for sid, info in servers.items():
        server_list.append(f"**{info['name']}** – {info['total_spawns']} spawns")
    
    embed = discord.Embed(
        title="📡 Tracked Servers",
        description="\n".join(server_list[:25]),
        color=0x2C2C2C
    )
    embed.set_footer(text=f"Total: {len(servers)} servers")
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

if __name__ == "__main__":
    from flask import Flask
    from threading import Thread
    app = Flask('')
    @app.route('/')
    def home():
        return "Spawn Tracker is alive!"
    def run():
        port = int(os.environ.get("PORT", 7860))
        app.run(host='0.0.0.0', port=port)
    Thread(target=run, daemon=True).start()

    token = os.getenv("SPAWN_TRACKER_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ Missing SPAWN_TRACKER_TOKEN")
