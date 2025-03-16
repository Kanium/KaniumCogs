from datetime import datetime, timezone
from os import environ
import requests
import json

#WEATHER_API_KEY = environ.get('WEATHER_API_KEY')
URL = 'http://api.weatherapi.com/v1'


def time_now() -> str:
    return str(datetime.now(timezone.utc))


def get_current_weather(location: str) -> str:
    weather = Weather(location=location)
    return json.dumps(weather.realtime())


def get_weather_forecast(location: str, days: int = 14, dt: str = '2025-03-24') -> str:
    weather = Weather(location=location)
    return json.dumps(weather.forecast(days=days, dt=dt))


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

    def realtime(self):
        method = '/current.json'
        params = {
            'key': self.api_key,
            'q': self.location,
        }
        return self.make_request(method=method, params=params)

    def forecast(self, days: int = 14, dt: str = '2025-03-24'):
        method = '/forecast.json'
        params = {
            'key': self.api_key,
            'q': self.location,
            'days': days,
            'dt': dt,
        }
        return self.make_request(method=method, params=params)


if __name__ == '__main__':
    test_weather = Weather('Aqtobe')
    result = json.dumps(test_weather.forecast(days=14, dt='2025-03-24'), indent=2)
    print(result)
