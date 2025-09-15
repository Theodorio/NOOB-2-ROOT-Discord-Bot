import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime
import os
import json
from dotenv import load_dotenv
from itertools import cycle
import aiohttp
from openai import OpenAI
import random

# =============================
# Load tokens from .env
# =============================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# =============================
# Channel IDs
# =============================
BOT_COMMANDS_CHANNEL_ID = 1413271293876244573
WELCOME_CHANNEL_ID = 1373637745376886847
ANNOUNCEMENT_CHANNEL_ID = 1413275012923920445
GAME_CHANNEL_ID = 1413980135555858432
REMINDER_CHANNEL_ID = 1413275012923920445

# =============================
# Setup bot
# =============================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# =============================
# OpenRouter client
# =============================
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
) if OPENROUTER_API_KEY else None

# =============================
# JSON persistence
# =============================
TASKS_FILE = "tasks.json"
REMINDERS_FILE = "reminders.json"
RESOURCES_FILE = "resources.json"
PROJECTS_FILE = "projects.json"
EVENTS_FILE = "events.json"
QUIZZES_FILE = "quizzes.json"
CHALLENGES_FILE = "challenges.json"
PROGRESS_FILE = "progress.json"

def load_json(file, default):
    try:
        with open(file, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) or isinstance(data, list) else default
    except FileNotFoundError:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

tasks_data = load_json(TASKS_FILE, {})
reminders = load_json(REMINDERS_FILE, {})
resources = load_json(RESOURCES_FILE, {"cybersecurity": [], "blender": [], "webdev": [], "blockchain": [], "general": []})
projects = load_json(PROJECTS_FILE, [])
events = load_json(EVENTS_FILE, {})
quizzes = load_json(QUIZZES_FILE, {"cybersecurity": [], "blender": [], "webdev": [], "blockchain": [], "general": []})
challenges = load_json(CHALLENGES_FILE, {"current": None, "date": None, "user_progress": {}})
progress_data = load_json(PROGRESS_FILE, {})

# =============================
# Gamification setup
# =============================
CATEGORY_BONUSES = {"cybersecurity": 2, "blender": 2, "webdev": 1, "blockchain": 3, "general": 0}

async def check_roles(user):
    user_id = str(user.id)
    points = progress_data[user_id]["points"]
    cat_points = progress_data[user_id]["category_points"]
    roles_assigned = progress_data[user_id]["roles_assigned"]
    guild = user.guild
    role_thresholds = [
        {"name": "Cyber Pro", "points": 1000, "type": "general"},
        {"name": "Blender Guru", "points": 2000, "type": "blender"},
        {"name": "Web Dev Wizard", "points": 3000, "type": "webdev"},
        {"name": "Blockchain Master", "points": 5000, "type": "blockchain"},
        {"name": "NFT Pioneer", "points": 3000, "type": "blockchain"}
    ]
    for role_info in role_thresholds:
        role = discord.utils.get(guild.roles, name=role_info["name"])
        if not role:
            role = await guild.create_role(name=role_info["name"])
        req_points = role_info["points"]
        if role_info["type"] == "general":
            if points >= req_points and role_info["name"] not in roles_assigned:
                await user.add_roles(role)
                roles_assigned.append(role_info["name"])
        else:
            if cat_points.get(role_info["type"], 0) >= req_points and role_info["name"] not in roles_assigned:
                await user.add_roles(role)
                roles_assigned.append(role_info["name"])
        progress_data[user_id]["roles_assigned"] = roles_assigned
    save_json(PROGRESS_FILE, progress_data)

# =============================
# Helpers
# =============================
def is_mod():
    async def predicate(interaction: discord.Interaction):
        mod_role = discord.utils.get(interaction.guild.roles, name="MOD")
        if mod_role and mod_role in interaction.user.roles:
            return True
        await interaction.response.send_message("❌ You need the MOD role!", ephemeral=True)
        return False
    return app_commands.check(predicate)

