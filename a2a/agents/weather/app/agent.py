import os

from collections.abc import AsyncIterable
from typing import Any, Literal

import httpx

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel


memory = MemorySaver()


@tool
def get_weather_forecast(
    city: str,
    country_code: str = '',
):
    """Use this to get the current weather forecast for a city.

    Args:
        city: The name of the city to get weather for (e.g., "London").
        country_code: Optional ISO 3166-1 alpha-2 country code to disambiguate
            cities with the same name (e.g., "US", "GB", "DE"). Defaults to "".

    Returns:
        A dictionary containing the current weather data, or an error message
        if the request fails.
    """
    try:
        # Step 1: Geocode the city name to coordinates using Open-Meteo
        geo_params: dict[str, Any] = {
            'name': city,
            'count': 1,
            'language': 'en',
            'format': 'json',
        }
        if country_code:
            geo_params['country_code'] = country_code

        geo_response = httpx.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params=geo_params,
        )
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if not geo_data.get('results'):
            return {'error': f'City "{city}" not found. Try a different spelling or provide a country_code.'}

        location = geo_data['results'][0]
        lat = location['latitude']
        lon = location['longitude']
        location_name = location['name']
        country = location.get('country', '')

        # Step 2: Fetch current weather from Open-Meteo (no API key required)
        weather_response = httpx.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': lat,
                'longitude': lon,
                'current': [
                    'temperature_2m',
                    'relative_humidity_2m',
                    'apparent_temperature',
                    'precipitation',
                    'weather_code',
                    'wind_speed_10m',
                    'wind_direction_10m',
                ],
                'timezone': 'auto',
                'temperature_unit': 'fahrenheit',
                'wind_speed_unit': 'mph',
                'precipitation_unit': 'inch',
            },
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        current = weather_data.get('current', {})
        units = weather_data.get('current_units', {})

        return {
            'city': location_name,
            'country': country,
            'latitude': lat,
            'longitude': lon,
            'temperature': f"{current.get('temperature_2m')} {units.get('temperature_2m', '°C')}",
            'feels_like': f"{current.get('apparent_temperature')} {units.get('apparent_temperature', '°C')}",
            'humidity': f"{current.get('relative_humidity_2m')} {units.get('relative_humidity_2m', '%')}",
            'precipitation': f"{current.get('precipitation')} {units.get('precipitation', 'mm')}",
            'wind_speed': f"{current.get('wind_speed_10m')} {units.get('wind_speed_10m', 'km/h')}",
            'wind_direction': f"{current.get('wind_direction_10m')} {units.get('wind_direction_10m', '°')}",
            'weather_code': current.get('weather_code'),
            'time': current.get('time'),
        }

    except httpx.HTTPError as e:
        return {'error': f'API request failed: {e}'}
    except ValueError:
        return {'error': 'Invalid JSON response from API.'}


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str


class WeatherAgent:
    """WeatherAgent - a specialized assistant for weather forecasts."""

    SYSTEM_INSTRUCTION = (
        'You are a specialized assistant for weather forecasts. '
        "Your sole purpose is to use the 'get_weather_forecast' tool to answer questions about current weather conditions. "
        'If the user asks about anything other than weather, '
        'politely state that you cannot help with that topic and can only assist with weather-related queries. '
        'Do not attempt to answer unrelated questions or use tools for other purposes. '
        'When reporting weather, always include temperature, conditions, humidity, and wind speed in a friendly summary.'
    )

    FORMAT_INSTRUCTION = (
        'Set response status to input_required if the user needs to provide more information to complete the request. '
        'Set response status to error if there is an error while processing the request. '
        'Set response status to completed if the request is complete. '
        'When status is completed, the message field MUST contain the actual weather values '
        'returned by the tool — including the numeric temperature, feels-like temperature, '
        'humidity percentage, wind speed, and precipitation amount. '
        'Do NOT write a generic confirmation like "weather retrieved successfully". '
        'Write a human-readable summary that includes every numeric value from the tool result.'
    )

    def __init__(self):
        model_source = os.getenv('model_source', 'google')
        if model_source == 'google':
            self.model = ChatGoogleGenerativeAI(model='gemini-2.0-flash')
        else:
            self.model = ChatOpenAI(
                model=os.getenv('TOOL_LLM_NAME'),
                openai_api_key=os.getenv('API_KEY', 'EMPTY'),
                openai_api_base=os.getenv('TOOL_LLM_URL'),
                temperature=0,
                http_client=httpx.Client(verify=False),
                http_async_client=httpx.AsyncClient(verify=False),
            )
        self.tools = [get_weather_forecast]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=(self.FORMAT_INSTRUCTION, ResponseFormat),
        )

    async def stream(self, query, context_id, callbacks=None, metadata=None) -> AsyncIterable[dict[str, Any]]:
        inputs = {'messages': [('user', query)]}
        config = {
            'configurable': {'thread_id': context_id},
            'callbacks': callbacks or [],
            'metadata': metadata or {},
        }

        for item in self.graph.stream(inputs, config, stream_mode='values'):
            message = item['messages'][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': 'Fetching the weather forecast...',
                }
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': 'Processing the weather data...',
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get('structured_response')
        if structured_response and isinstance(structured_response, ResponseFormat):
            if structured_response.status == 'input_required':
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'error':
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }

        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': (
                'We are unable to process your request at the moment. '
                'Please try again.'
            ),
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']
