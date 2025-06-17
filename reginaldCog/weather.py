from datetime import datetime, timezone
from os import environ
import requests
import json
from debug_stuff import debug

#WEATHER_API_KEY = environ.get('WEATHER_API_KEY')
URL = 'http://api.weatherapi.com/v1'


@debug
def time_now() -> str:
    return str(datetime.now(timezone.utc))


@debug
def get_current_weather(location: str) -> str:
    weather = Weather(location=location)
    return json.dumps(weather.realtime())


@debug
def get_weather_forecast(location: str, days: int = None) -> str:
    days += 1
    days = max(1, days)
    days = min(14, days)
    weather = Weather(location=location)
    return json.dumps(weather.forecast(days=days))


class Weather:
    def __init__(self, location: str):
        self.__location = location
        self.api_key = environ.get('WEATHER_API_KEY')

    @property
    def location(self) -> str:
        return self.__location

    @staticmethod
    def make_request(method: str, params: dict) -> dict:
        response = requests.get(url=f'{URL}{method}', params=params)
        return response.json()

    @debug
    def realtime(self):
        method = '/current.json'
        params = {
            'key': self.api_key,
            'q': self.location,
        }
        return self.make_request(method=method, params=params)

    @debug
    def forecast(self, days: int = 14):
        method = '/forecast.json'
        params = {
            'key': self.api_key,
            'q': self.location,
            'days': days,
        }
        return self.make_request(method=method, params=params)


if __name__ == '__main__':
    test_weather = Weather('Aqtobe')
    result = json.dumps(test_weather.forecast(days=13), indent=2)
    print(result)
