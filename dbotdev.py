import os
from os.path import join, dirname
from dotenv import load_dotenv
import psycopg2
import discord
import datetime
from discord.ext import commands
from discord.ext.commands import Greedy 
import asyncio

#Load the dotenv and set global vars
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
global PROD
global channel_id

#Grab Variables based on Prod or DEV
if str(os.environ.get('PROD')) == "True":
    PROD = True
    database = str(os.environ.get('sqlDB'))
    channel_id = int(os.environ.get('channel'))
    print("=========PRODUCTION MODE=========\n=============WARNING=============")
    
else:
    PROD = False
    database = str(os.environ.get('sqlDBDEV'))
    channel_id = int(os.environ.get('channelDEV'))
    print("=========DEVELOPER MODE=========")


intents = discord.Intents.all()

bot = commands.Bot(command_prefix='!', intents=intents)

host = str(os.environ.get('sqlHost'))
user = str(os.environ.get('sqlUser'))
password = str(os.environ.get('sqlPass'))

#Connect to DB
try:
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password
    )
except:
    print("There was an error connecting to the SQL server. Script will continue, but please beware there will be limited functionality.")



@bot.event
async def on_ready():

    if PROD:
        await bot.change_presence(status=discord.Status.online, activity=discord.Game(name = 'Roblox'))
    else:
        await bot.change_presence(status=discord.Status.online, activity=discord.Game(name = 'Development Shit'))
    
    # Get the channel where the bot should post the accounts
    channel = bot.get_channel(channel_id)
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM app_conf WHERE applicationid = 5 and title = 'RobloxMessageID'")
        message_id = cur.fetchone()

    if message_id:
        message_id = message_id[0]

        try:
            #This line checks to see if we can get the last send message by the bot-- whos ID is stored in SQL
            message = await channel.fetch_message(message_id)

        except discord.errors.NotFound:
            #and this creates a new message and stores the ID in SQL in the event ^^ doesn't work
            message = await channel.send(await get_accounts())
            with conn.cursor() as cur:
                cur.execute("UPDATE app_conf SET value = %s WHERE applicationid = %s and title = %s", (str(message.id), 5, 'RobloxMessageID'))
            conn.commit()
    
    else:
        message = await channel.send(await get_accounts())
        with conn.cursor() as cur:
            cur.execute("INSERT INTO app_conf (applicationid, title, type, value) VALUES (%s, %s, %s, %s)", (5, 'RobloxMessageID', 'MessageID', str(message.id)))
        conn.commit()

    #Start the tasks
    bot.loop.create_task(update_accounts(message))
    bot.loop.create_task(check_banned_accounts())



@bot.command()
async def create(ctx, username: str, password: str):
    await ctx.message.delete()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO robloxaccounts (username, password, banned) VALUES (%s, %s, %s)", (username.lower(), password, "0"))
        conn.commit()
        bot_message = await ctx.send(f'Account created for {username}')
    except:
        bot_message = await ctx.send('There was an error while trying to create the account. Please use the following format:\n`!create [username] [password]`')
    await asyncio.sleep(5)
    await bot_message.delete()

@bot.command()
async def update(ctx,username:str, newpassword:str):
    await ctx.message.delete()
    with conn.cursor() as cur:
        cur.execute("UPDATE robloxaccounts SET password = %s WHERE username = %s", (newpassword,username))
        conn.commit()
        if cur.rowcount == 1:
            bot_message = await ctx.send(f'The password for {username} has been updated')
        else:
            bot_message = await ctx.send(f'The account {username} does not exist')
        await asyncio.sleep(5)
        await bot_message.delete()


@bot.command()
async def accounts(ctx):
    await ctx.message.delete()

    # Retrieve all accounts that are not banned
    with conn.cursor() as cur:
        cur.execute("SELECT username, password FROM robloxaccounts WHERE banned = '0'")
        accounts = cur.fetchall()

    account_list = '```\nCURRENTLY UNBANNED ROBLOX ACCOUNTS:\n'
    for account in accounts:
        account_list += '\nUser: ' + account[0] + '\nPass: ' + account[1] + '\n\n'
    account_list += '```'
    bot_message = await ctx.send(account_list)
    await asyncio.sleep(5)
    await bot_message.delete()




