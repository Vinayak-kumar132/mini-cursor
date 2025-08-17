import os
import json
import requests
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Langfuse tracing + OpenAI wrapper
from langfuse import observe, get_client
from langfuse.openai import openai

load_dotenv()

app = FastAPI(title="Mini Cursor API")

# allow Streamlit localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = openai.Client()
# langfuse automatically track OPENAI_API_KEY because this openai is wrapper of openai and custom functionalities



@observe()
def run_command(command: str) -> str:
    try:
        code = os.system(command)
        return f"Command exited with code {code}"
    except Exception as e:
        return f"Error running command: {e}"


# @observe()
# def get_weather(city: str) -> str:
#     try:
#         url = f"https://wttr.in/{city}?format=%C+%t"
#         r = requests.get(url, timeout=10)
#         if r.status_code == 200:
#             return f"The weather in {city} is {r.text}"
#         return f"Weather API returned HTTP {r.status_code}"
#     except Exception as e:
#         return f"Weather call failed: {e}"
@observe()
def get_weather(city: str) -> str:
    try:
        api_key = os.getenv("WEATHERAPI_KEY")
        if not api_key:
            return "Weather API key not set. Define WEATHERAPI_KEY in your environment."

        url = "https://api.weatherapi.com/v1/current.json"
        params = {
            "key": api_key,
            "q": city,  # city/town name, e.g., "London" or "Ranchi"
            "aqi": "no",
        }
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()

        # Extract fields safely
        loc = data.get("location", {})
        cur = data.get("current", {})
        temp_c = cur.get("temp_c")
        condition = (cur.get("condition") or {}).get("text", "Unknown")

        name = loc.get("name", city)
        country = loc.get("country", "")
        place = f"{name}, {country}".strip().strip(
            ","
        )  # e.g., "London, United Kingdom"

        if temp_c is None:
            return f"Could not find temperature for {place}. Raw: {str(cur)[:120]}"

        return f"{place}: {temp_c}°C, {condition}"

    except requests.RequestException as e:
        return f"Weather API request failed: {e}"
    except (ValueError, TypeError, KeyError) as e:
        # ValueError covers bad JSON; KeyError/TypeError if structure changes
        try:
            raw = r.text[:200]
        except Exception:
            raw = ""
        return f"Weather API parse error: {e}. Raw: {raw}"


AVAILABLE_TOOLS = {
    "get_weather": {
        "fn": get_weather,
        "description": "Returns current weather for a city",
    },
    "run_command": {
        "fn": run_command,
        "description": "Executes a shell command on the server",
    },
}

SYSTEM_PROMPT = """
You are a helpful AI Assistant specialized in resolving user queries.
You work in start -> plan -> action -> observe -> output mode.

Rules:
- Emit exactly one JSON object per turn following the schema below.
- Only one step at a time: plan OR action OR output (and we will feed you observe).
- Think carefully before choosing tools.

Output JSON Format:
{
  "step": "string",
  "content": "string",
  "function": "The name of function if the step is action",
  "input": "The input parameter for the function"
}

Available Tools:
- get_weather(city)
- run_command(command)

Example:
User: What is the weather of new york?
Assistant: { "step": "plan", "content": "User wants weather for New York" }
Assistant: { "step": "action", "function": "get_weather", "input": "new york" }
Assistant: { "step": "observe", "output": "12 Degree Cel" }  # (fed back by server)
Assistant: { "step": "output", "content": "The weather for New York is 12 Degree Cel." }
"""


# -----------------------------
# Schemas
# -----------------------------
class ChatRequest(BaseModel):
    query: str = Field(...)
    # Accept any shape for history & sanitize server-side:
    history: Optional[List[Dict[str, Any]]] = None
    # Optional: accept turn_id from Streamlit (ignored by logic but avoids "extra field"):
    turn_id: Optional[str] = None


class Step(BaseModel):
    step: str
    content: Optional[str] = None
    function: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None


class ChatResponse(BaseModel):
    answer: str
    steps: List[Step]


# -----------------------------
# Helpers
# -----------------------------
def sanitize_history(
    raw_history: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    """Keep only {'role': str, 'content': str} pairs with valid strings."""
    safe: List[Dict[str, str]] = []
    if not raw_history:
        return safe
    for m in raw_history:
        role = m.get("role")
        content = m.get("content")
        if isinstance(role, str) and isinstance(content, str):
            safe.append({"role": role, "content": content})
    return safe


# -----------------------------
# Core single-query agent
# -----------------------------
def run_agent(
    user_query: str,
    history: Optional[List[Dict[str, Any]]] = None,
    max_iterations: int = 6,
) -> ChatResponse:
    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # include prior history (sanitized)
    safe_history = sanitize_history(history)
    messages.extend(safe_history)

    # append current user query
    messages.append({"role": "user", "content": user_query})

    steps: List[Step] = []

    for _ in range(max_iterations):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=messages,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM error: {e}")

        raw = resp.choices[0].message.content
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            steps.append(Step(step="error", content=f"Non-JSON output: {raw[:400]}"))
            break

        messages.append({"role": "assistant", "content": json.dumps(parsed)})
        step = (parsed.get("step") or "").lower()

        if step == "plan":
            steps.append(Step(step="plan", content=parsed.get("content")))
            continue

        if step == "action":
            tool = parsed.get("function")
            tool_input = parsed.get("input")
            steps.append(
                Step(
                    step="action",
                    function=tool,
                    input=tool_input,
                    content=f"Calling {tool}",
                )
            )
            if tool in AVAILABLE_TOOLS:
                out = AVAILABLE_TOOLS[tool]["fn"](tool_input)
                steps.append(Step(step="observe", output=out))
                obs_msg = {"step": "observe", "output": out}
                messages.append({"role": "assistant", "content": json.dumps(obs_msg)})
                continue
            else:
                steps.append(Step(step="error", content=f"Unknown tool: {tool}"))
                break

        if step == "output":
            final_text = parsed.get("content", "")
            steps.append(Step(step="output", content=final_text))
            return ChatResponse(answer=final_text, steps=steps)

        steps.append(Step(step="error", content=f"Unexpected step: {parsed}"))
        break

    return ChatResponse(answer="Could not complete the loop.", steps=steps)


# -----------------------------
# Routes
# -----------------------------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        return run_agent(req.query, req.history)
    finally:
        # flush traces so you can see spans immediately while devving
        try:
            get_client().flush()
        except Exception:
            pass


@app.get("/health")
def health():
    return {"status": "ok"}
