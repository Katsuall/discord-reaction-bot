import discord
from discord.ext import commands, tasks
import os
import asyncio
from datetime import datetime, timedelta
import json

intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

tracking_data = {}
report_channels = {}

CONFIG_FILE = 'config.json'

def load_config():
    global report_channels
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                report_channels = {int(k): int(v) for k, v in data.get('report_channels', {}).items()}
    except Exception as e:
        print(f"Error loading config: {e}")
        report_channels = {}

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                'report_channels': {str(k): v for k, v in report_channels.items()}
            }, f)
    except Exception as e:
        print(f"Error saving config: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} server(s)')
    load_config()
    check_tracking.start()

@bot.command(name='track')
async def track_reaction(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return
    
    embed = discord.Embed(
        title="📋 Reaction Check",
        description="Please react with ✅ to confirm you've seen this message!\n\n**You have 24 hours to react.**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Started by {ctx.author.name}")
    
    message = await ctx.send(embed=embed)
    await message.add_reaction('✅')
    
    end_time = datetime.utcnow() + timedelta(hours=24)
    
    tracking_data[message.id] = {
        'guild_id': ctx.guild.id,
        'channel_id': ctx.channel.id,
        'message_id': message.id,
        'end_time': end_time.isoformat(),
        'started_by': ctx.author.id,
        'members': [member.id for member in ctx.guild.members if not member.bot]
    }
    
    print(f"[TRACKING] Started tracking for message {message.id} in {ctx.guild.name}")
    print(f"[TRACKING] Tracking {len(tracking_data[message.id]['members'])} members")
    print(f"[TRACKING] Will check in 24 hours at {end_time}")

@bot.command(name='testtrack')
async def test_track_reaction(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return
    
    embed = discord.Embed(
        title="🧪 TEST Reaction Check",
        description="Please react with ✅ to confirm you've seen this message!\n\n**You have 20 seconds to react (TEST MODE)**",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Started by {ctx.author.name} | TEST MODE")
    
    message = await ctx.send(embed=embed)
    await message.add_reaction('✅')
    
    end_time = datetime.utcnow() + timedelta(seconds=20)
    
    tracking_data[message.id] = {
        'guild_id': ctx.guild.id,
        'channel_id': ctx.channel.id,
        'message_id': message.id,
        'end_time': end_time.isoformat(),
        'started_by': ctx.author.id,
        'members': [member.id for member in ctx.guild.members if not member.bot],
        'test_mode': True
    }
    
    print(f"[TEST TRACKING] Started test tracking for message {message.id} in {ctx.guild.name}")
    print(f"[TEST TRACKING] Tracking {len(tracking_data[message.id]['members'])} members")
    print(f"[TEST TRACKING] Will check in 20 seconds at {end_time}")

@bot.command(name='cancel')
async def cancel_tracking(ctx, message_id: str):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return
    
    try:
        msg_id = int(message_id)
    except ValueError:
        await ctx.send("❌ Invalid message ID! Please provide a valid number.")
        return
    
    if msg_id in tracking_data:
        del tracking_data[msg_id]
        embed = discord.Embed(
            title="✅ Tracking Cancelled",
            description=f"Stopped tracking for message ID: `{msg_id}`",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        print(f"[CANCEL] Tracking cancelled for message {msg_id} by {ctx.author.name}")
    else:
        await ctx.send("❌ No active tracking found for that message ID!")

@bot.command(name='cancelall')
async def cancel_all_tracking(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return
    
    count = len(tracking_data)
    
    if count > 0:
        tracking_data.clear()
        embed = discord.Embed(
            title="✅ All Tracking Cancelled",
            description=f"Stopped tracking for **{count}** active message(s)",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        print(f"[CANCEL ALL] All {count} tracking sessions cancelled by {ctx.author.name}")
    else:
        await ctx.send("❌ No active tracking sessions to cancel!")

@bot.command(name='setchannel')
@commands.has_permissions(administrator=True)
async def set_report_channel(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return
    
    report_channels[ctx.guild.id] = ctx.channel.id
    save_config()
    
    embed = discord.Embed(
        title="✅ Report Channel Set",
        description=f"Non-reactor reports will now be posted to {ctx.channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    print(f"[CONFIG] Report channel set to #{ctx.channel.name} in {ctx.guild.name}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command!")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Error: {error}")

@tasks.loop(seconds=10)
async def check_tracking():
    now = datetime.utcnow()
    completed = []
    
    for message_id, data in tracking_data.items():
        end_time = datetime.fromisoformat(data['end_time'])
        
        if now >= end_time:
            try:
                guild = bot.get_guild(data['guild_id'])
                if not guild:
                    completed.append(message_id)
                    continue
                
                channel = guild.get_channel(data['channel_id'])
                if not channel:
                    completed.append(message_id)
                    continue
                
                try:
                    message = await channel.fetch_message(data['message_id'])
                except:
                    completed.append(message_id)
                    continue
                
                reaction = None
                for r in message.reactions:
                    if str(r.emoji) == '✅':
                        reaction = r
                        break
                
                if reaction:
                    reactors = set()
                    async for user in reaction.users():
                        if not user.bot:
                            reactors.add(user.id)
                    
                    non_reactors = [member_id for member_id in data['members'] if member_id not in reactors]
                    
                    if non_reactors:
                        report_channel_id = report_channels.get(guild.id)
                        
                        if report_channel_id:
                            report_channel = guild.get_channel(report_channel_id)
                            if report_channel:
                                is_test = data.get('test_mode', False)
                                time_period = "20 seconds" if is_test else "24 hours"
                                title_prefix = "🧪 TEST " if is_test else ""
                                
                                KIZUKI_ROLE_ID = 1435698785249398794
                                kizuki_role = guild.get_role(KIZUKI_ROLE_ID)
                                
                                non_reactor_list = []
                                for user_id in non_reactors:
                                    member = guild.get_member(user_id)
                                    if member:
                                        if kizuki_role and kizuki_role in member.roles:
                                            non_reactor_list.append(f"• {member.mention} (ID: {user_id})")
                                    else:
                                        pass
                                
                                embed = discord.Embed(
                                    title=f"{title_prefix}⚠️ Non-Reactors Report (Kizuki Role)",
                                    description=f"**{len(non_reactor_list)} Kizuki member(s)** did not react within {time_period}",
                                    color=discord.Color.orange() if is_test else discord.Color.red(),
                                    timestamp=datetime.utcnow()
                                )
                                
                                if non_reactor_list:
                                    chunks = [non_reactor_list[i:i+20] for i in range(0, len(non_reactor_list), 20)]
                                    for i, chunk in enumerate(chunks):
                                        field_name = "Non-Reactors" if i == 0 else f"Non-Reactors (cont.)"
                                        embed.add_field(
                                            name=field_name,
                                            value='\n'.join(chunk),
                                            inline=False
                                        )
                                    
                                    embed.add_field(
                                        name="Original Message",
                                        value=f"[Jump to message]({message.jump_url})",
                                        inline=False
                                    )
                                    
                                    await report_channel.send(embed=embed)
                                    print(f"[REPORT] Posted {len(non_reactor_list)} Kizuki non-reactors to #{report_channel.name}")
                                else:
                                    print(f"[TRACKING] No Kizuki members failed to react.")
                            else:
                                print(f"[ERROR] Report channel not found for guild {guild.name}")
                        else:
                            print(f"[WARNING] No report channel set for guild {guild.name}")
                    else:
                        print(f"[TRACKING] Everyone reacted! No report needed.")
                
                try:
                    concluded_embed = discord.Embed(
                        title="✅ Activity Check Concluded",
                        description="This activity check has concluded. Thank you for participating!",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    concluded_embed.set_footer(text="Tracking completed")
                    
                    await message.edit(embed=concluded_embed)
                    await message.clear_reactions()
                    print(f"[TRACKING] Updated message {message.id} - Activity check concluded")
                except Exception as e:
                    print(f"[ERROR] Could not update message {message.id}: {e}")
                
                completed.append(message_id)
                
            except Exception as e:
                print(f"[ERROR] Error processing tracking for message {message_id}: {e}")
                completed.append(message_id)
    
    for message_id in completed:
        del tracking_data[message_id]
        print(f"[TRACKING] Completed tracking for message {message_id}")

@check_tracking.before_loop
async def before_check_tracking():
    await bot.wait_until_ready()

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("ERROR: DISCORD_TOKEN not found in environment variables!")
        print("Please add your Discord bot token to the Secrets.")
    else:
       import os
   bot.run(os.environ['DISCORD_TOKEN'])