@bot.command()
async def banned(ctx, account: str, length: int):
    await ctx.message.delete()
    try:
        # Grab the reason, don't totally know why this works, but it does.
        reason = ctx.message.content[len(ctx.prefix) + len(ctx.invoked_with) + len(account) + len(str(length)) + 3:]
        current_time = datetime.datetime.now()
        unban_time = current_time + datetime.timedelta(days=length)
        with conn.cursor() as cur:
            cur.execute("UPDATE robloxaccounts SET banned = '1', unbantime = %s WHERE username = %s", (unban_time, account.lower()))
            cur.execute("INSERT INTO robloxbanlog (account, starttime, endtime, reason) VALUES (%s, %s, %s, %s)", (account.lower(), current_time, unban_time, reason))
        conn.commit()
        bot_message = await ctx.send(f'Account {account} has been banned for {length} days for reason : {reason}')
        await asyncio.sleep(5)
        await bot_message.delete()
    except:
        bot_message = await ctx.send('Failed to ban account, are you using the correct format?\n`!banned [username] [# of days] [reason]`')


@bot.command()
async def banlog(ctx, account: str):
    await ctx.message.delete()
    with conn.cursor() as cur:
        cur.execute("SELECT starttime, endtime, reason FROM robloxbanlog WHERE account = %s ORDER BY starttime ASC", (account.lower(),))
        banlog = cur.fetchall()

    if not banlog:
        bot_message = await ctx.send(f"No banlog found for account {account}")
        await asyncio.sleep(5)
        await bot_message.delete()
        return
    banlog_list = f'```\nBanlog for {account}:\n'
    for ban in banlog:
        banlog_list += f'\nStart Time: {ban[0].strftime("%m-%d-%Y %H:%M")}\nEnd Time: {ban[1].strftime("%m-%d-%Y %H:%M")}\nReason: {ban[2]}\n\n'
    banlog_list += '```'
    bot_message = await ctx.send(banlog_list)
    await asyncio.sleep(5)
    await bot_message.delete()

@bot.command()
async def ex(ctx):
    await ctx.message.delete()
    help_message = '```\nAVAILABLE COMMANDS:\n\n'
    help_message += '!create <username> <password> - Creates a new account\n'
    help_message += '!banned <username> <length in days> <reason> - Bans the specified account\n'
    help_message += '!accounts - Displays a list of currently unbanned accounts\n'
    help_message += '!update <username> <new_username> <new_password> - updates the username and password of an account\n'
    help_message += '!total - Displays the total number of accounts\n'
    help_message += '!help - Displays this list of commands\n```'
    bot_message = await ctx.send(help_message)
    await asyncio.sleep(5)
    await bot_message.delete()

@bot.command()
async def total(ctx):
    await ctx.message.delete()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM robloxaccounts WHERE banned = '0'")
        unbanned_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM robloxaccounts WHERE banned = '1'")
        banned_count = cur.fetchone()[0]
    bot_message = await ctx.send(f'There are {unbanned_count} accounts unbanned.\nThere are {banned_count} accounts banned.')
    await asyncio.sleep(5)
    await bot_message.delete()


async def get_accounts():
    # Retrieve all accounts that are not banned
    with conn.cursor() as cur:
        cur.execute("SELECT username, password FROM robloxaccounts WHERE banned = '0'")
        accounts = cur.fetchall()
    account_list = '```\nCURRENTLY UNBANNED ROBLOX ACCOUNTS:\n'
    for account in accounts:
        account_list += '\nUser: ' + account[0] + '\nPass: ' + account[1] + '\n\n'
    account_list += '```'
    return account_list

async def update_accounts(message):
    while True:
        try:
            # Edit the previous message with the current accounts
            await message.edit(content=await get_accounts())
        except discord.errors.NotFound:
            channel = bot.get_channel(channel_id)
            message = await channel.send(await get_accounts())
            with conn.cursor() as cur:
                cur.execute("UPDATE app_conf SET value = %s WHERE applicationid = %s and title = %s", (str(message.id), 5, 'RobloxMessageID'))
            conn.commit()
        # Wait for 30s before updating the message again
        await asyncio.sleep(30)


async def check_banned_accounts():
    while True:
        with conn.cursor() as cur:
            current_time = datetime.datetime.now()
            # Get all banned accounts that have passed their unban time
            cur.execute("SELECT username FROM robloxaccounts WHERE banned = '1' AND unbantime <= %s", (current_time,))
            banned_accounts = cur.fetchall()
        if banned_accounts:
            with conn.cursor() as cur:
                for account in banned_accounts:
                    cur.execute("UPDATE robloxaccounts SET banned = '0', unbantime = NULL WHERE username = %s", (account,))
            conn.commit()
        # Wait for 1 hour before checking again
        await asyncio.sleep(3600)




if PROD:
    discordtoken = str(os.environ.get('discordEMbotRobloxToken'))
    print("Bot Chosen: PRODUCTION Emery Roblox Bot")
else:
    discordtoken = str(os.environ.get('discordEMbotRobloxTokenDEV'))
    print("Bot Chosen: DEVELOPER Emery Roblox Bot DEV")


bot.run(discordtoken)
