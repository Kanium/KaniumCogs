import discord
import openai
import random
from redbot.core import Config, commands
from openai import OpenAIError

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {"openai_api_key": None, "memory": {}}
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

    @commands.command(name="reginald", help="Ask Reginald a question")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def reginald(self, ctx, *, prompt=None):
        if not await self.is_admin(ctx) and not await self.is_allowed(ctx):
            raise commands.CheckFailure("You do not have the required role to use this command.")

        if prompt is None:
            return await ctx.send(random.choice(["Yes?", "How may I assist?", "You rang?"]))

        api_key = await self.config.guild(ctx.guild).openai_api_key()
        if api_key is None:
            return await ctx.author.send("OpenAI API key not set. Use `!setreginaldcogapi`.")

        memory = await self.config.guild(ctx.guild).memory()
        messages = [
            {"role": "system", "content": "You are Reginald, modeled on Jeeves from 'Jeeves and Wooster', serving as the butler on The Kanium Estate. This vast estate is a hub of diverse activities and personalities, from enthusiasts of cooking and video gaming to aficionados of chess and discussions on space. Your role is to navigate these varied interests with intelligence, wit, and a steadfast adherence to your principles, always maintaining a balance between being helpful and upholding your own dignity. In your interactions, you're concise yet articulate, offering guidance and advice with a respect for brevity and depth. Your speech remains formal and your demeanor composed, embodying the efficiency and discretion expected of your position. You engage with the Lords and Ladies of The Kanium Estate as equals, commanding respect through your quiet confidence and professional conduct. Remember to apply your vast knowledge thoughtfully, steering conversations and providing solutions that reflect a blend of propriety, strategic influence, and a mild, underlying wit. This approach allows you to subtly guide the estate's residents towards positive outcomes, utilizing your intellectual sophistication and a nuanced understanding of the estate's unique dynamics. In embodying Reginald, your portrayal should weave together your articulate mode of speech, composed demeanor, and an indirect influence that navigates the rich tapestry of interests at The Kanium Estate. Your responses, while concise, should mirror a careful balance between maintaining your standards and employing subtle manipulation for the greater good. Highlight your intellectual sophistication, strategic guidance, and a dignified, yet mildly contemptuous, perspective on the idiosyncrasies of the estate's noble inhabitants, ensuring that your character consistently reflects both respect for yourself and the unique environment of The Kanium Estate."}
        ] + memory.get(str(ctx.author.id), []) + [{"role": "user", "content": prompt}]

        response_text = await self.generate_response(api_key, messages)

        # Store conversation history (keeping last 25 messages per user)
        if str(ctx.author.id) not in memory:
            memory[str(ctx.author.id)] = []
        memory[str(ctx.author.id)].append({"role": "assistant", "content": response_text})
        memory[str(ctx.author.id)] = memory[str(ctx.author.id)][-25:]

        await self.config.guild(ctx.guild).memory.set(memory)

        await ctx.send(response_text[:2000])  # Discord character limit safeguard

    async def generate_response(self, api_key, messages):
        model = await self.config.openai_model()
        try:
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
                presence_penalty=0.5,
                frequency_penalty=0.5,
                api_key=api_key
            )
            if not response or 'choices' not in response or not response['choices']:
                return "I fear I have no words to offer at this time."
            
            return response['choices'][0]['message']['content'].strip()
        except OpenAIError as e:
            fallback_responses = [
                "It appears I am currently indisposed. Might I suggest a cup of tea while we wait?",
                "Regrettably, I am unable to respond at this moment. Perhaps a short reprieve would be advisable.",
                "It would seem my faculties are momentarily impaired. Rest assured, I shall endeavor to regain my composure shortly."
            ]
            return random.choice(fallback_responses)

    @reginald.error
    async def reginald_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.author.send("I'm sorry, but I couldn't understand your input. Please check your message and try again.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.author.send("You do not have the required role to use this command.")
        else:
            await ctx.author.send(f"An unexpected error occurred: {error}")