# Stillroom Personal AI

A small private workspace for local Ollama chat, task tracking, saved memories, and TXT/Markdown summaries. The original command-line assistant remains available through `main.py`; the browser app is served by FastAPI through `app.py`.

## Run locally

1. Install Python 3.10 or newer and [Ollama](https://ollama.com/).
2. In PowerShell, from this folder, run:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ollama pull llama3.2
   .\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
   ```

3. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). FastAPI's interactive API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The app uses FastAPI and Uvicorn, binds to your computer only, and is available at `http://127.0.0.1:8000`. The app uses `http://localhost:11434` for Ollama by default. Set `OLLAMA_BASE_URL` to use a different Ollama host, `MODEL_NAME` to select another installed model, and `DATABASE_PATH` to choose a different SQLite file. Local data is stored in `assistant.db` by default.

## Public HTTPS access with Cloudflare Quick Tunnel

The optional PowerShell script `.\Start-Stillroom.ps1` starts Uvicorn on `127.0.0.1:8000`, then opens a temporary Cloudflare Quick Tunnel to that local port. Stop any already-running local app on port 8000 before starting this script. It prompts for a password without echoing it, creates a random session key in memory, verifies the public HTTPS `/health` endpoint, and only then prints the generated URL. Enter the password at the app's sign-in page. Press Ctrl+C in the script window to stop both processes. Quick Tunnel URLs are temporary and change when restarted.

Install Cloudflare Tunnel on Windows first if `cloudflared` is not already installed. In PowerShell, run:

```powershell
winget install --id Cloudflare.cloudflared --exact
```

If `winget` is unavailable, follow [Cloudflare's Windows installation instructions](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/). Reopen PowerShell after installation so the updated PATH is available, then run:

```powershell
.\Start-Stillroom.ps1
```

The tunnel forwards requests only to the FastAPI app. The SQLite database and project files are not mounted as static files; public app access requires the password entered at startup. `/health` remains public so the tunnel can verify connectivity. Share the public URL only with people you trust, and do not upload private documents unless you accept sending them through your local app and Ollama setup.

## Deploy

Push this folder to a GitHub repository, then connect that repository to Render or import it into Vercel. `render.yaml` configures the Render web service and persistent disk. `vercel.json` configures the Vercel Python function.

Set `APP_PASSWORD` for a private sign-in and `SECRET_KEY` for secure sessions in the hosting environment. Render generates `SECRET_KEY` and prompts for `APP_PASSWORD` from the blueprint. On Vercel, configure both variables in Project Settings before deploying. The app refuses access to a hosted deployment until both are set.

Render's SQLite database is stored on its mounted persistent disk. Vercel's `/tmp` storage is temporary and can be reset between function instances, so its SQLite tasks and memories are not durable. Use Render for persistent storage or replace SQLite with a managed database before relying on Vercel for saved data.

The Ollama URL defaults to `localhost`, which means the same machine as the app process. A hosted Render or Vercel app cannot reach Ollama on your personal computer at that address. Hosted AI features need an Ollama service reachable from the host; exposing a personal Ollama instance publicly is not recommended. The local app works with the local Ollama installation without that change.

Uploaded documents are sent to the app server for summarization. For private documents, use the local app or only deploy to infrastructure you trust.