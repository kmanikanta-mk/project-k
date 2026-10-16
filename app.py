import os
import secrets
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from model import MODEL_NAME, ask_local_model, check_ollama
from tools import (
    add_task,
    complete_task,
    delete_memory,
    list_memories,
    list_tasks,
    save_memory,
    search_memory,
)

BASE_DIR = Path(__file__).resolve().parent
MAX_CONTENT_LENGTH = 1 * 1024 * 1024
APP_PASSWORD = os.environ.get("APP_PASSWORD")
SECRET_KEY_CONFIGURED = bool(os.environ.get("SECRET_KEY"))
HOSTED = bool(os.environ.get("RENDER") or os.environ.get("VERCEL"))
PUBLIC_TUNNEL = os.environ.get("PUBLIC_TUNNEL") == "1"
AUTH_REQUIRED = bool(APP_PASSWORD)
SYSTEM_PROMPT = """You are a helpful offline personal AI assistant.
Explain things simply. Help users with learning, planning, project notes,
and everyday questions. Do not claim to have saved information unless a tool
confirms it."""
HOSTING_CONFIGURATION_ERROR = (
    "Set APP_PASSWORD and SECRET_KEY in the hosting environment before using this app."
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app = FastAPI(title="Stillroom Personal AI", docs_url="/docs")


class AccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        content_length = request.headers.get("content-length")

        if content_length is not None:
            try:
                body_size = int(content_length)
            except ValueError:
                return JSONResponse({"error": "Invalid Content-Length."}, status_code=400)
            if body_size > MAX_CONTENT_LENGTH:
                return JSONResponse(
                    {"error": "Files must be 1 MB or smaller."},
                    status_code=413,
                )

        if path == "/health" or path == "/login" or path.startswith("/static/"):
            return await call_next(request)

        if (HOSTED or PUBLIC_TUNNEL) and (
            not APP_PASSWORD or not SECRET_KEY_CONFIGURED
        ):
            return JSONResponse({"error": HOSTING_CONFIGURATION_ERROR}, status_code=503)

        if AUTH_REQUIRED and not request.session.get("authenticated"):
            if path.startswith("/api/"):
                return JSONResponse(
                    {"error": "Please sign in to continue."},
                    status_code=401,
                )
            return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)


# Session middleware must wrap access checks so request.session is available.
app.add_middleware(AccessMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    same_site="lax",
    https_only=HOSTED or PUBLIC_TUNNEL,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


async def request_json(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    if (
        APP_PASSWORD
        and isinstance(password, str)
        and secrets.compare_digest(password, APP_PASSWORD)
    ):
        request.session.clear()
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "That password did not match."},
        status_code=401,
    )


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        url="/login" if APP_PASSWORD else "/",
        status_code=302,
    )


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"model_name": MODEL_NAME, "auth_required": bool(APP_PASSWORD)},
    )


@app.get("/api/status")
def status():
    return {"model": MODEL_NAME, "ollama_available": check_ollama()}


@app.post("/api/chat")
async def chat(request: Request):
    data = await request_json(request)
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return JSONResponse({"error": "Enter a message first."}, status_code=400)
    if len(message) > 12000:
        return JSONResponse(
            {"error": "Messages must be 12,000 characters or fewer."},
            status_code=413,
        )

    answer = await run_in_threadpool(
        ask_local_model,
        message.strip(),
        SYSTEM_PROMPT,
    )
    if answer.startswith("Cannot connect to local AI:"):
        return JSONResponse({"error": answer}, status_code=503)
    return {"answer": answer}


@app.get("/api/tasks")
def get_tasks():
    return {"tasks": list_tasks()}


@app.post("/api/tasks")
async def create_task(request: Request):
    data = await request_json(request)
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return JSONResponse({"error": "Task title cannot be empty."}, status_code=400)

    due_date = data.get("due_date")
    if due_date is not None and not isinstance(due_date, str):
        return JSONResponse({"error": "Due date must be text."}, status_code=400)

    priority = data.get("priority", "medium")
    if not isinstance(priority, str):
        return JSONResponse(
            {"error": "Priority must be low, medium, or high."},
            status_code=400,
        )
    priority = priority.lower()
    if priority not in {"low", "medium", "high"}:
        return JSONResponse(
            {"error": "Priority must be low, medium, or high."},
            status_code=400,
        )

    result = add_task(title, due_date, priority)
    return JSONResponse(
        {"message": result, "tasks": list_tasks()},
        status_code=201,
    )


@app.patch("/api/tasks/{task_id}")
def finish_task(task_id: int):
    result = complete_task(task_id)
    if result == "Task not found.":
        return JSONResponse({"error": result}, status_code=404)
    return {"message": result, "tasks": list_tasks()}


@app.get("/api/memories")
def memories(request: Request):
    query = request.query_params.get("q", "").strip()
    results = search_memory(query) if query else list_memories()
    return {"memories": results}


@app.post("/api/memories")
async def create_memory(request: Request):
    data = await request_json(request)
    content = data.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return JSONResponse({"error": "Memory cannot be empty."}, status_code=400)
    result = save_memory(content)
    return JSONResponse(
        {"message": result, "memories": list_memories()},
        status_code=201,
    )


@app.delete("/api/memories/{memory_id}")
def remove_memory(memory_id: int):
    result = delete_memory(memory_id)
    if result == "Memory not found.":
        return JSONResponse({"error": result}, status_code=404)
    return {"message": result, "memories": list_memories()}


@app.post("/api/summarize")
async def summarize(request: Request):
    form = await request.form()
    uploaded = form.get("file")
    if not isinstance(uploaded, UploadFile) or not uploaded.filename:
        return JSONResponse(
            {"error": "Choose a TXT or Markdown file."},
            status_code=400,
        )
    if not uploaded.filename.lower().endswith((".txt", ".md")):
        return JSONResponse(
            {"error": "Please choose a .txt or .md file."},
            status_code=415,
        )

    content_bytes = await uploaded.read(MAX_CONTENT_LENGTH + 1)
    if len(content_bytes) > MAX_CONTENT_LENGTH:
        return JSONResponse(
            {"error": "Files must be 1 MB or smaller."},
            status_code=413,
        )
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeError:
        return JSONResponse({"error": "The file must be UTF-8 text."}, status_code=400)
    if not content.strip():
        return JSONResponse({"error": "The file is empty."}, status_code=400)

    answer = await run_in_threadpool(
        ask_local_model,
        "Summarize this document. Explain the key points:\n\n" + content[:20000],
        "You are a helpful document summarization assistant.",
    )
    if answer.startswith("Cannot connect to local AI:"):
        return JSONResponse({"error": answer}, status_code=503)
    return {"summary": answer}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
    )