# =============================
# Welcome Event
# =============================
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    role = discord.utils.get(member.guild.roles, name="NOOBS")
    if role:
        await member.add_roles(role)
    embed = discord.Embed(
        title="🎉 Welcome to the Community!",
        description=f"Hey {member.mention}, you’ve just joined a hub of curious minds! Whether you’re into Cybersecurity, Blender, Web Dev, or Blockchain, you’ll find friends and challenges here.",
        color=0x00FF00,
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    intro_channel_id = 1416866081683013752
    embed.add_field(
        name="Get Started",
        value=f"Introduce yourself in <#{intro_channel_id}> to get a full access and explore the server! ",
        inline=False
    )
    await channel.send(embed=embed)

# =============================
# Grant Full Access on Introduction
# =============================
@bot.event
async def on_message(message):
    intro_channel_id = 1416866081683013752
    full_access_role_name = "Full Access"
    if message.channel.id == intro_channel_id and not message.author.bot:
        guild = message.guild
        role = discord.utils.get(guild.roles, name=full_access_role_name)
        if not role:
            role = await guild.create_role(name=full_access_role_name)
        if role not in message.author.roles:
            await message.author.add_roles(role)
            await message.channel.send(f"✅ {message.author.mention}, you now have full access! Welcome!")
    await bot.process_commands(message)

# =============================
# Resource Commands
# =============================
@tree.command(name="resource", description="Get learning resources by topic")
@app_commands.describe(topic="Topic: cybersecurity, blender, webdev, blockchain, general", search="Optional search term")
async def resource(interaction: discord.Interaction, topic: str, search: str = None):
    if topic.lower() not in resources:
        await interaction.response.send_message("❌ Invalid topic. Try: cybersecurity, blender, webdev, blockchain, general.", ephemeral=True)
        return
    filtered = resources[topic.lower()]
    if search:
        filtered = [r for r in filtered if search.lower() in r["title"].lower()]
    if not filtered:
        await interaction.response.send_message(f"❌ No resources found for {topic}.", ephemeral=True)
        return
    embed = discord.Embed(title=f"📚 {topic.title()} Resources", color=0x00FF00)
    for r in filtered[:5]:
        embed.add_field(name=r["title"], value=f"[Link]({r['url']})", inline=False)
    featured = next((r for r in filtered if r.get("featured")), None)
    if featured:
        embed.add_field(name="🌟 Featured", value=f"{featured['title']}: [Link]({featured['url']})", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="resource_add", description="Add a resource (mod only)")
@is_mod()
@app_commands.describe(topic="Topic: cybersecurity, blender, webdev, blockchain, general", title="Resource title", url="Resource URL", featured="Mark as featured? (true/false)")
async def resource_add(interaction: discord.Interaction, topic: str, title: str, url: str, featured: bool = False):
    if topic.lower() not in resources:
        await interaction.response.send_message("❌ Invalid topic.", ephemeral=True)
        return
    resources[topic.lower()].append({"title": title, "url": url, "featured": featured, "upvotes": 0, "downvotes": 0})
    save_json(RESOURCES_FILE, resources)
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    await channel.send(f"📢 New {topic} resource: **{title}** [Link]({url})" + (" 🌟 (Featured)" if featured else ""))
    await interaction.response.send_message(f"✅ Added {title} to {topic} resources.", ephemeral=True)

# =============================
# Project Showcase Commands
# =============================
@tree.command(name="submit_project", description="Submit a project to #project-hub")
@app_commands.describe(title="Project title", description="Project details", link="Optional link (e.g., GitHub)", image="Optional image attachment", category="Category: cybersecurity, blender, webdev, blockchain, general")
async def submit_project(interaction: discord.Interaction, title: str, description: str, link: str = None, image: discord.Attachment = None, category: str = "general"):
    valid_categories = ["cybersecurity", "blender", "webdev", "blockchain", "general"]
    if category.lower() not in valid_categories:
        await interaction.response.send_message("❌ Invalid category.", ephemeral=True)
        return
    project = {
        "user_id": str(interaction.user.id),
        "title": title,
        "description": description,
        "link": link,
        "image": str(image.url) if image else None,
        "timestamp": datetime.now().isoformat(),
        "upvotes": 0,
        "category": category.lower()
    }
    projects.append(project)
    save_json(PROJECTS_FILE, projects)
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    embed = discord.Embed(title=f"🚀 New Project: {title}", description=description, color=0xFFD700)
    if link:
        embed.add_field(name="Link", value=f"[Click here]({link})", inline=False)
    if image:
        embed.set_image(url=image.url)
    embed.set_footer(text=f"Submitted by {interaction.user.name} | React with 👍 to upvote!")
    message = await channel.send(embed=embed)
    await message.add_reaction("👍")
    user_id = str(interaction.user.id)
    progress_data.setdefault(user_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    points = 10 + CATEGORY_BONUSES.get(category.lower(), 0)
    progress_data[user_id]["points"] += points
    progress_data[user_id]["category_points"].setdefault(category.lower(), 0)
    progress_data[user_id]["category_points"][category.lower()] += points
    today = datetime.now().strftime("%Y-%m-%d")
    if progress_data[user_id]["last_activity"] != today:
        progress_data[user_id]["streak"] += 1
        progress_data[user_id]["last_activity"] = today
    if progress_data[user_id]["streak"] > 2:
        points = int(points * 1.5)
        progress_data[user_id]["points"] = int(progress_data[user_id]["points"] * 1.5)
    if challenges["current"] and challenges["date"] == today and challenges["current"]["type"] == "project_guru" and category.lower() == challenges["current"]["requirements"]["category"]:
        challenges["user_progress"].setdefault(user_id, {})
        challenges["user_progress"][user_id]["project_submitted"] = True
    save_json(CHALLENGES_FILE, challenges)
    save_json(PROGRESS_FILE, progress_data)
    await check_roles(interaction.user)
    await interaction.response.send_message(f"✅ Project submitted! (+{points} points)", ephemeral=True)

@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return
    message = reaction.message
    if message.author == bot.user and reaction.emoji == "👍":
        embed = message.embeds[0] if message.embeds else None
        if not embed:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        user_id = str(user.id)
        progress_data.setdefault(user_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
        for p in projects:
            if p["timestamp"] in embed.footer.text:
                p["upvotes"] += 1
                save_json(PROJECTS_FILE, projects)
                if challenges["current"] and challenges["date"] == today and challenges["current"]["type"] == "project_guru" and p["category"] == challenges["current"]["requirements"]["category"]:
                    proj_user_id = p["user_id"]
                    challenges["user_progress"].setdefault(proj_user_id, {})
                    challenges["user_progress"][proj_user_id]["upvotes"] = p["upvotes"]
                    if p["upvotes"] >= challenges["current"]["requirements"]["upvotes"]:
                        progress_data[proj_user_id]["points"] += challenges["current"]["points"]
                        progress_data[proj_user_id]["category_points"].setdefault(p["category"], 0)
                        progress_data[proj_user_id]["category_points"][p["category"]] += challenges["current"]["points"]
                        await bot.get_channel(ANNOUNCEMENT_CHANNEL_ID).send(f"🎉 <@{proj_user_id}> completed daily challenge! +{challenges['current']['points']} points")
                    save_json(CHALLENGES_FILE, challenges)
                    save_json(PROGRESS_FILE, progress_data)
                    await check_roles(await bot.fetch_user(int(proj_user_id)))
                break

# =============================
# To-Do Commands
# =============================
@tree.command(name="todo_add", description="Add a task with category and optional due date")
@app_commands.describe(task="Task description", category="Category: cybersecurity, blender, webdev, blockchain, general", due_date="Due date (YYYY-MM-DD, optional)")
async def todo_add(interaction: discord.Interaction, task: str, category: str = "general", due_date: str = None):
    valid_categories = ["cybersecurity", "blender", "webdev", "blockchain", "general"]
    if category.lower() not in valid_categories:
        await interaction.response.send_message("❌ Invalid category. Use: cybersecurity, blender, webdev, blockchain, general.", ephemeral=True)
        return
    if due_date:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            await interaction.response.send_message("❌ Invalid due date format. Use YYYY-MM-DD.", ephemeral=True)
            return
    user_id = str(interaction.user.id)
    tasks_data.setdefault(user_id, []).append({
        "task": task,
        "category": category.lower(),
        "due_date": due_date,
        "completed": False,
        "progress": "not_started",
        "notes": ""
    })
    save_json(TASKS_FILE, tasks_data)
    await interaction.response.send_message(f"📝 Task added: {task} ({category})" + (f", due {due_date}" if due_date else ""), ephemeral=True)

@tree.command(name="todo_add_user", description="Assign a task with category and due date (mod only)")
@is_mod()
@app_commands.describe(user="User to assign", task="Task description", category="Category: cybersecurity, blender, webdev, blockchain, general", due_date="Due date (YYYY-MM-DD, optional)")
async def todo_add_user(interaction: discord.Interaction, user: discord.Member, task: str, category: str = "general", due_date: str = None):
    valid_categories = ["cybersecurity", "blender", "webdev", "blockchain", "general"]
    if category.lower() not in valid_categories:
        await interaction.response.send_message("❌ Invalid category.", ephemeral=True)
        return
    if due_date:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            await interaction.response.send_message("❌ Invalid due date format.", ephemeral=True)
            return
    user_id = str(user.id)
    tasks_data.setdefault(user_id, []).append({
        "task": task,
        "category": category.lower(),
        "due_date": due_date,
        "completed": False,
        "progress": "not_started",
        "notes": ""
    })
    save_json(TASKS_FILE, tasks_data)
    try:
        await user.send(f"👾 Task assigned: {task} ({category})" + (f", due {due_date}" if due_date else ""))
    except:
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        await channel.send(f"👾 {user.mention}, Task assigned: {task} ({category})" + (f", due {due_date}" if due_date else ""))
    await interaction.response.send_message(f"✅ Task assigned to {user.mention}: {task}")

@tree.command(name="todo_update", description="Update task progress or notes")
@app_commands.describe(task_number="Task number from /todo_list", progress="Progress: not_started, in_progress", notes="Optional notes")
async def todo_update(interaction: discord.Interaction, task_number: int, progress: str = None, notes: str = None):
    user_id = str(interaction.user.id)
    if user_id not in tasks_data or task_number < 1 or task_number > len(tasks_data[user_id]):
        await interaction.response.send_message("❌ Invalid task number.", ephemeral=True)
        return
    task = tasks_data[user_id][task_number - 1]
    if progress and progress.lower() in ["not_started", "in_progress"]:
        task["progress"] = progress.lower()
    if notes:
        task["notes"] = notes
    save_json(TASKS_FILE, tasks_data)
    await interaction.response.send_message(f"✅ Updated task {task_number}: {task['task']}", ephemeral=True)

@tree.command(name="todo_list", description="List your tasks")
async def todo_list(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in tasks_data or not tasks_data[user_id]:
        await interaction.response.send_message("✅ No tasks!", ephemeral=True)
        return
    embed = discord.Embed(title="📝 Your Tasks", color=0x00FF00)
    for i, t in enumerate(tasks_data[user_id]):
        status = "✅" if t["completed"] else "🏃" if t["progress"] == "in_progress" else "❌"
        embed.add_field(
            name=f"{i+1}. {t['task']} ({t['category'].title()})",
            value=f"Status: {status} | Progress: {t['progress'].title()}" + 
                  (f"\nDue: {t['due_date']}" if t['due_date'] else "") +
                  (f"\nNotes: {t['notes']}" if t['notes'] else ""),
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="todo_list_user", description="List tasks of another user (mod only)")
@is_mod()
@app_commands.describe(user="User whose tasks to view")
async def todo_list_user(interaction: discord.Interaction, user: discord.Member):
    user_id = str(user.id)
    if user_id not in tasks_data or not tasks_data[user_id]:
        await interaction.response.send_message(f"✅ {user.mention} has no tasks.")
        return
    embed = discord.Embed(title=f"📝 Tasks for {user.name}", color=0x00FF00)
    for i, t in enumerate(tasks_data[user_id]):
        status = "✅" if t["completed"] else "🏃" if t["progress"] == "in_progress" else "❌"
        embed.add_field(
            name=f"{i+1}. {t['task']} ({t['category'].title()})",
            value=f"Status: {status} | Progress: {t['progress'].title()}" + 
                  (f"\nDue: {t['due_date']}" if t['due_date'] else "") +
                  (f"\nNotes: {t['notes']}" if t['notes'] else ""),
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@tree.command(name="todo_complete", description="Mark a task as completed")
@app_commands.describe(number="Task number from your list")
async def todo_complete(interaction: discord.Interaction, number: int):
    user_id = str(interaction.user.id)
    if user_id not in tasks_data or number < 1 or number > len(tasks_data[user_id]):
        await interaction.response.send_message("❌ Invalid task number.", ephemeral=True)
        return
    task = tasks_data[user_id][number - 1]
    tasks_data[user_id][number - 1]["completed"] = True
    reminder_key = f"{user_id}_{number}"
    if reminder_key in reminders:
        del reminders[reminder_key]
        save_json(REMINDERS_FILE, reminders)
    save_json(TASKS_FILE, tasks_data)
    points = 5 + CATEGORY_BONUSES.get(task["category"], 0)
    progress_data.setdefault(user_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    progress_data[user_id]["points"] += points
    progress_data[user_id]["category_points"].setdefault(task["category"], 0)
    progress_data[user_id]["category_points"][task["category"]] += points
    today = datetime.now().strftime("%Y-%m-%d")
    if progress_data[user_id]["last_activity"] != today:
        progress_data[user_id]["streak"] += 1
        progress_data[user_id]["last_activity"] = today
    if progress_data[user_id]["streak"] > 2:
        points = int(points * 1.5)
        progress_data[user_id]["points"] = int(progress_data[user_id]["points"] * 1.5)
    save_json(PROGRESS_FILE, progress_data)
    await check_roles(interaction.user)
    await interaction.response.send_message(f"✅ Task completed: {task['task']} (+{points} points, Streak: {progress_data[user_id]['streak']})")

@tree.command(name="todo_clear", description="Clear all tasks (mod only)")
@is_mod()
async def todo_clear(interaction: discord.Interaction):
    tasks_data.clear()
    reminders.clear()
    save_json(TASKS_FILE, tasks_data)
    save_json(REMINDERS_FILE, reminders)
    await interaction.response.send_message("🗑️ All tasks and reminders cleared!")

# =============================
# Reminder Commands
# =============================
@tree.command(name="remind", description="Set a reminder for a task or goal")
@app_commands.describe(task_number="Task number from /todo_list (0 for standalone)", message="Reminder message (if standalone)", interval="Reminder interval: 30min, 2hours, daily")
async def remind(interaction: discord.Interaction, task_number: int = 0, message: str = None, interval: str = "daily"):
    valid_intervals = ["30min", "2hours", "daily"]
    if interval.lower() not in valid_intervals:
        await interaction.response.send_message("❌ Invalid interval. Use: 30min, 2hours, daily.", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    if task_number == 0 and not message:
        await interaction.response.send_message("❌ Provide a message for standalone reminders.", ephemeral=True)
        return
    if task_number > 0:
        if user_id not in tasks_data or task_number < 1 or task_number > len(tasks_data[user_id]):
            await interaction.response.send_message("❌ Invalid task number.", ephemeral=True)
            return
        task = tasks_data[user_id][task_number - 1]["task"]
        reminder_key = f"{user_id}_{task_number}"
    else:
        task = message
        reminder_key = f"{user_id}_{datetime.now().isoformat()}"
    
    reminders[reminder_key] = {
        "user_id": user_id,
        "task": task,
        "interval": interval.lower(),
        "reminder_count": 0,
        "max_reminders": 5,
        "last_reminder": "2020-01-01T00:00:00",
        "task_number": task_number
    }
    save_json(REMINDERS_FILE, reminders)
    await interaction.response.send_message(f"🔔 Reminder set for: {task} ({interval})", ephemeral=True)

@tree.command(name="remind_user", description="Set a reminder for another user’s task (mod only)")
@is_mod()
@app_commands.describe(user="User to remind", task_number="Task number from /todo_list_user (0 for standalone)", message="Reminder message (if standalone)", interval="Reminder interval: 30min, 2hours, daily")
async def remind_user(interaction: discord.Interaction, user: discord.Member, task_number: int = 0, message: str = None, interval: str = "daily"):
    valid_intervals = ["30min", "2hours", "daily"]
    if interval.lower() not in valid_intervals:
        await interaction.response.send_message("❌ Invalid interval. Use: 30min, 2hours, daily.", ephemeral=True)
        return
    user_id = str(user.id)
    if task_number == 0 and not message:
        await interaction.response.send_message("❌ Provide a message for standalone reminders.", ephemeral=True)
        return
    if task_number > 0:
        if user_id not in tasks_data or task_number < 1 or task_number > len(tasks_data[user_id]):
            await interaction.response.send_message("❌ Invalid task number.", ephemeral=True)
            return
        task = tasks_data[user_id][task_number - 1]["task"]
    else:
        task = message
    reminder_key = f"{user_id}_{task_number or datetime.now().isoformat()}"
    reminders[reminder_key] = {
        "user_id": user_id,
        "task": task,
        "interval": interval.lower(),
        "reminder_count": 0,
        "max_reminders": 5,
        "last_reminder": "2020-01-01T00:00:00",
        "task_number": task_number
    }
    save_json(REMINDERS_FILE, reminders)
    try:
        await user.send(f"🔔 Reminder set: {task} ({interval})")
    except:
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        await channel.send(f"🔔 {user.mention}, Reminder set: {task} ({interval})")
    await interaction.response.send_message(f"✅ Reminder set for {user.mention}: {task}")

@tasks.loop(minutes=15)
async def send_reminders():
    now = datetime.now()
    for reminder_key, data in reminders.copy().items():
        if data["reminder_count"] >= data["max_reminders"]:
            continue
        user_id = data["user_id"]
        if data["task_number"] > 0 and user_id in tasks_data and data["task_number"] <= len(tasks_data[user_id]):
            if tasks_data[user_id][data["task_number"] - 1]["completed"]:
                del reminders[reminder_key]
                save_json(REMINDERS_FILE, reminders)
                continue
        last_reminder = datetime.fromisoformat(data["last_reminder"])
        interval_minutes = {"30min": 30, "2hours": 120, "daily": 1440}
        if (now - last_reminder).total_seconds() / 60 >= interval_minutes[data["interval"]]:
            user = await bot.fetch_user(int(user_id))
            try:
                await user.send(f"⏰ Reminder: {data['task']}")
            except:
                channel = bot.get_channel(REMINDER_CHANNEL_ID)
                await channel.send(f"⏰ {user.mention}, Reminder: {data['task']}")
            data["reminder_count"] += 1
            data["last_reminder"] = now.isoformat()
            save_json(REMINDERS_FILE, reminders)

@tasks.loop(hours=24)
async def task_due_notifications():
    now = datetime.now()
    for user_id, tasks in tasks_data.items():
        user = await bot.fetch_user(int(user_id))
        for i, task in enumerate(tasks):
            if task["due_date"] and not task["completed"]:
                due = datetime.strptime(task["due_date"], "%Y-%m-%d")
                if (due - now).days <= 1:
                    try:
                        await user.send(f"⏳ Task due soon: {task['task']} (Due: {task['due_date']})")
                    except:
                        channel = bot.get_channel(REMINDER_CHANNEL_ID)
                        await channel.send(f"⏳ {user.mention}, Task due soon: {task['task']} (Due: {task['due_date']})")

# =============================
# Event Commands
# =============================

# =============================
# Quiz Commands with OpenRouter
# =============================
async def generate_ai_question(category: str, difficulty: str = "medium"):
    if not client:
        print("OpenRouter client not initialized. Check OPENROUTER_API_KEY in .env")
        return None
    models = [
        "mistralai/mistral-7b-instruct:free",
        "deepseek/deepseek-chat-v3.1:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "z-ai/glm-4.5-air:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
    ]
    prompt = (
        f"You are a quiz master for a tech learning server. Generate a single multiple-choice question (MCQ) on {category}. "
        f"Make it educational for beginners in Cybersecurity, Blender, Web Dev, Blockchain, or NFTs. "
        f"Difficulty: {difficulty}. For blockchain, include NFT-related questions (e.g., Moana NFT minting).\n"
        "Output ONLY valid JSON in this exact format: "
        "{ 'question': 'The question text?', 'options': ['1. Option A', '2. Option B', '3. Option C', '4. Option D'], 'answer': 1 }\n"
        "Rules: 1. Provide exactly 4 options, each starting with its number (e.g., '1. ...'). 2. Only one option is correct. 3. The answer field must be an integer 1-4 matching the correct option. 4. Do not include explanations or any extra text. 5. Output only valid JSON, no markdown or commentary."
    )
    for model in models:
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Generate a question for: {category}. Difficulty: {difficulty}."}
                ],
                max_tokens=200,
                temperature=0.7
            )
            generated_text = response.choices[0].message.content.strip()
            try:
                q = json.loads(generated_text)
            except json.JSONDecodeError:
                fixed_text = generated_text.replace("'", '"')
                try:
                    q = json.loads(fixed_text)
                except json.JSONDecodeError:
                    print(f"AI generation failed for {category} (model {model}): Invalid JSON - {generated_text}")
                    continue
            if not all(k in q for k in ["question", "options", "answer"]) or not isinstance(q["options"], list) or len(q["options"]) != 4 or q["answer"] not in [1, 2, 3, 4]:
                print(f"Invalid AI question format for {category} (model {model}): {generated_text}")
                continue
            q["ai_generated"] = True
            q["difficulty"] = difficulty.lower()
            quizzes.setdefault(category.lower(), []).append(q)
            save_json(QUIZZES_FILE, quizzes)
            print(f"Generated AI question for {category} ({difficulty}) using {model}: {q['question']}")
            return q
        except Exception as e:
            print(f"OpenRouter API error for {category} (model {model}): {e}")
            continue
    return {"question": f"Failed to generate {category} question.", "options": ["1. N/A", "2. N/A", "3. N/A", "4. N/A"], "answer": 1, "ai_generated": False}

@tree.command(name="quiz", description="Answer one or more AI-generated quiz questions by category (in #game channel only)")
@app_commands.describe(category="Topic: cybersecurity, blender, webdev, blockchain, general", questions="Number of questions (max 20)", difficulty="Difficulty: easy, medium, hard")
async def quiz(interaction: discord.Interaction, category: str = "general", questions: int = 1, difficulty: str = "medium"):
    print(f"Quiz command invoked by {interaction.user.id} in channel {interaction.channel.id}")
    if interaction.channel.id != GAME_CHANNEL_ID:
        await interaction.response.send_message(f"❌ Use this in <#{GAME_CHANNEL_ID}> only.", ephemeral=True)
        print(f"Quiz failed: Wrong channel {interaction.channel.id}")
        return
    await interaction.response.defer(ephemeral=True)
    category = category.lower()
    valid_categories = ["cybersecurity", "blender", "webdev", "blockchain", "general"]
    valid_difficulties = ["easy", "medium", "hard"]
    if category not in valid_categories:
        await interaction.followup.send(f"❌ Invalid topic. Try: {', '.join(valid_categories)}.", ephemeral=True)
        print(f"Quiz failed: Invalid category {category}")
        return
    if difficulty.lower() not in valid_difficulties:
        await interaction.followup.send(f"❌ Invalid difficulty. Try: {', '.join(valid_difficulties)}.", ephemeral=True)
        print(f"Quiz failed: Invalid difficulty {difficulty}")
        return
    questions = max(1, min(questions, 20))
    user_id = str(interaction.user.id)
    progress_data.setdefault(user_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    today = datetime.now().strftime("%Y-%m-%d")
    if progress_data[user_id]["last_activity"] != today:
        progress_data[user_id]["streak"] += 1
        progress_data[user_id]["last_activity"] = today
    total_points = 0
    correct = 0
    seen_questions = set()
    import re
    def normalize_question(text):
        return re.sub(r'[^a-z0-9 ]', '', text.lower())
    for q_num in range(1, questions + 1):
        tries = 0
        question = None
        norm = None
        while tries < 5:
            question = await generate_ai_question(category, difficulty)
            if not question or question.get("question", "").startswith("Failed to generate"):
                tries += 1
                continue
            norm = normalize_question(question["question"])
            if norm in seen_questions:
                tries += 1
                continue
            seen_questions.add(norm)
            break
        if not question or question.get("question", "").startswith("Failed to generate") or norm in seen_questions:
            await interaction.followup.send(f"❌ No valid unique AI quiz question available for {category} (Q{q_num}). Try again later or with a different category/difficulty.", ephemeral=True)
            print(f"No valid unique AI quiz question for {category} (Q{q_num})")
            continue
        await interaction.followup.send(f"🧩 Quiz {q_num}/{questions} ({category.title()}, {difficulty.title()})!\n**{question['question']}**\n" + "\n".join(question["options"]))
        print(f"Quiz question {q_num} posted for {user_id}: {question['question']}")
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit() and 1 <= int(m.content) <= 4
        try:
            msg = await bot.wait_for("message", check=check, timeout=20)
            points = 0
            if int(msg.content) == question["answer"]:
                points = 2 + (5 if question.get("ai_generated", False) else 0)
                progress_data[user_id]["points"] += points
                progress_data[user_id]["category_points"].setdefault(category, 0)
                progress_data[user_id]["category_points"][category] += points
                if progress_data[user_id]["streak"] > 2:
                    points = int(points * 1.5)
                    progress_data[user_id]["points"] = int(progress_data[user_id]["points"] * 1.5)
                await interaction.followup.send(f"✅ Correct, {interaction.user.mention}! 🎉 (+{points} points)")
                correct += 1
                total_points += points
            else:
                await interaction.followup.send(f"❌ Wrong, {interaction.user.mention}. Correct: {question['options'][question['answer']-1]}.")
            if challenges["current"] and challenges["date"] == today and challenges["current"]["type"] == "quiz_master":
                challenges["user_progress"].setdefault(user_id, {"quiz_score": 0, "num_questions": 0})
                challenges["user_progress"][user_id]["num_questions"] += 1
                challenges["user_progress"][user_id]["quiz_score"] += 1 if int(msg.content) == question["answer"] else 0
                total_qs = challenges["user_progress"][user_id]["num_questions"]
                score = challenges["user_progress"][user_id]["quiz_score"] / total_qs if total_qs > 0 else 0
                if score >= challenges["current"]["requirements"]["quiz_score"] and total_qs >= challenges["current"]["requirements"]["num_questions"]:
                    progress_data[user_id]["points"] += challenges["current"]["points"]
                    progress_data[user_id]["category_points"][category] += challenges["current"]["points"]
                    await interaction.followup.send(f"🎉 Completed daily challenge! +{challenges['current']['points']} points")
            save_json(PROGRESS_FILE, progress_data)
            save_json(CHALLENGES_FILE, challenges)
            await check_roles(interaction.user)
            print(f"Quiz completed for user {user_id} in {category}: {'Correct' if int(msg.content) == question['answer'] else 'Wrong'}, +{points} points")
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⌛ Time’s up, {interaction.user.mention}! Correct: {question['options'][question['answer']-1]}.")
            print(f"Quiz timed out for user {user_id} in {category} (Q{q_num})")
    await interaction.followup.send(f"🏁 Quiz session complete! You answered {correct}/{questions} correctly and earned {total_points} points.", ephemeral=True)

# =============================
# Challenge a Friend Quiz Helpers
# =============================
async def create_challenge_thread(channel, challenger, friend, category, questions, difficulty):
    thread_name = f"Quiz Duel: {challenger.display_name} vs {friend.display_name}"
    thread = await channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread, invitable=False)
    await thread.add_user(challenger)
    await thread.add_user(friend)
    await thread.send(f"👾 {challenger.mention} has challenged {friend.mention} to a {questions}-question quiz duel in {category.title()} (difficulty: {difficulty.title()})! {friend.mention}, type 'accept' to play or 'decline' to ignore.")
    return thread

async def await_challenge_acceptance(bot, thread, friend):
    def check(m):
        return m.channel == thread and m.author == friend and m.content.lower() in ["accept", "decline"]
    try:
        reply = await bot.wait_for("message", check=check, timeout=60)
        if reply.content.lower() == "decline":
            await thread.send(f"❌ {friend.mention} declined the challenge.")
            return False
        await thread.send(f"✅ Challenge accepted! The quiz will begin shortly.")
        return True
    except asyncio.TimeoutError:
        await thread.send(f"⌛ {friend.mention} did not respond in time. Challenge cancelled.")
        return False

async def run_quiz_duel_session(bot, thread, challenger, friend, category, questions, difficulty):
    challenger_id = str(challenger.id)
    friend_id = str(friend.id)
    progress_data.setdefault(challenger_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    progress_data.setdefault(friend_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    today = datetime.now().strftime("%Y-%m-%d")
    if progress_data[challenger_id]["last_activity"] != today:
        progress_data[challenger_id]["streak"] += 1
        progress_data[challenger_id]["last_activity"] = today
    if progress_data[friend_id]["last_activity"] != today:
        progress_data[friend_id]["streak"] += 1
        progress_data[friend_id]["last_activity"] = today
    challenger_score = 0
    friend_score = 0
    seen_questions = set()
    import re
    def normalize_question(text):
        return re.sub(r'[^a-z0-9 ]', '', text.lower())
    for q_num in range(1, questions + 1):
        tries = 0
        while tries < 5:
            question = await generate_ai_question(category, difficulty)
            if not question or question["question"].startswith("Failed to generate"):
                tries += 1
                continue
            norm = normalize_question(question["question"])
            if norm in seen_questions:
                tries += 1
                continue
            seen_questions.add(norm)
            break
        if not question or question["question"].startswith("Failed to generate") or norm in seen_questions:
            await thread.send(f"❌ No valid unique question for Q{q_num}. Skipping to next or ending duel.")
            print(f"No valid unique question for duel Q{q_num} ({category}, {difficulty})")
            continue
        await thread.send(f"🧩 Duel Question {q_num}/{questions} ({category.title()}, {difficulty.title()})\n**{question['question']}**\n" + "\n".join(question["options"]) + f"\n{challenger.mention} and {friend.mention}, reply with 1-4 within 20 seconds!")
        print(f"Duel question {q_num} posted: {question['question']}")
        challenger_answer = None
        friend_answer = None
        def check(m):
            return m.channel == thread and m.author in [challenger, friend] and m.content.isdigit() and 1 <= int(m.content) <= 4
        try:
            tasks = []
            while len(tasks) < 2:
                msg = await bot.wait_for("message", check=check, timeout=20 - (len(tasks) * 0.1))
                if msg.author == challenger and challenger_answer is None:
                    challenger_answer = int(msg.content)
                    tasks.append("challenger")
                elif msg.author == friend and friend_answer is None:
                    friend_answer = int(msg.content)
                    tasks.append("friend")
        except asyncio.TimeoutError:
            pass
        points = 2 + (5 if question.get("ai_generated", False) else 0)
        if challenger_answer == question["answer"]:
            challenger_score += 1
            progress_data[challenger_id]["points"] += points
            progress_data[challenger_id]["category_points"].setdefault(category, 0)
            progress_data[challenger_id]["category_points"][category] += points
            if progress_data[challenger_id]["streak"] > 2:
                progress_data[challenger_id]["points"] = int(progress_data[challenger_id]["points"] * 1.5)
            await thread.send(f"✅ {challenger.mention} got it right! (+{points} points)")
        else:
            await thread.send(f"❌ {challenger.mention} got it wrong." + (f" Answer: {challenger_answer}" if challenger_answer else ""))
        if friend_answer == question["answer"]:
            friend_score += 1
            progress_data[friend_id]["points"] += points
            progress_data[friend_id]["category_points"].setdefault(category, 0)
            progress_data[friend_id]["category_points"][category] += points
            if progress_data[friend_id]["streak"] > 2:
                progress_data[friend_id]["points"] = int(progress_data[friend_id]["points"] * 1.5)
            await thread.send(f"✅ {friend.mention} got it right! (+{points} points)")
        else:
            await thread.send(f"❌ {friend.mention} got it wrong." + (f" Answer: {friend_answer}" if friend_answer else ""))
        await thread.send(f"Correct: {question['options'][question['answer']-1]}")
        # Daily challenge check
        for user_id, user in [(challenger_id, challenger), (friend_id, friend)]:
            if challenges["current"] and challenges["date"] == today and challenges["current"]["type"] == "quiz_master":
                challenges["user_progress"].setdefault(user_id, {"quiz_score": 0, "num_questions": 0})
                challenges["user_progress"][user_id]["num_questions"] += 1
                challenges["user_progress"][user_id]["quiz_score"] += 1 if (challenger_answer if user_id == challenger_id else friend_answer) == question["answer"] else 0
                total_qs = challenges["user_progress"][user_id]["num_questions"]
                score = challenges["user_progress"][user_id]["quiz_score"] / total_qs if total_qs > 0 else 0
                if score >= challenges["current"]["requirements"]["quiz_score"] and total_qs >= challenges["current"]["requirements"]["num_questions"]:
                    progress_data[user_id]["points"] += challenges["current"]["points"]
                    progress_data[user_id]["category_points"][category] += challenges["current"]["points"]
                    await thread.send(f"🎉 {user.mention} completed daily challenge! +{challenges['current']['points']} points")
        save_json(PROGRESS_FILE, progress_data)
        save_json(CHALLENGES_FILE, challenges)
        await check_roles(challenger)
        await check_roles(friend)
        print(f"Duel Q{q_num}: {challenger.name} ({'Correct' if challenger_answer == question['answer'] else 'Wrong'}), {friend.name} ({'Correct' if friend_answer == question['answer'] else 'Wrong'})")
        await asyncio.sleep(2)
    winner = (
        challenger if challenger_score > friend_score else
        friend if friend_score > challenger_score else
        None
    )
    result = (
        f"🏆 {winner.mention} wins {challenger_score}-{friend_score}! (+10 bonus points)" if winner
        else f"🤝 It's a tie at {challenger_score}-{friend_score}!"
    )
    if winner:
        winner_id = str(winner.id)
        progress_data[winner_id]["points"] += 10
        progress_data[winner_id]["category_points"].setdefault(category, 0)
        progress_data[winner_id]["category_points"][category] += 10
        save_json(PROGRESS_FILE, progress_data)
        await check_roles(winner)
    await thread.send(f"🏁 Duel complete! {challenger.mention}: {challenger_score}, {friend.mention}: {friend_score}. {result}")
    print(f"Duel complete: {challenger.name} ({challenger_score}) vs {friend.name} ({friend_score})")
    try:
        await thread.edit(archived=True, locked=True)
    except Exception as e:
        print(f"Failed to archive thread: {e}")

@tree.command(name="challenge_friend", description="Challenge a friend to a quiz duel!")
@app_commands.describe(
    friends="Tag up to 5 users to challenge (separate with spaces)",
    category="Quiz category: cybersecurity, blender, webdev, blockchain, general",
    questions="Number of questions (max 10)",
    difficulty="Difficulty: easy, medium, hard"
)
async def challenge_friend(
    interaction: discord.Interaction,
    friends: str,
    category: str = "general",
    questions: int = 5,
    difficulty: str = "medium"
):
    valid_categories = ["cybersecurity", "blender", "webdev", "blockchain", "general"]
    valid_difficulties = ["easy", "medium", "hard"]
    await interaction.response.defer(ephemeral=True)
    if category.lower() not in valid_categories:
        await interaction.followup.send(f"❌ Invalid category. Choose from: {', '.join(valid_categories)}.", ephemeral=True)
        return
    if difficulty.lower() not in valid_difficulties:
        await interaction.followup.send(f"❌ Invalid difficulty. Choose from: {', '.join(valid_difficulties)}.", ephemeral=True)
        return
    questions = max(1, min(questions, 10))
    # Parse mentions (expecting <@id> format)
    friend_ids = [int(fid.strip('<@!>')) for fid in friends.split() if fid.strip('<@!>').isdigit()]
    if not friend_ids or len(friend_ids) > 5:
        await interaction.followup.send("❌ Tag 1-5 real users to challenge.", ephemeral=True)
        return
    if interaction.user.id in friend_ids:
        await interaction.followup.send("❌ You cannot challenge yourself!", ephemeral=True)
        return
    channel = interaction.channel
    # Fetch member objects
    guild = interaction.guild
    friend_members = [guild.get_member(fid) for fid in friend_ids if guild.get_member(fid) and not guild.get_member(fid).bot]
    if not friend_members or len(friend_members) != len(friend_ids):
        await interaction.followup.send("❌ All challenged users must be real, non-bot members.", ephemeral=True)
        return
    if interaction.channel.id != GAME_CHANNEL_ID:
        await interaction.followup.send(f"❌ Use this in <#{GAME_CHANNEL_ID}> only.", ephemeral=True)
        print(f"Challenge failed: Wrong channel {interaction.channel.id}")
        return
    # Create thread and add all users
    thread_name = f"Quiz Duel: {interaction.user.display_name} vs {'/'.join([m.display_name for m in friend_members])}"
    thread = await channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread, invitable=False)
    await thread.add_user(interaction.user)
    for m in friend_members:
        await thread.add_user(m)
    await thread.send(f"👾 {interaction.user.mention} has challenged {' '.join([m.mention for m in friend_members])} to a {questions}-question quiz duel in {category.title()} (difficulty: {difficulty.title()})! Each, type 'accept' to play or 'decline' to ignore.")
    # Wait for all to accept
    accepted = []
    for m in friend_members:
        def check(msg, member=m):
            return msg.channel == thread and msg.author == member and msg.content.lower() in ["accept", "decline"]
        try:
            reply = await bot.wait_for("message", check=check, timeout=60)
            if reply.content.lower() == "accept":
                accepted.append(m)
            else:
                await thread.send(f"❌ {m.mention} declined the challenge.")
        except asyncio.TimeoutError:
            await thread.send(f"⌛ {m.mention} did not respond in time. Challenge cancelled for them.")
    if not accepted:
        await thread.send("❌ No one accepted the challenge. Duel cancelled.")
        await thread.edit(archived=True, locked=True)
        return
    await thread.send(f"✅ Challenge accepted by: {' '.join([m.mention for m in accepted])}! The quiz will begin shortly.")
    await run_group_quiz_duel_session(bot, thread, [interaction.user] + accepted, category, questions, difficulty)

# Group duel session logic
async def run_group_quiz_duel_session(bot, thread, players, category, questions, difficulty):
    ids = [str(p.id) for p in players]
    for pid in ids:
        progress_data.setdefault(pid, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    today = datetime.now().strftime("%Y-%m-%d")
    for pid in ids:
        if progress_data[pid]["last_activity"] != today:
            progress_data[pid]["streak"] += 1
            progress_data[pid]["last_activity"] = today
    scores = {pid: 0 for pid in ids}
    seen_questions = set()
    import re
    def normalize_question(text):
        return re.sub(r'[^a-z0-9 ]', '', text.lower())
    for q_num in range(1, questions + 1):
        tries = 0
        question = None
        norm = None
        while tries < 5:
            question = await generate_ai_question(category, difficulty)
            if not question or question["question"].startswith("Failed to generate"):
                tries += 1
                continue
            norm = normalize_question(question["question"])
            if norm in seen_questions:
                tries += 1
                continue
            seen_questions.add(norm)
            break
        # Fallback to stored questions if all AI fail
        if not question or question["question"].startswith("Failed to generate") or norm in seen_questions:
            available = [q for q in quizzes.get(category, []) if q.get("difficulty", "medium") == difficulty.lower() and normalize_question(q["question"]) not in seen_questions]
            if available:
                question = random.choice(available)
                norm = normalize_question(question["question"])
                seen_questions.add(norm)
            else:
                await thread.send(f"❌ No valid unique quiz question for Q{q_num}. Skipping.")
                continue
        await thread.send(f"🧩 Group Duel Q{q_num}/{questions} ({category.title()}, {difficulty.title()})\n**{question['question']}**\n" + "\n".join(question["options"]) + f"\nPlayers: {' '.join([p.mention for p in players])}, reply with 1-4 within 20 seconds!")
        answers = {}
        def check(m):
            return m.channel == thread and m.author in players and m.content.isdigit() and 1 <= int(m.content) <= 4 and m.author.id not in answers
        try:
            while len(answers) < len(players):
                msg = await bot.wait_for("message", check=check, timeout=20)
                answers[msg.author.id] = int(msg.content)
        except asyncio.TimeoutError:
            pass
        points = 2 + (5 if question.get("ai_generated", False) else 0)
        for p in players:
            pid = str(p.id)
            if answers.get(p.id) == question["answer"]:
                scores[pid] += 1
                progress_data[pid]["points"] += points
                progress_data[pid]["category_points"].setdefault(category, 0)
                progress_data[pid]["category_points"][category] += points
                if progress_data[pid]["streak"] > 2:
                    progress_data[pid]["points"] = int(progress_data[pid]["points"] * 1.5)
                await thread.send(f"✅ {p.mention} got it right! (+{points} points)")
            else:
                await thread.send(f"❌ {p.mention} got it wrong." + (f" Answer: {answers.get(p.id)}" if answers.get(p.id) else ""))
        await thread.send(f"Correct: {question['options'][question['answer']-1]}")
    # Results
    winner_ids = [pid for pid, score in scores.items() if score == max(scores.values())]
    winners = [p for p in players if str(p.id) in winner_ids]
    result = (
        f"🏆 {' & '.join([w.mention for w in winners])} win(s) with {max(scores.values())} points! (+10 bonus points each)"
        if winners else f"🤝 It's a tie!"
    )
    for w in winners:
        wid = str(w.id)
        progress_data[wid]["points"] += 10
        progress_data[wid]["category_points"].setdefault(category, 0)
        progress_data[wid]["category_points"][category] += 10
        await check_roles(w)
    save_json(PROGRESS_FILE, progress_data)
    await thread.send(f"🏁 Group Duel complete! {result}")
    try:
        await thread.edit(archived=True, locked=True)
        await thread.delete()
    except Exception as e:
        print(f"Failed to archive or delete thread: {e}")

@tree.command(name="quiz_add", description="Add a quiz question (mod only)")
@is_mod()
@app_commands.describe(topic="Topic: cybersecurity, blender, webdev, blockchain, general", question="Question text", option1="Option 1", option2="Option 2", option3="Option 3", option4="Option 4", answer="Correct option (1-4)", difficulty="Difficulty: easy, medium, hard")
async def quiz_add(interaction: discord.Interaction, topic: str, question: str, option1: str, option2: str, option3: str, option4: str, answer: int, difficulty: str = "medium"):
    valid_categories = ["cybersecurity", "blender", "webdev", "blockchain", "general"]
    valid_difficulties = ["easy", "medium", "hard"]
    if topic.lower() not in valid_categories:
        await interaction.response.send_message("❌ Invalid topic.", ephemeral=True)
        return
    if difficulty.lower() not in valid_difficulties:
        await interaction.response.send_message("❌ Invalid difficulty.", ephemeral=True)
        return
    if answer not in [1, 2, 3, 4]:
        await interaction.response.send_message("❌ Answer must be 1-4.", ephemeral=True)
        return
    quizzes[topic.lower()].append({
        "question": question,
        "options": [f"1. {option1}", f"2. {option2}", f"3. {option3}", f"4. {option4}"],
        "answer": answer,
        "ai_generated": False,
        "difficulty": difficulty.lower()
    })
    save_json(QUIZZES_FILE, quizzes)
    await interaction.response.send_message(f"✅ Added quiz question to {topic} ({difficulty}).", ephemeral=True)

@tree.command(name="sync", description="Force sync bot commands")
async def sync(interaction: discord.Interaction):
    try:
        await tree.sync(guild=discord.Object(id=interaction.guild.id))
        await interaction.response.send_message("✅ Commands synced for this server!", ephemeral=True)
        print(f"Commands synced for guild {interaction.guild.id} by {interaction.user.id}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Sync failed: {e}", ephemeral=True)
        print(f"Sync error for guild {interaction.guild.id}: {e}")

# =============================
# Daily Challenges
# =============================
HARD_CHALLENGES = [
    {
        "type": "quiz_master",
        "task": "Score 80%+ on 5 quizzes in any category",
        "requirements": {"quiz_score": 0.8, "num_questions": 5},
        "points": 20,
        "category": None
    },
    {
        "type": "project_guru",
        "task": "Submit a blockchain project with 2+ upvotes",
        "requirements": {"category": "blockchain", "upvotes": 2},
        "points": 25,
        "category": "blockchain"
    },
    {
        "type": "resource_hunter",
        "task": "Add a featured resource and get 3+ upvotes",
        "requirements": {"featured": True, "upvotes": 3},
        "points": 15,
        "category": None
    }
]

@tasks.loop(hours=24)
async def generate_daily_challenge():
    challenges["date"] = datetime.now().strftime("%Y-%m-%d")
    challenges["current"] = random.choice(HARD_CHALLENGES)
    challenges["user_progress"] = {}
    save_json(CHALLENGES_FILE, challenges)
    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    await channel.send(f"🌟 **Daily Challenge ({challenges['date']}):** {challenges['current']['task']} (+{challenges['current']['points']} points)")

@tree.command(name="daily_challenge", description="View the current daily challenge and your progress")
async def daily_challenge(interaction: discord.Interaction):
    if not challenges["current"]:
        await interaction.response.send_message("❌ No challenge today. Check back later!", ephemeral=True)
        return
    user_id = str(interaction.user.id)
    progress = challenges["user_progress"].get(user_id, {})
    embed = discord.Embed(title=f"🌟 Daily Challenge ({challenges['date']})", description=challenges["current"]["task"], color=0xFFD700)
    embed.add_field(name="Reward", value=f"+{challenges['current']['points']} points", inline=False)
    if progress:
        embed.add_field(name="Your Progress", value=", ".join([f"{k}: {v}" for k, v in progress.items()]) or "None", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# =============================
# Gamification Commands
# =============================
@tree.command(name="progress", description="Check your points and roles")
@app_commands.describe(user="User to check (optional)")
async def progress(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    user_id = str(target.id)
    data = progress_data.get(user_id, {"points": 0, "category_points": {}, "streak": 0, "last_activity": None, "roles_assigned": [], "votes_today": {}})
    embed = discord.Embed(title=f"📊 Progress for {target.display_name}", color=0x3498DB)
    embed.add_field(name="Total Points", value=str(data["points"]), inline=False)
    embed.add_field(name="Streak", value=f"{data['streak']} days", inline=False)
    embed.add_field(name="Category Points", value=", ".join([f"{k}: {v}" for k, v in data["category_points"].items()]) or "None", inline=False)
    embed.add_field(name="Roles", value=", ".join(data["roles_assigned"]) or "None", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True if user is None else False)

@tree.command(name="leaderboard", description="View top users by points")
@app_commands.describe(limit="Number to show (max 10)")
async def leaderboard(interaction: discord.Interaction, limit: int = 5):
    sorted_users = sorted(progress_data.items(), key=lambda x: x[1]["points"], reverse=True)[:min(limit, 10)]
    embed = discord.Embed(title="🏆 Leaderboard", color=0xFFD700)
    for i, (uid, data) in enumerate(sorted_users, 1):
        user = await bot.fetch_user(int(uid))
        embed.add_field(name=f"{i}. {user.name}", value=f"{data['points']} points (Streak: {data['streak']})", inline=False)
    await interaction.response.send_message(embed=embed)

# =============================
# Moderation Commands
# =============================
@tree.command(name="kick", description="Kick a member")
@is_mod()
@app_commands.describe(member="Member to kick", reason="Reason for kick")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member} has been kicked. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to kick: {e}")

@tree.command(name="ban", description="Ban a member")
@is_mod()
@app_commands.describe(member="Member to ban", reason="Reason for ban")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 {member} has been banned. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to ban: {e}")

@tree.command(name="mute", description="Mute a member for X minutes")
@is_mod()
@app_commands.describe(member="Member to mute", minutes="Duration in minutes")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels:
            await channel.set_permissions(mute_role, speak=False, send_messages=False, add_reactions=False)
    await member.add_roles(mute_role)
    await interaction.response.send_message(f"🔇 {member.mention} muted for {minutes} minutes.")
    await asyncio.sleep(minutes * 60)
    await member.remove_roles(mute_role)
    await interaction.followup.send(f"🔊 {member.mention} unmuted.")

# =============================
# Status Rotation
# =============================
statuses = cycle([
    discord.Game("/help for commands"),
    discord.Activity(type=discord.ActivityType.watching, name="the server 👀"),
    discord.Activity(type=discord.ActivityType.listening, name="/todo and /quiz"),
    discord.Game("with cybersecurity puzzles 🛡️")
])

@tasks.loop(seconds=30)
async def change_status():
    await bot.change_presence(activity=next(statuses))

# =============================
# AI Tutor Command
# =============================
@tree.command(name="tutor", description="Ask the AI tutor to explain a concept or walk through a solution step-by-step.")
@app_commands.describe(question="What do you want explained? (e.g., 'Explain how blockchains work')")
async def tutor(interaction: discord.Interaction, question: str):
    await interaction.response.defer(ephemeral=True)
    if not client:
        await interaction.followup.send("❌ AI is not configured. Please contact an admin.", ephemeral=True)
        return
    prompt = (
        "You are an expert tutor. Explain the following concept or walk through the solution step-by-step in a clear, beginner-friendly way. "
        "If the user asks for a solution, break it down into logical steps.\n\nQuestion: " + question
    )
    models = [
        "mistralai/mistral-7b-instruct:free",
        "openchat/openchat-3.5-0106:free",
        "meta-llama/llama-3-8b-instruct:free",
        "meta-llama/llama-2-70b-chat:free",
        "google/gemma-7b-it:free",
        "gryphe/mythomist-7b:free"
    ]
    for model in models:
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful AI tutor."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )
            answer = response.choices[0].message.content.strip()
            if answer:
                await interaction.followup.send(f"🧑‍🏫 **AI Tutor:**\n{answer}", ephemeral=True)
                return
        except Exception as e:
            print(f"AI Tutor error (model {model}): {e}")
            continue
    await interaction.followup.send("❌ All AI models are currently rate-limited or unavailable. Please try again later.", ephemeral=True)


# =============================
# Ready Event
# =============================
@bot.event
async def on_ready():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            await tree.sync(guild=None)
            print(f"✅ Commands synced globally for {bot.user} in {len(bot.guilds)} servers (attempt {attempt + 1})!")
            break
        except Exception as e:
            print(f"❌ Command sync failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(10)
            else:
                print("❌ All sync attempts failed. Use /sync command manually.")
    change_status.start()
    send_reminders.start()
    task_due_notifications.start()
    generate_daily_challenge.start()
    print(f"✅ {bot.user} is online in {len(bot.guilds)} servers!")

# =============================
# Run bot
# =============================
bot.run(TOKEN)
