import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get environment variables
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Check for missing API keys
if not API_KEY or not BASE_URL or not LLM_MODEL or not WEATHER_API_KEY:
    print("\n[ERROR] Missing API keys! Check your .env file.\n")
    exit()

# Initialize OpenAI client
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# =============================
#  Implementing the Weather Tools
# =============================

def get_current_weather(location):
    """Get the current weather for a given location."""
    url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={location}&aqi=no"

    response = requests.get(url)
    data = response.json()

    if "error" in data:
        return f"Error: {data['error']['message']}"

    weather_info = data["current"]
    return json.dumps({
        "location": data["location"]["name"],
        "temperature_c": weather_info["temp_c"],
        "temperature_f": weather_info["temp_f"],
        "condition": weather_info["condition"]["text"],
        "humidity": weather_info["humidity"],
        "wind_kph": weather_info["wind_kph"]
    })


def get_weather_forecast(location, days=3):
    """Get a weather forecast for a location."""
    url = f"http://api.weatherapi.com/v1/forecast.json?key={WEATHER_API_KEY}&q={location}&days={days}&aqi=no"

    response = requests.get(url)
    data = response.json()

    if "error" in data:
        return f"Error: {data['error']['message']}"

    forecast_days = data["forecast"]["forecastday"]
    forecast_data = []

    for day in forecast_days:
        forecast_data.append({
            "date": day["date"],
            "max_temp_c": day["day"]["maxtemp_c"],
            "min_temp_c": day["day"]["mintemp_c"],
            "condition": day["day"]["condition"]["text"],
            "chance_of_rain": day["day"]["daily_chance_of_rain"]
        })

    return json.dumps({
        "location": data["location"]["name"],
        "forecast": forecast_data
    })


def calculator(expression):
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {str(e)}"


def web_search(query):
    """Simulate a web search for information."""
    search_results = {
        "weather forecast": "Weather forecasts predict atmospheric conditions for a specific location and time period. They typically include temperature, precipitation, wind, and other variables.",
        "temperature conversion": "To convert Celsius to Fahrenheit: multiply by 9/5 and add 32. To convert Fahrenheit to Celsius: subtract 32 and multiply by 5/9.",
        "climate change": "Climate change refers to significant changes in global temperature, precipitation, wind patterns, and other measures of climate that occur over several decades or longer.",
        "severe weather": "Severe weather includes thunderstorms, tornadoes, hurricanes, blizzards, floods, and high winds that can cause damage, disruption, and loss of life."
    }
    
    # Find the closest matching key
    best_match = None
    best_match_score = 0
    for key in search_results:
        words_in_query = set(query.lower().split())
        words_in_key = set(key.lower().split())
        match_score = len(words_in_query.intersection(words_in_key))
        if match_score > best_match_score:
            best_match = key
            best_match_score = match_score
    
    if best_match_score > 0:
        return json.dumps({"query": query, "result": search_results[best_match]})
    else:
        return json.dumps({"query": query, "result": "No relevant information found."})


# =============================
# Defining the Tool Schema
# =============================

weather_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City or country name"}
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get the weather forecast for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City or country name"},
                    "days": {"type": "integer", "description": "Number of days (1-10)", "minimum": 1, "maximum": 10}
                },
                "required": ["location"]
            }
        }
    }
]

calculator_tool = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate a mathematical expression",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g., '2 + 2' or '5 * (3 + 2)'"
                }
            },
            "required": ["expression"]
        }
    }
}

search_tool = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search for information on the web",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
}

# Create tool combinations
cot_tools = weather_tools + [calculator_tool]
react_tools = cot_tools + [search_tool]

# Dictionary to store available functions
available_functions = {
    "get_current_weather": get_current_weather,
    "get_weather_forecast": get_weather_forecast,
    "calculator": calculator,
    "web_search": web_search
}


# =============================
#  Implementing the process_messages Function
# =============================

def process_messages(client, messages, tools=None, available_functions=None):
    """
    Process messages and invoke tools as needed.
    """
    tools = tools or []
    available_functions = available_functions or {}

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL, 
            messages=messages, 
            tools=tools, 
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        messages.append({"role": "assistant", 
                         "content": response_message.content, 
                         "tool_calls": response_message.tool_calls})

        # Process tool calls
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                function_response = available_functions[function_name](**function_args)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool", 
                    "name": function_name, 
                    "content": function_response
                })
            
            # After processing all tool calls, get a final response
            second_response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            second_message = second_response.choices[0].message
            messages.append({"role": "assistant", "content": second_message.content})

        return messages

    except Exception as e:
        print(f"\n[ERROR] API Error: {e}\n")
        return messages


# =============================
#  Implementing the Conversation Loop
# =============================

def run_conversation(client, system_message="You are a helpful weather assistant.", tools=None):
    """Run a conversation with selected tools and system message."""
    if tools is None:
        tools = weather_tools
        
    messages = [{"role": "system", "content": system_message}]
    
    print("\nWeather Assistant: Hello! I can help you with weather information. (Type 'exit' to quit)\n")
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("\nWeather Assistant: Goodbye!")
            break
            
        messages.append({"role": "user", "content": user_input})
        messages = process_messages(client, messages, tools, available_functions)
        
        # Find the last assistant message
        for i in range(len(messages)-1, -1, -1):
            if messages[i]["role"] == "assistant" and messages[i].get("content"):
                content = messages[i]["content"]
                if content:
                    print(f"\nWeather Assistant: {content}\n")
                break
    
    return messages


