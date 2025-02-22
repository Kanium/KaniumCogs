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
from .chess_addon import ChessHandler

chess_handler = ChessHandler()

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.memory_locks = {}  # ✅ Prevents race conditions per channel
        self.short_term_memory_limit = 30  # Default value, can be changed dynamically

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
                    facts_text = "\n".join(
                        f"- {fact['fact']} (First noted: {fact['timestamp']}, Last updated: {fact['last_updated']})"
                        for fact in user_profile.get("facts", [])
                    )
                    formatted_messages.append({
                        "role": "system",
                        "content": f"Knowledge about {user_name}:\n{facts_text or 'No detailed memory yet.'}"
                    })

                relevant_summaries = self.select_relevant_summaries(mid_term_summaries, prompt)
                for summary_entry in relevant_summaries:
                    formatted_messages.append({
                        "role": "system",
                        "content": f"[{summary_entry['timestamp']}] Topics: {', '.join(summary_entry['topics'])}\n{summary_entry['summary']}"
                    })

                formatted_messages += [{"role": "user", "content": f"{entry['user']}: {entry['content']}"} for entry in memory]
                formatted_messages.append({"role": "user", "content": f"{user_name}: {prompt}"})

                response_text = await self.generate_response(api_key, formatted_messages, ctx)

                # ✅ Extract potential long-term facts from Reginald's response
                potential_fact = self.extract_fact_from_response(response_text)
                if potential_fact:
                    await self.update_long_term_memory(user_id, potential_fact, ctx.message.content, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

                # ✅ First, add the new user input and response to memory
                memory.append({"user": user_name, "content": prompt})
                memory.append({"user": "Reginald", "content": response_text})

                # ✅ Ensure a minimum of 10 short-term messages are always retained
                MINIMUM_SHORT_TERM_MESSAGES = 10

                # ✅ Check if pruning is needed
                if len(memory) > self.short_term_memory_limit:

                    # 🔹 Generate a summary of the short-term memory
                    summary = await self.summarize_memory(ctx, memory)

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

                    # ✅ Ensure at least 10 short-term messages remain after pruning
                    retention_ratio = 0.25  # Default: Keep 25% of messages for continuity
                    keep_count = max(MINIMUM_SHORT_TERM_MESSAGES, int(len(memory) * retention_ratio))

                    memory = memory[-keep_count:]  # Remove oldest messages but keep at least 10

                # ✅ Store updated short-term memory back
                short_memory[channel_id] = memory

        await self.send_split_message(ctx, response_text)



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

    async def generate_response(self, api_key, messages, ctx):
        """Handles AI responses and function calling for chess interactions."""
    
        model = await self.config.openai_model()

        try:
            client = openai.AsyncClient(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1500,  # Balanced token limit to allow function execution & flavor text
                temperature=0.7,
                presence_penalty=0.5,
                frequency_penalty=0.5,
                functions=[
                    {
                        "name": "set_board",
                        "description": "Sets up the chessboard to a given FEN string.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "fen": {"type": "string", "description": "The FEN string representing the board state."}
                            },
                            "required": ["fen"]
                        }
                    },
                    {
                        "name": "make_move",
                        "description": "Executes a chess move for the current game.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "move": {"type": "string", "description": "The move in SAN format (e.g., 'e2e4')."}
                            },
                            "required": ["move"]
                        }
                    },
                    {
                        "name": "reset_board",
                        "description": "Resets the chessboard to the default starting position.",
                        "parameters": {}
                    },
                    {
                        "name": "resign",
                        "description": "Resigns from the current chess game.",
                        "parameters": {}
                    },
                    {
                        "name": "get_board_state_text",
                        "description": "Retrieves the current board state as a FEN string.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_id": {"type": "string", "description": "The user's unique ID."}
                            },
                            "required": ["user_id"]
                        }
                    }
                ]
            )

            response_data = response.choices[0].message

            # 🟢 Check if OpenAI returned a function call
            if hasattr(response_data, "function_call") and response_data.function_call:
                function_call = response_data.function_call

                function_name = function_call.name
                function_args = json.loads(function_call.arguments)  # Convert JSON string to dict

                # 🟢 Call the appropriate function
                if function_name == "set_board":
                    return chess_handler.set_board(ctx.author.id, function_args["fen"])
                elif function_name == "make_move":
                    return chess_handler.make_move(ctx.author.id, function_args["move"])
                elif function_name == "reset_board":
                    return chess_handler.reset_board(ctx.author.id)
                elif function_name == "resign":
                    return chess_handler.resign(ctx.author.id)
                elif function_name == "get_board_state_text":
                    return chess_handler.get_fen(ctx.author.id)  # Returns FEN string of the board

            # 🟢 If no function was called, return AI-generated response with flavor text
            return response_data.get("content", "I'm afraid I have nothing to say.")

        except openai.OpenAIError as e:
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


    async def update_long_term_memory(self, ctx, user_id: str, fact: str, source_message: str, timestamp: str):
        """Ensures long-term memory updates are structured, preventing overwrites and tracking historical changes."""

        async with self.config.guild(ctx.guild).long_term_profiles() as long_memory:
            if user_id not in long_memory:
                long_memory[user_id] = {"facts": []}

            user_facts = long_memory[user_id]["facts"]

            # Check if fact already exists
            for entry in user_facts:
                if entry["fact"].lower() == fact.lower():
                    # ✅ If fact exists, just update the timestamp
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

            if conflicting_entry:
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
