# LangGraph Weather Agent with A2A Protocol

A weather forecast agent built with [LangGraph](https://langchain-ai.github.io/langgraph/) and exposed through the A2A protocol. Uses the [Open-Meteo API](https://open-meteo.com/) — no API key required for weather data.

## How It Works

The agent uses a LangGraph ReAct pattern to geocode a city name and fetch current weather conditions. It supports multi-turn dialogue (e.g., asking "what about Paris?" as a follow-up) and streaming responses.

## Setup & Running

1. Navigate to this directory:

   ```bash
   cd samples/python/agents/langgraph_weather
   ```

2. Create a `.env` file with your LLM credentials:

   ```bash
   # Google Gemini
   echo "GOOGLE_API_KEY=your_api_key_here" > .env

   # OpenAI-compatible
   echo "model_source=litellm" >> .env
   echo "API_KEY=your_api_key_here" >> .env
   echo "TOOL_LLM_URL=your_llm_url" >> .env
   echo "TOOL_LLM_NAME=your_model_name" >> .env
   ```

3. Run the agent (default port 10001):

   ```bash
   uv run app
   ```

## Build Container Image

```bash
podman build . -t langgraph-weather-agent
podman run -p 10001:10001 -e GOOGLE_API_KEY=your_key langgraph-weather-agent
```

## Example Queries

- "What's the weather in New York?"
- "How cold is it in Tokyo right now?"
- "Is it raining in London?"
- "What's the temperature in Sydney, AU?"
