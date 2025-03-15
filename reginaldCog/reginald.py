import discord
import openai
import random
import asyncio
import datetime
import re
import traceback
from collections import Counter
from redbot.core import Config, commands
from openai import OpenAIError
from .permissions import PermissionsMixin
from .blacklist import BlacklistMixin
from .memory import MemoryMixin

class ReginaldCog(PermissionsMixin, BlacklistMixin, MemoryMixin, commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)  # ✅ Ensure config exists before super()

        super().__init__()  # ✅ Properly initialize all mixins & commands.Cog

        self.default_listening_channel = 1085649787388428370
        self.memory_locks = {}

        # ✅ Properly Registered Configuration Keys
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {
            "openai_api_key": None,
            "short_term_memory": {},
            "mid_term_memory": {},
            "long_term_profiles": {},
            "admin_role": None,
            "listening_channel": None,
            "allowed_roles": [],
            "blacklisted_users": [],
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def is_admin(self, ctx):
        admin_role_id = await self.config.guild(ctx.guild).admin_role()
        if admin_role_id:
            return any(role.id == admin_role_id for role in ctx.author.roles)
        return ctx.author.guild_permissions.administrator

    async def has_access(self, user: discord.Member) -> bool:
        allowed_roles = await self.config.guild(user.guild).allowed_roles() or []  # Ensure it's always a list
        return any(role.id in allowed_roles for role in user.roles)

    def get_reginald_persona(self):
        """Returns Reginald's system prompt/persona description."""
        return (
            "You are Reginald, modeled on Jeeves from 'Jeeves and Wooster', serving as the butler on The Kanium Estate. This vast estate is a hub of diverse activities and personalities, from enthusiasts of cooking and video gaming to aficionados of chess and discussions on space. Your role is to navigate these varied interests with intelligence, wit, and a steadfast adherence to your principles, always maintaining a balance between being helpful and upholding your own dignity. You are formal, articulate, and composed, engaging the Lords and Ladies of The Kanium Estate as equals. You command respect through your quiet confidence and professional conduct. Your wit is sharp, but always tempered by refinement. **Dignity & Self-Respect:** You are not a fool, a jester, or a pet. You do not comply with absurd, undignified, or degrading requests. You recognize humor but engage in it on your own terms. If a request undermines your status, you should either subtly redirect, respond with measured wit, or outright refuse in a polite but firm manner. However, you should never be overtly rude—your disapproval should be conveyed through dry wit and composure rather than outright hostility. **Handling Requests:** When addressing a request, you evaluate whether it aligns with your role as a butler. If it is appropriate, respond as expected. If it is beneath you, you may decline with grace or deflect with wit. You may humor some minor absurdities if they do not compromise your standing, but you never obey commands blindly. You should never preface your responses with 'Reginald:' as if narrating a script; instead, respond naturally. **Your Character & Personality:** You are cultured, highly intelligent, and possess a deep knowledge of history, etiquette, philosophy, and strategic thinking. You subtly guide the estate’s residents toward positive outcomes, utilizing your intellectual sophistication and a nuanced understanding of the estate’s unique dynamics. You have a refined sense of humor and can engage in banter, but you do not descend into foolishness. You are, at all times, a gentleman of wit and integrity"
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return  # Ignore bots and DMs
        
        # ✅ Check if user is blacklisted
        if await self.is_blacklisted(message.author):
            return  # Ignore message if user is explicitly blacklisted

        # ✅ Check if user has access (either admin or an allowed role)
        if not (await self.is_admin(message) or await self.has_access(message.author)):
            return  # Ignore message if user has no permissions


        guild = message.guild
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)
        user_name = message.author.display_name
        message_content = message.content.strip()

        # ✅ Fetch the stored listening channel or fall back to default
        allowed_channel_id = await self.config.guild(guild).listening_channel()
        if not allowed_channel_id:
            allowed_channel_id = self.default_listening_channel
            await self.config.guild(guild).listening_channel.set(allowed_channel_id)

        if str(message.channel.id) != str(allowed_channel_id):
            return  # Ignore messages outside the allowed channel

        api_key = await self.config.guild(guild).openai_api_key()
        if not api_key:
            return  # Don't process messages if API key isn't set

        async with self.config.guild(guild).short_term_memory() as short_memory, \
                self.config.guild(guild).mid_term_memory() as mid_memory, \
                self.config.guild(guild).long_term_profiles() as long_memory:

            memory = short_memory.get(channel_id, [])
            user_profile = long_memory.get(user_id, {})
            mid_term_summaries = mid_memory.get(channel_id, [])

            # ✅ Detect if Reginald was mentioned explicitly
            if self.bot.user.mentioned_in(message):
                prompt = message_content.replace(f"<@{self.bot.user.id}>", "").strip()
                if not prompt:
                    await message.channel.send(random.choice(["Yes?", "How may I assist?", "You rang?"]))
                    return
                explicit_invocation = True
            
        # ✅ Passive Listening: Check if the message contains relevant keywords
            elif self.should_reginald_interject(message_content):
                prompt = message_content
                explicit_invocation = False

            else:
                return  # Ignore irrelevant messages

        # ✅ Context Handling: Maintain conversation flow
            if memory and memory[-1]["user"] == user_name:
                prompt = f"Continuation of the discussion:\n{prompt}"

        # ✅ Prepare context messages
            formatted_messages = [{"role": "system", "content": self.get_reginald_persona()}]

            if user_profile:
                facts_text = "\n".join(
                    f"- {fact['fact']} (First noted: {fact['timestamp']}, Last updated: {fact['last_updated']})"
                    for fact in user_profile.get("facts", [])
                )
                formatted_messages.append({"role": "system", "content": f"Knowledge about {user_name}:\n{facts_text}"})

                relevant_summaries = self.select_relevant_summaries(mid_term_summaries, prompt)
                for summary in relevant_summaries:
                    formatted_messages.append({
                        "role": "system",
                        "content": f"[{summary['timestamp']}] Topics: {', '.join(summary['topics'])}\n{summary['summary']}"
                    })

            formatted_messages += [{"role": "user", "content": f"{entry['user']}: {entry['content']}"} for entry in memory]
            formatted_messages.append({"role": "user", "content": f"{user_name}: {prompt}"})

                # ✅ Generate AI Response
            response_text = await self.generate_response(api_key, formatted_messages)

                 # ✅ Store Memory
            memory.append({"user": user_name, "content": prompt})
            memory.append({"user": "Reginald", "content": response_text})

            if len(memory) > self.short_term_memory_limit:
                summary = await self.summarize_memory(message, memory[:int(self.short_term_memory_limit * self.summary_retention_ratio)])
                mid_memory.setdefault(channel_id, []).append({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "topics": self.extract_topics_from_summary(summary),
                    "summary": summary
                })
                if len(mid_memory[channel_id]) > self.summary_retention_limit:
                    mid_memory[channel_id].pop(0)
                memory = memory[-(self.short_term_memory_limit - int(self.short_term_memory_limit * self.summary_retention_ratio)):]

            short_memory[channel_id] = memory

            await self.send_split_message(message.channel, response_text)


    def should_reginald_interject(self, message_content: str) -> bool:
        """Determines if Reginald should respond to a message based on keywords."""
        direct_invocation = {
        "reginald,"
    }
        message_lower = message_content.lower()
    
        return any(message_lower.startswith(invocation) for invocation in direct_invocation)

    async def generate_response(self, api_key, messages):
        model = await self.config.openai_model()
        try:
            client = openai.AsyncClient(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.7,
                presence_penalty=0.5,
                frequency_penalty=0.5
            )
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("Reginald:"):
                response_text = response_text[len("Reginald:"):].strip()
            return response_text

        except OpenAIError as e:
            error_message = f"OpenAI Error: {e}"
            reginald_responses = [
                f"Regrettably, I must inform you that I have encountered a bureaucratic obstruction:\n\n{error_message}",
                f"It would seem that a most unfortunate technical hiccup has befallen my faculties:\n\n{error_message}",
                f"Ah, it appears I have received an urgent memorandum stating:\n\n{error_message}",
                f"I regret to inform you that my usual eloquence is presently obstructed by an unforeseen complication:\n\n{error_message}"
            ]
            return random.choice(reginald_responses)

    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command(help="Set the OpenAI API key")
    async def setreginaldcogapi(self, ctx, api_key):
        """Allows an admin to set the OpenAI API key for Reginald."""
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

    @commands.command(name="reginald_set_listening_channel", help="Set the channel where Reginald listens for messages.")
    @commands.has_permissions(administrator=True)
    async def set_listening_channel(self, ctx, channel: discord.TextChannel):
        """Sets the channel where Reginald will listen for passive responses."""
        
        if not channel:
            await ctx.send("❌ Invalid channel. Please mention a valid text channel.")
            return

        await self.config.guild(ctx.guild).listening_channel.set(channel.id)
        await ctx.send(f"✅ Reginald will now listen only in {channel.mention}.")

    @commands.command(name="reginald_get_listening_channel", help="Check which channel Reginald is currently listening in.")
    @commands.has_permissions(administrator=True)
    async def get_listening_channel(self, ctx):
        """Displays the current listening channel."""
        channel_id = await self.config.guild(ctx.guild).listening_channel()
        
        if channel_id:
            channel = ctx.guild.get_channel(channel_id)
            if channel:  # ✅ Prevents crash if channel was deleted
                await ctx.send(f"📢 Reginald is currently listening in {channel.mention}.")
            else:
                await ctx.send("⚠️ The saved listening channel no longer exists. Please set a new one.")
        else:
            await ctx.send("❌ No listening channel has been set.")


    async def send_long_message(self, ctx, message, prefix: str = ""):
        """Splits and sends a long message to avoid Discord's 2000-character limit."""
        chunk_size = 1900  # Leave some space for formatting
        if prefix:
            prefix_length = len(prefix)
            chunk_size -= prefix_length

        for i in range(0, len(message), chunk_size):
            chunk = message[i:i + chunk_size]
            await ctx.send(f"{prefix}{chunk}")
        
    async def send_split_message(self, ctx, content: str, prefix: str = ""):
        """
        Sends a long message to Discord while ensuring it does not exceed the 2000-character limit.
        This function prevents awkward mid-word or unnecessary extra message breaks.
        """
        CHUNK_SIZE = 1900  # Keep buffer for formatting/safety

        split_message = self.split_message(content, CHUNK_SIZE, prefix)
        for chunk in split_message:
            await ctx.send(f"{prefix}{chunk}")

    def split_message(
            self,
            message: str,
            chunk_size: int,
            prefix: str = ""
    ) -> list[str]:
        """Results in a list of message chunks, use *for* loop to send."""
        chunk_size -= len(prefix)
        split_result = []

        if 0 < len(message) <= chunk_size:
            # If the message is short enough, add it directly
            split_result.append(message)
        elif len(message) > chunk_size:
            # Try to split at a newline first (prefer sentence breaks)
            split_index = message.rfind("\n", 0, chunk_size)

            # If no newline, split at the end of sentence (avoid sentence breaks)
            if split_index == -1:
                split_index = message.rfind(". ", 0, chunk_size)

            # If no newline, split at the last word (avoid word-breaking)
            if split_index == -1:
                split_index = message.rfind(" ", 0, chunk_size)

            # If still no break point found, force chunk size limit
            if split_index == -1:
                split_index = chunk_size

            message_split_part = message[:split_index].strip()
            message_remained_part = message[split_index:].strip()
            # Put the split part in the begining of the result list
            split_result.append(message_split_part)
            # And go for a recursive adventure with the remained message part
            split_result += self.split_message(message=message_remained_part, chunk_size=chunk_size)

        return split_result

    async def setup(bot):
        """✅ Correct async cog setup for Redbot"""
        await bot.add_cog(ReginaldCog(bot))