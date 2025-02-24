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
        self.default_listening_channel = 1085649787388428370  #
        self.memory_locks = {}  # ✅ Prevents race conditions per channel
        self.short_term_memory_limit = 100  # ✅ Now retains 100 messages
        self.summary_retention_limit = 25  # ✅ Now retains 25 summaries
        self.summary_retention_ratio = 0.8  # ✅ 80% summarization, 20% retention

        # ✅ Properly Registered Configuration Keys
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {
            "openai_api_key": None,
            "short_term_memory": {},  # Tracks last 100 messages per channel
            "mid_term_memory": {},  # Stores multiple condensed summaries
            "long_term_profiles": {},  # Stores persistent knowledge
            "admin_role": None,
            "listening_channel": None,  # ✅ Stores the designated listening channel ID,
            "allowed_roles": [],  # ✅ List of roles that can access Reginald
            "blacklisted_users": [],  # ✅ List of users who are explicitly denied access
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

    
    @commands.command(name="reginald_list_roles", help="List roles that can interact with Reginald.")
    @commands.has_permissions(administrator=True)
    async def list_allowed_roles(self, ctx):
        allowed_roles = await self.config.guild(ctx.guild).allowed_roles() or []
        print(f"DEBUG: Retrieved allowed_roles: {allowed_roles}")  # ✅ Print Debug Info

        valid_roles = [role_id for role_id in allowed_roles if ctx.guild.get_role(role_id)]
        
        await self.config.guild(ctx.guild).allowed_roles.set(valid_roles)  # Save cleaned list

        if not valid_roles:
            await ctx.send("⚠️ No roles are currently allowed to interact with Reginald.")
            return

        role_mentions = [f"<@&{role_id}>" for role_id in valid_roles]
        await ctx.send(f"✅ **Roles with access to Reginald:**\n{', '.join(role_mentions)}")



    @commands.command(name="reginald_allowrole", help="Grant a role permission to interact with Reginald.")
    @commands.has_permissions(administrator=True)
    async def allow_role(self, ctx, role: discord.Role):
        async with self.config.guild(ctx.guild).allowed_roles() as allowed_roles:
            if role.id not in allowed_roles:
                allowed_roles.append(role.id)
                await self.config.guild(ctx.guild).allowed_roles.set(allowed_roles)  # Save change
                await ctx.send(f"DEBUG: Role {role.id} added. Current allowed_roles: {allowed_roles}")
            else:
                await ctx.send(f"⚠️ Role `{role.name}` already has access.")


    @commands.command(name="reginald_disallowrole", help="Revoke a role's access to interact with Reginald.")
    @commands.has_permissions(administrator=True)
    async def disallow_role(self, ctx, role: discord.Role):
        async with self.config.guild(ctx.guild).allowed_roles() as allowed_roles:
            # Remove invalid roles
            valid_roles = [role_id for role_id in allowed_roles if ctx.guild.get_role(role_id)]
            await self.config.guild(ctx.guild).allowed_roles.set(valid_roles)

            if role.id in valid_roles:
                valid_roles.remove(role.id)
                await self.config.guild(ctx.guild).allowed_roles.set(valid_roles)
                await ctx.send(f"❌ Role `{role.name}` has been removed from Reginald's access list.")
            else:
                await ctx.send(f"⚠️ Role `{role.name}` was not in the access list.")

    async def is_blacklisted(self, user: discord.Member) -> bool:
        blacklisted_users = await self.config.guild(user.guild).blacklisted_users()
        return str(user.id) in blacklisted_users
    
    @commands.command(name="reginald_blacklist", help="List users who are explicitly denied access to Reginald.")
    @commands.has_permissions(administrator=True)
    async def list_blacklisted_users(self, ctx):
        blacklisted_users = await self.config.guild(ctx.guild).blacklisted_users()
        if not blacklisted_users:
            await ctx.send("✅ No users are currently blacklisted from interacting with Reginald.")
            return

        user_mentions = [f"<@{user_id}>" for user_id in blacklisted_users]
        await ctx.send(f"🚫 **Blacklisted Users:**\n{', '.join(user_mentions)}")

    @commands.command(name="reginald_blacklist_add", help="Blacklist a user from interacting with Reginald.")
    @commands.has_permissions(administrator=True)
    async def add_to_blacklist(self, ctx, user: discord.User):
        async with self.config.guild(ctx.guild).blacklisted_users() as blacklisted_users:
            if str(user.id) not in blacklisted_users:
                blacklisted_users.append(str(user.id))
                await ctx.send(f"🚫 `{user.display_name}` has been **blacklisted** from interacting with Reginald.")
            else:
                await ctx.send(f"⚠️ `{user.display_name}` is already blacklisted.")

    
    @commands.command(name="reginald_blacklist_remove", help="Remove a user from Reginald's blacklist.")
    @commands.has_permissions(administrator=True)
    async def remove_from_blacklist(self, ctx, user: discord.User):
        async with self.config.guild(ctx.guild).blacklisted_users() as blacklisted_users:
            if str(user.id) in blacklisted_users:
                blacklisted_users.remove(str(user.id))
                await ctx.send(f"✅ `{user.display_name}` has been removed from the blacklist.")
            else:
                await ctx.send(f"⚠️ `{user.display_name}` was not on the blacklist.")

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

    async def summarize_memory(self, ctx, messages):
        """✅ Generates a structured, compact summary of past conversations for mid-term storage."""
        summary_prompt = (
            "Summarize the following conversation into a structured, concise format that retains key details while maximizing brevity. "
            "The summary should be **organized** into clear sections: "
            "\n\n📌 **Key Takeaways:** Important facts or conclusions reached."
            "\n🔹 **Disputed Points:** Areas where opinions or facts conflicted."
            "\n🗣️ **Notable User Contributions:** Key statements from users that shaped the discussion."
            "\n📜 **Additional Context:** Any other relevant information."
            "\n\nEnsure the summary is **dense but not overly verbose**. Avoid unnecessary repetition while keeping essential meaning intact."
        )

        summary_text = "\n".join(f"{msg['user']}: {msg['content']}" for msg in messages)

        try:
            api_key = await self.config.guild(ctx.guild).openai_api_key()
            if not api_key:
                print("🛠️ DEBUG: No API key found for summarization.")
                return (
                    "It appears that I have not been furnished with the necessary credentials to carry out this task. "
                    "Might I suggest consulting an administrator to rectify this unfortunate oversight?"
                )

            client = openai.AsyncClient(api_key=api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": summary_text}
                ],
                max_tokens=2048
            )

            summary_content = response.choices[0].message.content.strip()

            if not summary_content:
                print("🛠️ DEBUG: Empty summary received from OpenAI.")
                return (
                    "Ah, an unusual predicament indeed! It seems that my attempt at summarization has resulted in "
                    "a void of information. I shall endeavor to be more verbose next time."
                )

            return summary_content

        except OpenAIError as e:
            error_message = f"OpenAI Error: {e}"
            print(f"🛠️ DEBUG: {error_message}")  # Log error to console
    
            reginald_responses = [
                f"Regrettably, I must inform you that I have encountered a bureaucratic obstruction whilst attempting to summarize:\n\n```{error_message}```",
                f"It would seem that a most unfortunate technical hiccup has befallen my faculties in the matter of summarization:\n\n```{error_message}```",
                f"Ah, it appears I have received an urgent memorandum stating that my summarization efforts have been thwarted:\n\n```{error_message}```",
                f"I regret to inform you that my usual eloquence is presently obstructed by an unforeseen complication while summarizing:\n\n```{error_message}```"
            ]

            return random.choice(reginald_responses)


        
    def extract_topics_from_summary(self, summary):
        """Dynamically extracts the most important topics from a summary."""

        # 🔹 Extract all words from summary
        keywords = re.findall(r"\b\w+\b", summary.lower())

        # 🔹 Count word occurrences
        word_counts = Counter(keywords)

        # 🔹 Remove unimportant words (common filler words)
        stop_words = {"the", "and", "of", "in", "to", "is", "on", "for", "with", "at", "by", "it", "this", "that", "his", "her"}
        filtered_words = {word: count for word, count in word_counts.items() if word not in stop_words and len(word) > 2}

        # 🔹 Take the 5 most frequently used words as "topics"
        topics = sorted(filtered_words, key=filtered_words.get, reverse=True)[:5]

        return topics

    def select_relevant_summaries(self, summaries, prompt):
        """Selects the most relevant summaries based on topic matching, frequency, and recency weighting."""

        max_summaries = 5 if len(prompt) > 50 else 3  # Use more summaries if the prompt is long
        current_time = datetime.datetime.now()

        def calculate_weight(summary):
            """Calculate a weighted score for a summary based on relevance, recency, and frequency."""
            topic_match = sum(1 for topic in summary["topics"] if topic in prompt.lower())  # Context match score
            frequency_score = len(summary["topics"])  # More topics = likely more important
            timestamp = datetime.datetime.strptime(summary["timestamp"], "%Y-%m-%d %H:%M")
            recency_factor = max(0.1, 1 - ((current_time - timestamp).days / 365))  # Older = lower weight

            return (topic_match * 2) + (frequency_score * 1.5) + (recency_factor * 3)

        # Apply the weighting function and sort by highest weight
        weighted_summaries = sorted(summaries, key=calculate_weight, reverse=True)

        return weighted_summaries[:max_summaries]  # Return the top-scoring summaries

    def extract_fact_from_response(self, response_text):
        """
        Extracts potential long-term knowledge from Reginald's response.
        This filters out generic responses and focuses on statements about user preferences, traits, and history.
        """

        # Define patterns that suggest factual knowledge (adjust as needed)
        fact_patterns = [
            r"I recall that you (.*?)\.",  # "I recall that you like chess."
            r"You once mentioned that you (.*?)\.",  # "You once mentioned that you enjoy strategy games."
            r"Ah, you previously stated that (.*?)\.",  # "Ah, you previously stated that you prefer tea over coffee."
            r"As I remember, you (.*?)\.",  # "As I remember, you studied engineering."
            r"I believe you (.*?)\.",  # "I believe you enjoy historical fiction."
            r"I seem to recall that you (.*?)\.",  # "I seem to recall that you work in software development."
            r"You have indicated in the past that you (.*?)\.",  # "You have indicated in the past that you prefer single-malt whisky."
            r"From what I remember, you (.*?)\.",  # "From what I remember, you dislike overly sweet desserts."
            r"You previously mentioned that (.*?)\.",  # "You previously mentioned that you train in martial arts."
            r"It is my understanding that you (.*?)\.",  # "It is my understanding that you have a preference for Linux systems."
            r"If I am not mistaken, you (.*?)\.",  # "If I am not mistaken, you studied philosophy."
        ]

        for pattern in fact_patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                return match.group(1)  # Extract the meaningful fact

        return None  # No strong fact found

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

    def normalize_fact(self, fact: str) -> str:  # ✅ Now it's a proper method
        """Cleans up facts for better duplicate detection."""
        return re.sub(r"\s+", " ", fact.strip().lower())  # Removes excess spaces)
    
    async def update_long_term_memory(self, ctx, user_id: str, fact: str, source_message: str, timestamp: str):
        """Ensures long-term memory updates are structured, preventing overwrites and tracking historical changes."""
        fact = self.normalize_fact(fact)  # ✅ Normalize before comparison

        async with self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            if user_id not in long_memory:
                long_memory[user_id] = {"facts": []}

            user_facts = long_memory[user_id]["facts"]

            for entry in user_facts:
                if self.normalize_fact(entry["fact"]) == fact:
                    entry["last_updated"] = timestamp
                    return

            # Check for conflicting facts (same topic but different details)
            conflicting_entry = None
            for entry in user_facts:
                existing_keywords = set(entry["fact"].lower().split())
                new_keywords = set(fact.lower().split())

                # If there's significant overlap in keywords, assume it's a conflicting update
                if len(existing_keywords & new_keywords) >= 2:
                    conflicting_entry = entry
                    break

            if "previous_versions" not in conflicting_entry:
                # ✅ If contradiction found, archive the previous version
                conflicting_entry["previous_versions"].append({
                    "fact": conflicting_entry["fact"],
                    "source": conflicting_entry["source"],
                    "timestamp": conflicting_entry["timestamp"]
                })
                conflicting_entry["fact"] = fact  # Store the latest fact
                conflicting_entry["source"] = source_message
                conflicting_entry["timestamp"] = timestamp
                conflicting_entry["last_updated"] = timestamp
            else:
                # ✅ Otherwise, add it as a new fact
                user_facts.append({
                    "fact": fact,
                    "source": source_message,
                    "timestamp": timestamp,
                    "last_updated": timestamp,
                    "previous_versions": []
                })

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

            await self.send_long_message(ctx, formatted_summary)

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
        A unified function to handle sending long messages on Discord, ensuring they don't exceed the 2,000-character limit.

        Parameters:
        - ctx: Discord command context (for sending messages)
        - content: The message content to send
        - prefix: Optional prefix for each message part (e.g., "📜 Summary:")
        """
        # Discord message character limit (allowing a safety buffer)
        CHUNK_SIZE = 1900  # Slightly below 2000 to account for formatting/prefix

        if prefix:
            CHUNK_SIZE -= len(prefix)  # Adjust chunk size if a prefix is used

        # If the message is short enough, send it directly
        if len(content) <= CHUNK_SIZE:
            await ctx.send(f"{prefix}{content}")
            return

        # Splitting the message into chunks
        chunks = []
        while len(content) > 0:
            # Find a good breaking point (preferably at a sentence or word break)
            split_index = content.rfind("\n", 0, CHUNK_SIZE)
            if split_index == -1:
                split_index = content.rfind(" ", 0, CHUNK_SIZE)
            if split_index == -1:
                split_index = CHUNK_SIZE  # Fallback to max chunk size

            # Extract chunk and trim remaining content
            chunks.append(content[:split_index].strip())
            content = content[split_index:].strip()

        # Send chunks sequentially
        for chunk in chunks:
            await ctx.send(f"{prefix}{chunk}")

async def setup(bot):
    """✅ Correct async cog setup for Redbot"""
    await bot.add_cog(ReginaldCog(bot))