TOOLS = [
    # time_now
    {
        'type': 'function',
        'function': {
            'name': 'time_now',
            'description': '''
                Get current date and time in UTC timezone.
                Use this before get_weather_forecast function if user gave you date of forecast
                instead of number of days.
            ''',
        }
    },
    # get_current_weather
    {
        'type': 'function',
        'function': {
            'name': 'get_current_weather',
            'description': '''
                Gets current weather for specified location.
            ''',
            'parameters': {
                'type': 'object',
                'properties': {
                    'location': {
                        'type': 'string',
                        'description': '''
                            Location in human readable format.
                            e.g: "Copenhagen", or "Copenhagen, Louisiana, US", if needed specifying.
                        '''
                    }
                },
                'required': [
                    'location',
                ],
                'additionalProperties': False
            },
            'strict': True
        }
    },
    # get_weather_forecast
    {
        'type': 'function',
        'function': {
            'name': 'get_weather_forecast',
            'description': '''
                Forecast weather API method returns, depending upon your price plan level, upto next 14 day weather
                forecast and weather alert as json. The data is returned as a Forecast Object.
                Forecast object contains astronomy data, day weather forecast and hourly interval weather information
                for a given city.
                Number of days could be less, depending on the API subscription plan.
                With a free plan only up to three days of forecast would be returned.
            ''',
            'parameters': {
                'type': 'object',
                'properties': {
                    'location': {
                        'type': 'string',
                        'description': '''
                            Location in human readable format.
                            e.g: "Copenhagen", or "Copenhagen, Louisiana, US", if needed specifying.
                        '''
                    },
                    'days': {
                        'type': 'integer',
                        'description': '''
                            Number of days of forecast between 0 and 13, where 0 is only today, 1 up to tomorrow, etc.
                        '''
                    },
                },
                'required': [
                    'location', 'days'
                ],
                'additionalProperties': False
            },
            'strict': True
        }
    }
]