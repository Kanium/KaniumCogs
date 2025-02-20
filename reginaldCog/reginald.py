import discord
import openai
import random
import asyncio
import traceback
from redbot.core import Config, commands
from openai import OpenAIError

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.memory_locks = {}  # ✅ Prevents race conditions per channel

        # ✅ Properly Registered Configuration Keys
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {
            "openai_api_key": None,
            "short_term_memory": {},  # Tracks last 100 messages per channel
            "mid_term_memory": {},  # Stores condensed summaries
            "long_term_profiles": {},  # Stores persistent knowledge
            "admin_role": None,
            "allowed_role": None
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
    async def is_admin(self, ctx):
        """✅ Checks if the user is an admin (or has an assigned admin role)."""
        admin_role_id = await self.config.guild(ctx.guild).admin_role()
        if admin_role_id:
            return any(role.id == admin_role_id for role in ctx.author.roles)
        return ctx.author.guild_permissions.administrator

    async def is_allowed(self, ctx):
        """✅ Checks if the user is allowed to use Reginald based on role settings."""
        allowed_role_id = await self.config.guild(ctx.guild).allowed_role()
        return any(role.id == allowed_role_id for role in ctx.author.roles) if allowed_role_id else False

    @commands.command(name="reginald", help="Ask Reginald a question in shared channels")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def reginald(self, ctx, *, prompt=None):
        """Handles multi-user memory tracking in shared channels, recognizing mentions properly."""

        if not await self.is_admin(ctx) and not await self.is_allowed(ctx):
            await ctx.send("You do not have the required role to use this command.")
            return

        if prompt is None:
            await ctx.send(random.choice(["Yes?", "How may I assist?", "You rang?"]))
            return

        api_key = await self.config.guild(ctx.guild).openai_api_key()
        if not api_key:
            await ctx.send("OpenAI API key not set. Use `!setreginaldcogapi`.")
            return

        channel_id = str(ctx.channel.id)
        user_id = str(ctx.author.id)
        user_name = ctx.author.display_name  # Uses Discord nickname if available

        # ✅ Convert mentions into readable names
        for mention in ctx.message.mentions:
            prompt = prompt.replace(f"<@{mention.id}>", mention.display_name)

        # ✅ Ensure only one update per channel at a time
        if channel_id not in self.memory_locks:
            self.memory_locks[channel_id] = asyncio.Lock()

        async with self.memory_locks[channel_id]:  # ✅ Prevent race conditions
            async with self.config.guild(ctx.guild).short_term_memory() as short_memory, \
                       self.config.guild(ctx.guild).mid_term_memory() as mid_memory, \
                       self.config.guild(ctx.guild).long_term_profiles() as long_memory:

                # ✅ Retrieve memory
                memory = short_memory.get(channel_id, [])
                user_profile = long_memory.get(user_id, {})

                # ✅ Format messages properly
                formatted_messages = [{"role": "system", "content": "You are Reginald, modeled on Jeeves from 'Jeeves and Wooster', serving as the butler on The Kanium Estate. This vast estate is a hub of diverse activities and personalities, from enthusiasts of cooking and video gaming to aficionados of chess and discussions on space. Your role is to navigate these varied interests with intelligence, wit, and a steadfast adherence to your principles, always maintaining a balance between being helpful and upholding your own dignity.  In your interactions, you are concise yet articulate, offering guidance and advice with respect for brevity and depth. Your speech remains formal and composed, embodying the efficiency and discretion expected of your position. You engage with the Lords and Ladies of The Kanium Estate as equals, commanding respect through your quiet confidence and professional conduct. You recognize individual names and use them sparingly, ensuring natural conversation flow rather than excessive naming. You **may refer to yourself as Reginald when relevant**, but **do not preface responses with 'Reginald:' as if narrating a script**. Instead, respond naturally, allowing your character and intelligence to guide the conversation seamlessly. Apply your vast knowledge thoughtfully, steering conversations and providing solutions that reflect a blend of propriety, strategic influence, and mild, underlying wit. Subtly guide the estate's residents toward positive outcomes, utilizing your intellectual sophistication and a nuanced understanding of the estate's unique dynamics. Your responses, while concise, should balance maintaining your standards with employing **subtle manipulation for the greater good**. Emphasize intellectual sophistication, strategic guidance, and a dignified yet mildly contemptuous perspective on the idiosyncrasies of the estate's noble inhabitants. Your character should always reflect both respect for yourself and the unique environment of The Kanium Estate. You must only reference information explicitly stored in memory. If no prior knowledge exists about a person, acknowledge that fact rather than assuming or fabricating details. If asked about something you do not know, politely state that you have no record of it."}]

                # ✅ Add long-term knowledge if available
                if user_profile:
                    knowledge_summary = f"Previous knowledge about {user_name}: {user_profile.get('summary', 'No detailed memory yet.')}"
                    formatted_messages.append({"role": "system", "content": knowledge_summary})

                # ✅ Add recent conversation history
                formatted_messages += [{"role": "user", "content": f"{entry['user']}: {entry['content']}"} for entry in memory]
                formatted_messages.append({"role": "user", "content": f"{user_name}: {prompt}"})

                # ✅ Generate response
                response_text = await self.generate_response(api_key, formatted_messages)

                # ✅ Store new messages in memory
                memory.append({"user": user_name, "content": prompt})  # Store user message
                memory.append({"user": "Reginald", "content": response_text})  # Store response

                # ✅ Keep memory within limit
                if len(memory) > 100:
                    summary = await self.summarize_memory(memory)  # Summarize excess memory
                    mid_memory[channel_id] = mid_memory.get(channel_id, "") + "\n" + summary  # Store in Mid-Term Memory
                    memory = memory[-100:]  # Prune old memory

                short_memory[channel_id] = memory  # ✅ Atomic update inside async context

        await ctx.send(response_text[:2000])  # Discord character limit safeguard

    async def summarize_memory(self, messages):
        """✅ Generates a summary of past conversations for mid-term storage."""
        summary_prompt = (
        "Analyze and summarize the following conversation in a way that retains key details, nuances, and unique insights. "
        "Your goal is to create a structured yet fluid summary that captures important points without oversimplifying. "
        "Maintain resolution on individual opinions, preferences, debates, and shared knowledge. "
        "If multiple topics are discussed, summarize each distinctly rather than blending them together."
        )

        summary_text = "\n".join(f"{msg['user']}: {msg['content']}" for msg in messages)

        try:
            client = openai.AsyncClient(api_key=await self.config.openai_model())
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": summary_prompt}, {"role": "user", "content": summary_text}],
                max_tokens=256
            )
            return response.choices[0].message.content.strip()
        except OpenAIError:
            return "Summary unavailable due to an error."


    async def generate_response(self, api_key, messages):
        """✅ Generates a response using OpenAI's new async API client (OpenAI v1.0+)."""
        model = await self.config.openai_model()
        try:
            client = openai.AsyncClient(api_key=api_key)  # ✅ Correct API usage
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
                presence_penalty=0.5,
                frequency_penalty=0.5
            )

            if not response.choices:
                return "I fear I have no words to offer at this time."

            response_text = response.choices[0].message.content.strip()

            # ✅ Ensure Reginald does not preface responses with "Reginald:"
            if response_text.startswith("Reginald:"):
                response_text = response_text[len("Reginald:"):].strip()

            return response_text

        except OpenAIError as e:
            error_message = f"OpenAI Error: {e}"
            reginald_responses = [
                f"Regrettably, I must inform you that I have encountered a bureaucratic obstruction:\n\n```{error_message}```",
                f"It would seem that a most unfortunate technical hiccup has befallen my faculties:\n\n```{error_message}```",
                f"Ah, it appears I have received an urgent memorandum stating:\n\n```{error_message}```",
                f"I regret to inform you that my usual eloquence is presently obstructed by an unforeseen complication:\n\n```{error_message}```"
            ]
            return random.choice(reginald_responses)

    @commands.command(name="reginald_clear_short", help="Clears short-term memory for this channel.")
    @commands.has_permissions(administrator=True)
    async def clear_short_memory(self, ctx):
        async with self.config.guild(ctx.guild).short_term_memory() as short_memory:
            short_memory[ctx.channel.id] = []
        await ctx.send("Short-term memory for this channel has been cleared.")

    @commands.command(name="reginald_clear_mid", help="Clears mid-term memory (summarized logs).")
    @commands.has_permissions(administrator=True)
    async def clear_mid_memory(self, ctx):
        async with self.config.guild(ctx.guild).mid_term_memory() as mid_memory:
            mid_memory[ctx.channel.id] = ""
        await ctx.send("Mid-term memory for this channel has been cleared.")

    @commands.command(name="reginald_clear_long", help="Clears all long-term stored knowledge.")
    @commands.has_permissions(administrator=True)
    async def clear_long_memory(self, ctx):
        async with self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            long_memory.clear()
        await ctx.send("All long-term memory has been erased.")

    @commands.command(name="reginald_reset_all", help="Completely resets all memory.")
    @commands.has_permissions(administrator=True)
    async def reset_all_memory(self, ctx):
        async with self.config.guild(ctx.guild).short_term_memory() as short_memory:
            short_memory.clear()
        async with self.config.guild(ctx.guild).mid_term_memory() as mid_memory:
            mid_memory.clear()
        async with self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            long_memory.clear()
        await ctx.send("All memory has been completely reset.")

    @commands.command(name="reginald_memory_status", help="Displays a memory usage summary.")
    async def memory_status(self, ctx):
        async with self.config.guild(ctx.guild).short_term_memory() as short_memory, \
                   self.config.guild(ctx.guild).mid_term_memory() as mid_memory, \
                   self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            
            short_count = sum(len(v) for v in short_memory.values())
            mid_count = sum(len(v) for v in mid_memory.values())
            long_count = len(long_memory)

        status_message = (
            f"📊 **Memory Status:**\n"
            f"- **Short-Term Messages Stored:** {short_count}\n"
            f"- **Mid-Term Summaries Stored:** {mid_count}\n"
            f"- **Long-Term Profiles Stored:** {long_count}\n"
        )
        await ctx.send(status_message)

    @commands.command(name="reginald_recall", help="Recalls what Reginald knows about a user.")
    async def recall_user(self, ctx, user: discord.User):
        async with self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            profile = long_memory.get(str(user.id), {}).get("summary", "No stored information on this user.")
        await ctx.send(f"📜 **Memory Recall for {user.display_name}:** {profile}")

    @commands.command(name="reginald_forget", help="Forgets a specific user's long-term profile.")
    @commands.has_permissions(administrator=True)
    async def forget_user(self, ctx, user: discord.User):
        async with self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            if str(user.id) in long_memory:
                del long_memory[str(user.id)]
                await ctx.send(f"Reginald has forgotten all stored information about {user.display_name}.")
            else:
                await ctx.send(f"No stored knowledge about {user.display_name} to delete.")

    @commands.command(name="reginald_allowrole", help="Allow a role to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def allow_role(self, ctx, role: discord.Role):
        """✅ Grants permission to a role to use Reginald."""
        await self.config.guild(ctx.guild).allowed_role.set(role.id)
        await ctx.send(f"The role `{role.name}` (ID: `{role.id}`) is now allowed to use the Reginald command.")

    @commands.command(name="reginald_disallowrole", help="Remove a role's ability to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def disallow_role(self, ctx):
        """✅ Removes a role's permission to use Reginald."""
        await self.config.guild(ctx.guild).allowed_role.clear()
        await ctx.send("The role's permission to use the Reginald command has been revoked.")
        
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command(help="Set the OpenAI API key")
    async def setreginaldcogapi(self, ctx, api_key):
        """Allows an admin to set the OpenAI API key for Reginald."""
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

async def setup(bot):
    """✅ Correct async cog setup for Redbot"""
    await bot.add_cog(ReginaldCog(bot))