# =============================
#  Implementing Chain of Thought Reasoning
# =============================

cot_system_message = """You are a helpful assistant that can answer questions about weather and perform calculations.
When responding to complex questions, please follow these steps:
1. Think step-by-step about what information you need
2. Break down the problem into smaller parts
3. Use the appropriate tools to gather information
4. Explain your reasoning clearly
5. Provide a clear final answer

For example, if someone asks about temperature conversions or comparisons between cities, 
first get the weather data, then use the calculator if needed, showing your work.
"""


# =============================
#  Implementing ReAct Reasoning
# =============================

react_system_message = """You are a helpful weather and information assistant that uses the ReAct 
(Reasoning and Acting) approach to solve problems.

When responding to questions, follow this pattern:
1. Thought: Think about what you need to know and what steps to take
2. Action: Use a tool to gather information (weather data, search, calculator)
3. Observation: Review what you learned from the tool
4. ... (repeat the Thought, Action, Observation steps as needed)
5. Final Answer: Provide your response based on all observations

For example:
User: What's the temperature difference between New York and London today?
Thought: I need to find the current temperatures in both New York and London, then calculate the difference.
Action: [Use get_current_weather for New York]
Observation: [Results from weather tool]
Thought: Now I need London's temperature.
Action: [Use get_current_weather for London]
Observation: [Results from weather tool]
Thought: Now I can calculate the difference.
Action: [Use calculator to subtract]
Observation: [Result of calculation]
Final Answer: The temperature difference between New York and London today is X degrees.

Always make your reasoning explicit and show your work.
"""


# =============================
#  Challenge Exercise - Comparative Evaluation
# =============================

def comparative_evaluation(client, query):
    
    import csv
    from datetime import datetime
    
    print("\n===== COMPARATIVE EVALUATION =====")
    print(f"Query: {query}\n")
    
    # Set up agent configurations
    agents = [
        {"name": "Basic Agent", "system_message": "You are a helpful weather assistant.", "tools": weather_tools},
        {"name": "Chain of Thought Agent", "system_message": cot_system_message, "tools": cot_tools},
        {"name": "ReAct Agent", "system_message": react_system_message, "tools": react_tools}
    ]
    
    results = []
    
    # Process the query with each agent
    responses = {}
    for agent in agents:
        print(f"\n--- {agent['name']} ---")
        messages = [
            {"role": "system", "content": agent["system_message"]},
            {"role": "user", "content": query}
        ]
        
        # Process the message and handle tool calls
        processed_messages = process_messages(client, messages, agent["tools"], available_functions)
        
        # Extract the last assistant response
        response = None
        for msg in reversed(processed_messages):
            if msg["role"] == "assistant" and msg.get("content"):
                response = msg["content"]
                break
        
        if response:
            responses[agent["name"]] = response
            print(f"\nResponse:\n{response}\n")
        else:
            responses[agent["name"]] = "No response received."
            print("No response received.")
    
    # Display responses side by side (in a simplified way for console)
    print("\n===== SIDE BY SIDE COMPARISON =====")
    for agent_name, response in responses.items():
        print(f"\n{agent_name}:\n{'-' * 40}")
        # Print first 200 chars to keep it concise in the comparison view
        print(f"{response[:200]}{'...' if len(response) > 200 else ''}")
    
    # Collect ratings for each agent
    print("\n===== RATINGS =====")
    for agent in agents:
        agent_name = agent["name"]
        if agent_name in responses:
            while True:
                try:
                    rating = int(input(f"Rate {agent_name} response (1-5): "))
                    if 1 <= rating <= 5:
                        break
                    print("Please enter a rating between 1 and 5.")
                except ValueError:
                    print("Please enter a valid number between 1 and 5.")
            
            results.append({
                "agent": agent_name,
                "query": query,
                "response": responses[agent_name],
                "rating": rating
            })
    
    # Save results to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"agent_evaluation_{timestamp}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['agent', 'query', 'response', 'rating']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    
    print(f"\nResults saved to {filename}")
    
    # Provide a summary of the ratings
    print("\n===== RATING SUMMARY =====")
    for result in results:
        print(f"{result['agent']}: {result['rating']}/5")
    
    return results


# =============================
#  Running the Chosen Agent
# =============================

if __name__ == "__main__":
    print("\nChoose an option:")
    print("1: Basic Weather Assistant")
    print("2: Chain of Thought Reasoning")
    print("3: ReAct Reasoning")
    print("4: Comparative Evaluation")

    choice = input("Enter your choice (1/2/3/4): ")

    if choice == "1":
        system_message = "You are a helpful weather assistant."
        tools = weather_tools
        run_conversation(client, system_message, tools)
    elif choice == "2":
        system_message = cot_system_message
        tools = cot_tools
        run_conversation(client, system_message, tools)
    elif choice == "3":
        system_message = react_system_message
        tools = react_tools
        run_conversation(client, system_message, tools)
    elif choice == "4":
        query = input("\nEnter a query to evaluate across all agents: ")
        comparative_evaluation(client, query)
    else:
        print("Invalid choice, defaulting to Basic Weather Assistant.")
        system_message = "You are a helpful weather assistant."
        tools = weather_tools
        run_conversation(client, system_message, tools)