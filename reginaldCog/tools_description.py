TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'time_now',
            'description': 'Get current date and time in UTC timezone.',
        }
    },
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
    {
        'type': 'function',
        'function': {
            'name': 'get_weather_forecast',
            'description': '''
                Forecast weather API method returns, depending upon your price plan level, upto next 14 day weather
                forecast and weather alert as json. The data is returned as a Forecast Object.
                Forecast object contains astronomy data, day weather forecast and hourly interval weather information
                for a given city.
                With a free weather API subscription, only up to three days of forecast can be requested.
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
                    'dt': {
                        'type': 'string',
                        'description': '''
                            The date up until to request the forecast in YYYY-MM-DD format.
                            Check the **time_now** function first if you unsure which date it is.
                        '''
                    },
                },
                'required': [
                    'location', 'dt'
                ],
                'additionalProperties': False
            },
            'strict': True
        }
    }
]