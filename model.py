
import os

import requests

MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.2")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/chat"


def check_ollama():
    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=3
        )
        return response.ok
    except requests.RequestException:
        return False


def ask_local_model(message, system_prompt=None):
    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    messages.append({
        "role": "user",
        "content": message
    })

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False
            },
            timeout=180
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]

    except requests.RequestException as error:
        return (
            f"Cannot connect to local AI: {error}\n"
            "Check that Ollama is running and the model is installed."
        )
