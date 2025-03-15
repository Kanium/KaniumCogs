import re
import random
import datetime
import discord
import openai
from collections import Counter
from redbot.core import commands, Config
from openai import OpenAIError


class MemoryMixin:
    """Handles all memory-related functions for Reginald."""

    def __init__(self):
        """No longer requires `config` as a parameter."""
        self.short_term_memory_limit = 100
        self.summary_retention_limit = 25
        self.summary_retention_ratio = 0.8

    def get_config(self):
        """Access `_config` from the parent class (ReginaldCog)."""
        return self._config  # ✅ Use `_config` instead of `self.config`
    
    @commands.command(name="reginald_clear_short", help="Clears short-term memory for this channel.")
    @commands.has_permissions(administrator=True)
    async def clear_short_memory(self, ctx):
        """Clears short-term memory for this channel."""
        async with self.config.guild(ctx.guild).short_term_memory() as short_memory:
            short_memory[ctx.channel.id] = []
        await ctx.send("Short-term memory for this channel has been cleared.")


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

    @commands.command(name="reginald_clear_mid", help="Clears mid-term memory (summarized logs).")
    @commands.has_permissions(administrator=True)
    async def clear_mid_memory(self, ctx):
        async with self.config.guild(ctx.guild).mid_term_memory() as mid_memory:
            mid_memory[ctx.channel.id] = ""
        await ctx.send("Mid-term memory for this channel has been cleared.")

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
            
            # Format output correctly
            formatted_summary = (
                f"📜 **Summary {index} of {len(summaries)}**\n"
                f"📅 **Date:** {selected_summary['timestamp']}\n"
                f"🔍 **Topics:** {', '.join(selected_summary['topics']) or 'None'}\n"
                f"📝 **Summary:**\n\n"
                f"{selected_summary['summary']}"
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
                f"Regrettably, I must inform you that I have encountered a bureaucratic obstruction whilst attempting to summarize:\n\n{error_message}",
                f"It would seem that a most unfortunate technical hiccup has befallen my faculties in the matter of summarization:\n\n{error_message}",
                f"Ah, it appears I have received an urgent memorandum stating that my summarization efforts have been thwarted:\n\n{error_message}",
                f"I regret to inform you that my usual eloquence is presently obstructed by an unforeseen complication while summarizing:\n\n{error_message}"
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