# Railway Deployment

Deploy both services (web + api) on Railway.

## Setup

1. Create a new Railway project
2. Add two services from the same repo:

### Web Service (Next.js)
- **Root Directory**: `apps/web`
- **Build Command**: `pnpm install && pnpm build`
- **Start Command**: `pnpm start`
- **Port**: `3000`

### API Service (FastAPI)
- **Root Directory**: `services/api`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Environment Variables

Set these on the API service:

| Variable | Value | Required |
|----------|-------|----------|
| `B2_REGION` | Your B2 region, e.g. `us-west-004` | required |
| `B2_APPLICATION_KEY_ID` | Your B2 key ID | required |
| `B2_APPLICATION_KEY` | Your B2 key | required |
| `B2_BUCKET_NAME` | Your bucket name | required |
| `B2_PUBLIC_URL_BASE` | Public bucket or CDN base URL | optional |
| `API_CORS_ORIGINS` | Your web service URL (e.g., `https://web-production-xxx.up.railway.app`) | required |
| `ASSEMBLYAI_API_KEY` | AssemblyAI key — used for diarized transcription. | required |
| `LLM_PROVIDER` | LLM provider for summary + action-item extraction. Default `openai`; alt `anthropic`. | optional |
| `OPENAI_API_KEY` | OpenAI key — used for summary + action-item extraction. Without it the pipeline still runs ASR but the next stage records `state=failed`. | required (default LLM) |
| `OPENAI_MODEL` | Override the OpenAI model. Default `gpt-4o-mini`. | optional |
| `ANTHROPIC_API_KEY` | Anthropic key — used for summary + action-item extraction when `LLM_PROVIDER=anthropic`. | required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | Override the Claude model. Default `claude-haiku-4-5-20251001`. | optional |

Set this on the Web service:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Your API service URL (e.g., `https://api-production-xxx.up.railway.app`) |
