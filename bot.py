import nextcord
from nextcord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv

# Import configuration variables from config.py
from config import ADMIN_USER_IDS, START_CHANNEL_ID, FEEDBACK_CHANNEL_ID, ADMIN_EMAIL

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Verify that BOT_TOKEN is loaded
if BOT_TOKEN is None:
    print("Error: Bot token not found. Please ensure it is set in the .env file.")
    exit(1)

# Define intents
intents = nextcord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Initialize bot
bot = commands.Bot(command_prefix='/', intents=intents)

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} is ready!')

# Function to get the next order ID
def get_next_order_id():
    try:
        with open('order_counter.json', 'r') as f:
            data = json.load(f)
            order_number = data['last_order_number'] + 1
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        order_number = 1

    # Save the new order number
    with open('order_counter.json', 'w') as f:
        json.dump({'last_order_number': order_number}, f)

    # Format the order ID
    order_id = f"st-{order_number:02d}"
    return order_id

# Slash Command: Start
@bot.slash_command(name="start", description="Begin a new request")
async def start_command(interaction: nextcord.Interaction):
    # Check if the command is used in the correct channel
    if interaction.channel_id != START_CHANNEL_ID:
        await interaction.response.send_message(
            "Please use this command in the designated channel.", ephemeral=True
        )
        return

    # Generate the order ID
    order_id = get_next_order_id()
    channel_name = order_id

    # Create a new private channel
    guild = interaction.guild
    overwrites = {
        guild.default_role: nextcord.PermissionOverwrite(view_channel=False),
        interaction.user: nextcord.PermissionOverwrite(view_channel=True, send_messages=True),
    }

    # Add all admins to the channel
    for admin_id in ADMIN_USER_IDS:
        admin_member = guild.get_member(admin_id)
        if admin_member:
            overwrites[admin_member] = nextcord.PermissionOverwrite(view_channel=True, send_messages=True)
        else:
            print(f"Warning: Admin with ID {admin_id} not found in the guild.")

    new_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

    # Send a welcome message in the new channel
    await new_channel.send(
        f"Hello {interaction.user.mention}, please provide your assignment details here. An admin will be with you shortly."
    )

    # Send a confirmation to the user
    await interaction.response.send_message(
        f"A private channel has been created for you: {new_channel.mention}", ephemeral=True
    )

    # Post in the feedback channel
    feedback_channel = guild.get_channel(FEEDBACK_CHANNEL_ID)
    if feedback_channel:
        await feedback_channel.send(f"New order created: {order_id}")
    else:
        print("Error: Feedback channel not found.")

# Slash Command: Doable
@bot.slash_command(name="doable", description="Admin command to mark the order as doable")
async def doable(interaction: nextcord.Interaction):
    # Check if the command is used in an order channel
    if not interaction.channel.name.startswith("st-"):
        await interaction.response.send_message("This command can only be used in an order channel.", ephemeral=True)
        return

    # Check if the user is an admin
    if interaction.user.id not in ADMIN_USER_IDS:
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    # Find the student in the channel
    student = None
    for member in interaction.channel.members:
        if member.id not in ADMIN_USER_IDS and not member.bot:
            student = member
            break

    if student:
        await interaction.response.send_message("Order marked as doable.", ephemeral=True)
        await interaction.channel.send(
            f"{student.mention}, your assignment is doable. Please send your assignment details to the email: {ADMIN_EMAIL}"
        )
    else:
        await interaction.response.send_message("Could not find the student in this channel.", ephemeral=True)

# Slash Command: Notdoable
@bot.slash_command(name="notdoable", description="Admin command to mark the order as not doable")
async def notdoable(interaction: nextcord.Interaction):
    # Check if the command is used in an order channel
    if not interaction.channel.name.startswith("st-"):
        await interaction.response.send_message("This command can only be used in an order channel.", ephemeral=True)
        return

    # Check if the user is an admin
    if interaction.user.id not in ADMIN_USER_IDS:
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    # Find the student in the channel
    student = None
    for member in interaction.channel.members:
        if member.id not in ADMIN_USER_IDS and not member.bot:
            student = member
            break

    if student:
        await interaction.response.send_message("Order marked as not doable.", ephemeral=True)
        await interaction.channel.send(
            f"Hello {student.mention}, unfortunately, we are unable to assist with your request at this time. We apologize for any inconvenience."
        )
        # Delete the channel after notifying the student
        await asyncio.sleep(5)  # Wait for 5 seconds before deleting
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("Could not find the student in this channel.", ephemeral=True)

# Slash Command: Revision
@bot.slash_command(name="revision", description="Request a revision")
async def revision_command(interaction: nextcord.Interaction):
    # Check if the command is used in an order channel
    if not interaction.channel.name.startswith("st-"):
        await interaction.response.send_message(
            "This command can only be used in your order channel.", ephemeral=True
        )
        return

    # Ask the client to send the revision details
    await interaction.response.send_message(
        "Please provide the revision details in this channel."
    )

# Slash Command: Complete
@bot.slash_command(name="complete", description="Admin command to complete and archive the order")
async def complete(interaction: nextcord.Interaction):
    # Check if the command is used in an order channel
    if not interaction.channel.name.startswith("st-"):
        await interaction.response.send_message("This command can only be used in an order channel.", ephemeral=True)
        return

    # Check if the user is an admin
    if interaction.user.id not in ADMIN_USER_IDS:
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    # Move the channel to the 'Archived Orders' category
    archived_category = nextcord.utils.get(interaction.guild.categories, name="Archived Orders")
    if not archived_category:
        # Create the category if it doesn't exist
        archived_category = await interaction.guild.create_category("Archived Orders")

    await interaction.channel.edit(category=archived_category)

    # Make the channel read-only for the student
    for member in interaction.channel.members:
        if member.id not in ADMIN_USER_IDS and not member.bot:
            await interaction.channel.set_permissions(member, send_messages=False)

    await interaction.response.send_message("Order marked as complete and channel archived.", ephemeral=True)
    await interaction.channel.send("This order has been marked as complete and the channel has been archived.")

# Run the bot
bot.run(BOT_TOKEN)
