# AI Execution Pipeline

Thin Flask spine ported from `harvest/487_marketing-for-beginners/`.
The source thread drafted 87 Python + 85 jsx + 82 bash blocks across
300 iterations toward an "AI Execution Pipeline." This repo keeps the
Python spine only: a chat-log server with JSON persistence, API-key
auth, CORS, optional OpenAI response generation, and an execution
pipeline tracker that mirrors the `conversation_flow` structure from
the thread's final output.

React Native + Google Drive blocks from the source thread were
intentionally dropped. If they matter later, they can be added as
separate subpackages.

## Run

```bash
cd apps/ai-exec-pipeline
pip install -r requirements.txt
cp .env.example .env              # edit keys if desired
PIPELINE_API_KEYS=DEV_KEY python server.py
```

Server starts on `http://127.0.0.1:5000`.

## Endpoints

| Method | Path             | Purpose                              |
|--------|------------------|--------------------------------------|
| GET    | `/health`        | No auth. Liveness + message count.   |
| GET    | `/chatlog`       | Fetch full log. Requires `X-API-KEY`.|
| POST   | `/update_chat`   | Append message; generates AI reply.  |
| GET    | `/pipeline`      | Get execution-pipeline state.        |
| POST   | `/pipeline/step` | Record a step + workflow_status.     |

Auth header: `X-API-KEY: DEV_KEY` (or whatever you set in `PIPELINE_API_KEYS`).

If `OPENAI_API_KEY` is unset, `/update_chat` returns a stub response so
the server stays runnable without credentials.

## Client

```bash
python client.py send "hello AI"
python client.py poll
```

## Lineage

Source thread: `services/cognitive-sensor/harvest/487_marketing-for-beginners/`.
Blocks fused: 3, 11, 17, 18, 24, 26 (server); 12, 15, 19, 27 (client);
`final_output.md` conversation_flow schema (pipeline).
