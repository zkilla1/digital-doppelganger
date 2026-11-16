# AI Chatbot: Digital Doppelganger

A chatbot that texts like you. A Python ETL pipeline processes your iMessage history into a style profile and a bank of real (their message → your reply) examples. A Node.js server uses those to prompt GPT. Google Cloud Vision lets the bot react to photos, and a React client gives you a real-time chat UI. It deploys to Google Cloud Run.

**Stack:** React · Node.js (Express) · Python · GCP (Cloud Run, Cloud Build) · Google Cloud Vision · OpenAI GPT

```
 chat.db / CSV ──► Python ETL ──► persona.json + examples.jsonl ──► Node API ──► GPT
                   (extract,        (style rules,                   │  ▲
                    clean,           few-shot bank,                 │  └── Cloud Vision (photos)
                    pair, profile)   fine-tune JSONL)               ▼
                                                              React chat client
```

## How it works

**1. ETL (`etl/`)**
- **Extract:** reads macOS `~/Library/Messages/chat.db`. It handles both timestamp formats, skips tapback reactions, and decodes the `attributedBody` blob that newer macOS versions use instead of `message.text`. It also accepts a generic CSV export.
- **Transform:** redacts phone numbers and emails, drops link-only and attachment-only messages, splits chats into conversations at 30-minute gaps, and merges bursts of consecutive texts into turns. It then pairs each of your replies with the conversation leading up to it.
- **Profile:** measures your texting style: average length, lowercase starts, punctuation, emoji use and favorites, laugh style ("lol" vs. "lmao" vs. 💀), and common phrases. These become plain-language rules in the system prompt.
- **Load:** writes `persona.json`, `examples.jsonl`, and `finetune.jsonl` (OpenAI fine-tuning format, if you want a dedicated model).

**2. Server (`server/`)**
- For each incoming text, it retrieves the most similar real exchanges (token-overlap similarity) and sends them to GPT as few-shot turns, along with the style rules and recent chat history.
- Photos go to **Google Cloud Vision** (labels, faces and expressions, landmarks, OCR). The result is summarized into a sentence the model reacts to in your voice.
- **Mock mode:** with no API keys it replies using your closest real message, so everything runs locally for free.

**3. Client (`client/`)**
- An iMessage-style thread with typing indicators. Multi-line replies arrive as separate bubbles, like a real burst of texts. Supports photo attachments.

## Quick start

```bash
# 1. Build your persona (on a Mac, copy chat.db first; Terminal needs Full Disk Access)
cp ~/Library/Messages/chat.db /tmp/chat.db
cd etl && python -m doppel_etl --chat-db /tmp/chat.db --name Zach --out ../server/data
#   or try it with the included synthetic sample:
python -m doppel_etl --csv sample/sample_messages.csv --name Zach --out ../server/data

# 2. Run the server (http://localhost:8080)
cd ../server && npm install
OPENAI_API_KEY=sk-... npm start          # omit the key for mock mode

# 3. Run the client (http://localhost:5173)
cd ../client && npm install && npm run dev
```

Without your own data, the server uses `server/data/*.sample.*`, a small **synthetic** persona.

> **Privacy:** your generated `persona.json`, `examples.jsonl`, and `finetune.jsonl` contain real message content, so they are git-ignored. Don't commit them or bake them into a public image.

## Deploy to Google Cloud Run

```bash
gcloud services enable run.googleapis.com vision.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
gcloud artifacts repositories create doppelganger --repository-format=docker --location=us-east1
printf "sk-..." | gcloud secrets create openai-api-key --data-file=-
gcloud builds submit --config cloudbuild.yaml
```

The Docker image builds the React client and serves it from the Node server in one container. On Cloud Run, the service account authenticates to Cloud Vision automatically. Give it the `roles/secretmanager.secretAccessor` role for the OpenAI key.

## API

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/persona` | Name, style rules, example count, active LLM and vision mode |
| POST | `/api/chat` | JSON or multipart: `message`, `history` (`[{role, text}]`), optional `image` → `{reply, imageDescription}` |
| GET | `/health` | Health check |

## Tests

```bash
cd etl && pytest -q          # chat.db parsing, attributedBody decoding, pairing, style analysis
cd server && npm test        # retrieval, prompt assembly, Vision summaries, HTTP API with mocked GPT and Vision
```
