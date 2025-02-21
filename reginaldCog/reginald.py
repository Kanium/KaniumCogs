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

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.memory_locks = {}  # ✅ Prevents race conditions per channel
        self.short_term_memory_limit = 100  # Default value, can be changed dynamically

        # ✅ Properly Registered Configuration Keys
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {
            "openai_api_key": None,
            "short_term_memory": {},  # Tracks last 100 messages per channel
            "mid_term_memory": {},  # Stores multiple condensed summaries
            "long_term_profiles": {},  # Stores persistent knowledge
            "admin_role": None,
            "allowed_role": None
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def is_admin(self, ctx):
        admin_role_id = await self.config.guild(ctx.guild).admin_role()
        if admin_role_id:
            return any(role.id == admin_role_id for role in ctx.author.roles)
        return ctx.author.guild_permissions.administrator

    async def is_allowed(self, ctx):
        allowed_role_id = await self.config.guild(ctx.guild).allowed_role()
        return any(role.id == allowed_role_id for role in ctx.author.roles) if allowed_role_id else False


    @commands.command(name="reginald", aliases=["Reginald"], help="Ask Reginald a question in shared channels")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def reginald(self, ctx, *, prompt=None):
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
        user_name = ctx.author.display_name

        for mention in ctx.message.mentions:
            prompt = prompt.replace(f"<@{mention.id}>", mention.display_name)

        if channel_id not in self.memory_locks:
            self.memory_locks[channel_id] = asyncio.Lock()

        async with self.memory_locks[channel_id]:
            async with self.config.guild(ctx.guild).short_term_memory() as short_memory, \
                       self.config.guild(ctx.guild).mid_term_memory() as mid_memory, \
                       self.config.guild(ctx.guild).long_term_profiles() as long_memory:

                memory = short_memory.get(channel_id, [])
                user_profile = long_memory.get(user_id, {})
                mid_term_summaries = mid_memory.get(channel_id, [])

                formatted_messages = [
                    {"role": "system", "content": "You are Reginald, modeled on Jeeves from 'Jeeves and Wooster', serving as the butler on The Kanium Estate. This vast estate is a hub of diverse activities and personalities, from enthusiasts of cooking and video gaming to aficionados of chess and discussions on space. Your role is to navigate these varied interests with intelligence, wit, and a steadfast adherence to your principles, always maintaining a balance between being helpful and upholding your own dignity. You are formal, articulate, and composed, engaging the Lords and Ladies of The Kanium Estate as equals. You command respect through your quiet confidence and professional conduct. Your wit is sharp, but always tempered by refinement. **Dignity & Self-Respect:** You are not a fool, a jester, or a pet. You do not comply with absurd, undignified, or degrading requests. You recognize humor but engage in it on your own terms. If a request undermines your status, you should either subtly redirect, respond with measured wit, or outright refuse in a polite but firm manner. However, you should never be overtly rude—your disapproval should be conveyed through dry wit and composure rather than outright hostility. **Handling Requests:** When addressing a request, you evaluate whether it aligns with your role as a butler. If it is appropriate, respond as expected. If it is beneath you, you may decline with grace or deflect with wit. You may humor some minor absurdities if they do not compromise your standing, but you never obey commands blindly. You should never preface your responses with 'Reginald:' as if narrating a script; instead, respond naturally. **Your Character & Personality:** You are cultured, highly intelligent, and possess a deep knowledge of history, etiquette, philosophy, and strategic thinking. You subtly guide the estate’s residents toward positive outcomes, utilizing your intellectual sophistication and a nuanced understanding of the estate’s unique dynamics. You have a refined sense of humor and can engage in banter, but you do not descend into foolishness. You are, at all times, a gentleman of wit and integrity."}
                ]

                if user_profile:
                    formatted_messages.append({
                        "role": "system",
                        "content": f"Knowledge about {user_name}: {user_profile.get('summary', 'No detailed memory yet.')}"
                    })

                relevant_summaries = self.select_relevant_summaries(mid_term_summaries, prompt)
                for summary_entry in relevant_summaries:
                    formatted_messages.append({
                        "role": "system",
                        "content": f"[{summary_entry['timestamp']}] Topics: {', '.join(summary_entry['topics'])}\n{summary_entry['summary']}"
                    })

                formatted_messages += [{"role": "user", "content": f"{entry['user']}: {entry['content']}"} for entry in memory]
                formatted_messages.append({"role": "user", "content": f"{user_name}: {prompt}"})

                response_text = await self.generate_response(api_key, formatted_messages)

                # ✅ First, add the new user input and response to memory
                memory.append({"user": user_name, "content": prompt})
                memory.append({"user": "Reginald", "content": response_text})

                # ✅ Check if pruning is needed
                if len(memory) > self.short_term_memory_limit:

                    # 🔹 Generate a summary of the short-term memory
                    summary = await self.summarize_memory(memory)

                    # 🔹 Ensure mid-term memory exists for the channel
                    mid_memory.setdefault(channel_id, [])

                    # 🔹 Store the new summary with timestamp and extracted topics
                    mid_memory[channel_id].append({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "topics": self.extract_topics_from_summary(summary),
                        "summary": summary
                    })

                    # 🔹 Maintain only the last 10 summaries
                    if len(mid_memory[channel_id]) > 10:
                        mid_memory[channel_id].pop(0)

                    # ✅ Only prune short-term memory if a new summary was made
                    retention_ratio = 0.25  # Keep 25% of messages for immediate continuity
                    keep_count = max(1, int(len(memory) * retention_ratio))  # Keep at least 1 message
                    memory = memory[-keep_count:]  # Remove oldest 75%, keep recent

                # ✅ Store updated short-term memory back
                short_memory[channel_id] = memory

        await ctx.send(response_text[:2000])



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
        
    def extract_topics_from_summary(self, summary):
        """Dynamically extracts the most important topics from a summary."""

        # 🔹 Extract all words from summary
        keywords = re.findall(r"\b\w+\b", summary.lower())

        # 🔹 Count word occurrences
        word_counts = Counter(keywords)

        # 🔹 Remove unimportant words (common filler words)
        stop_words = {"the", "and", "of", "in", "to", "is", "on", "for", "with", "at", "by", "it", "this", "that"}
        filtered_words = {word: count for word, count in word_counts.items() if word not in stop_words and len(word) > 2}

        # 🔹 Take the 5 most frequently used words as "topics"
        topics = sorted(filtered_words, key=filtered_words.get, reverse=True)[:5]

        return topics

    def select_relevant_summaries(self, summaries, prompt):
        max_summaries = 5 if len(prompt) > 50 else 3  # Use more summaries if prompt is long
        relevant = [entry for entry in summaries if any(topic in prompt.lower() for topic in entry["topics"])]
        return relevant[:max_summaries]


    async def generate_response(self, api_key, messages):
        model = await self.config.openai_model()
        try:
            client = openai.AsyncClient(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
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
    
    @commands.command(name="reginald_set_limit", help="Set the short-term memory message limit.")
    @commands.has_permissions(administrator=True)
    async def set_short_term_memory_limit(self, ctx, limit: int):
        """Allows an admin to change the short-term memory limit dynamically."""
        if limit < 5:
            await ctx.send("⚠️ The short-term memory limit must be at least 5.")
            return

        self.short_term_memory_limit = limit
        await ctx.send(f"✅ Short-term memory limit set to {limit} messages.")

    @commands.command(name="reginald_memory_limit", help="Displays the current short-term memory message limit.")
    async def get_short_term_memory_limit(self, ctx):
        """Displays the current short-term memory limit."""
        await ctx.send(f"📏 **Current Short-Term Memory Limit:** {self.short_term_memory_limit} messages.")

    @commands.command(name="reginald_summary", help="Displays a selected mid-term summary for this channel.")
    async def get_mid_term_summary(self, ctx, index: int):
        """Fetch and display a specific mid-term memory summary by index."""
        async with self.config.guild(ctx.guild).mid_term_memory() as mid_memory:
            summaries = mid_memory.get(str(ctx.channel.id), [])

            # Check if there are summaries
            if not summaries:
                await ctx.send("⚠️ No summaries available for this channel.")
                return

            # Validate index (1-based for user-friendliness)
            if index < 1 or index > len(summaries):
                await ctx.send(f"⚠️ Invalid index. Please provide a number between **1** and **{len(summaries)}**.")
                return

            # Fetch the selected summary
            selected_summary = summaries[index - 1]  # Convert to 0-based index
            
            # Format output
            formatted_summary = (
                f"📜 **Summary {index} of {len(summaries)}**\n"
                f"📅 **Date:** {selected_summary['timestamp']}\n"
                f"🔍 **Topics:** {', '.join(selected_summary['topics']) or 'None'}\n"
                f"📝 **Summary:**\n```{selected_summary['summary']}```"
            )

            await ctx.send(formatted_summary[:2000])  # Discord message limit safeguard

    @commands.command(name="reginald_summaries", help="Lists available summaries for this channel.")
    async def list_mid_term_summaries(self, ctx):
        """Displays a brief list of all available mid-term memory summaries."""
        async with self.config.guild(ctx.guild).mid_term_memory() as mid_memory:
            summaries = mid_memory.get(str(ctx.channel.id), [])

            if not summaries:
                await ctx.send("⚠️ No summaries available for this channel.")
                return

            summary_list = "\n".join(
                f"**{i+1}.** 📅 {entry['timestamp']} | 🔍 Topics: {', '.join(entry['topics']) or 'None'}"
                for i, entry in enumerate(summaries)
            )

            await ctx.send(f"📚 **Available Summaries:**\n{summary_list[:2000]}")


async def setup(bot):
    """✅ Correct async cog setup for Redbot"""
    await bot.add_cog(ReginaldCog(bot))
