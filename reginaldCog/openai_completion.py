import random
import json
import openai
from openai import OpenAIError
from .weather import time_now, get_current_weather, get_weather_forecast
from .tools_description import TOOLS

CALLABLE_FUNCTIONS = {
    # Dictionary with functions to call.
    # You can use globals()[func_name](**args) instead, but that's too implicit.
    'time_now': time_now,
    'get_current_weather': get_current_weather,
    'get_weather_forecast': get_weather_forecast,
}


class Completion:
    def __init__(self, model: str, api_key: str):
        self.__model = model
        self.__api_key = api_key
        self.__messages = []

    async def create_completion(self, messages: list):
        self.__messages = messages
        model = self.__model
        try:
            client = openai.AsyncClient(api_key=self.__api_key)
            completion_kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.7,
                "presence_penalty": 0.5,
                "frequency_penalty": 0.5,
                "tools": TOOLS,
                "tool_choice": "auto",
            }
            response = await client.chat.completions.create(**completion_kwargs)
            response_content = response.choices[0].message.content
            tool_calls = response.choices[0].message.tool_calls
            self.append_message(role="assistant", content=response_content, tool_calls=tool_calls)
            if tool_calls:
                for i_call in tool_calls:
                    func_name = i_call.function.name
                    func_args = json.loads(i_call.function.arguments)
                    tool_call_id = i_call.id
                    self.function_manager(func_name, func_args, tool_call_id)
                return self.create_completion(messages=self.__messages)
            return response_content
        except OpenAIError as e:
            return self.get_error_message(error_message=str(e), error_type="OpenAIError")

    def append_message(
            self,
            role: str,
            content: str,
            tool_calls: list = None,
            tool_call_id: str = None,
    ):
        self.__messages.append({
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "tool_call_id": tool_call_id,
        })

    @staticmethod
    def get_error_message(error_message: str, error_type: str) -> str:
        reginald_responses = [
            f"Regrettably, I must inform you that I have encountered a bureaucratic obstruction:",
            f"It would seem that a most unfortunate technical hiccup has befallen my faculties:",
            f"Ah, it appears I have received an urgent memorandum stating:",
            f"I regret to inform you that my usual eloquence is presently obstructed by an unforeseen complication:",
        ]
        random_response = random.choice(reginald_responses)
        return f"{random_response}\n\n{error_type}: {error_message}"

    def function_manager(self, func_name: str, func_kwargs: dict, tool_call_id: str):
        result = CALLABLE_FUNCTIONS[func_name](**func_kwargs)
        self.append_message(role="tool", content=result, tool_call_id=tool_call_id)

