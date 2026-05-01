# TikTok SaaS Backend

Production-style backend architecture for generating short-form Reddit videos with Gemini, Piper TTS, Whisper subtitles, and MoviePy rendering.

## What Changed

- Replaced the old monolith with a FastAPI API layer and an independent worker process.
- Migrated TTS to a provider-based Piper-first architecture.
- Made `PiperTTSProvider` the default and only active text-to-speech engine.
- Added database-backed jobs, logs, credits, JWT auth, storage abstraction, and AWS-friendly deployment structure.

## Architecture

```text
backend/
  app/
    api/
      routes/
    core/
    models/
    providers/
      tts/
        base.py
        piper.py
    pipelines/
    services/
    workers/
    utils/
  worker/
    main.py
  docker/
    Dockerfile
  main.py
```

## API Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{id}`

## Job Lifecycle

- `queued`
- `scraping`
- `generating_script`
- `generating_tts`
- `generating_subtitles`
- `rendering_video`
- `completed`
- `failed`

## Worker Flow

1. Poll PostgreSQL for the next queued job.
2. Atomically claim the job to prevent duplicate execution.
3. Scrape Reddit content.
4. Generate narration with Gemini.
5. Generate audio through `tts_provider.generate(text, output_path)`.
6. Create subtitles with Whisper, or use the Gemini fallback if Whisper fails.
7. Render the final video with MoviePy.
8. Upload the final video to local storage or S3.
9. Persist job status, logs, and video metadata.

## Database Schema

### `users`

- `id`
- `email`
- `password_hash`
- `credits`
- `created_at`

### `jobs`

- `id`
- `user_id`
- `status`
- `subreddit`
- `script`
- `tts_provider`
- `video_url`
- `error_message`
- `created_at`

Operational support fields were added for worker orchestration:

- `source_title`
- `source_text`
- `attempts`
- `started_at`
- `completed_at`

### `job_logs`

- `id`
- `job_id`
- `stage`
- `message`
- `timestamp`

### `videos`

- `id`
- `job_id`
- `url`
- `duration`

## Piper TTS Migration

The pipeline no longer calls any TTS vendor directly. All narration generation now goes through:

```python
tts_provider.generate(text, output_path)
```

Implemented providers:

- `PiperTTSProvider` as the default
- `ChatterboxTTSProvider` stub for future GPU scaling
- `CoquiTTSProvider` stub for future optional expansion

### Piper Runtime Requirements

Set these environment variables:

```env
PIPER_BINARY=piper
PIPER_MODEL_PATH=/absolute/path/to/model.onnx
PIPER_CONFIG_PATH=/absolute/path/to/model.onnx.json
```

The worker expects the Piper binary and model files to already exist on the host or container image.

## Local Development

Create `.env`:

```env
SECRET_KEY=replace-this
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tiktok_saas
GOOGLE_API_KEY=your_gemini_api_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=tiktok-saas/1.0
PIPER_BINARY=piper
PIPER_MODEL_PATH=/models/en_US-lessac-medium.onnx
PIPER_CONFIG_PATH=/models/en_US-lessac-medium.onnx.json
MINECRAFT_CLIP_PATH=/app/assets/minecraft_loop.mp4
TIKTOK_HANDLE=@YourHandle
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/app/storage/videos
```

Start with Docker Compose:

```bash
docker compose up --build
```

Services:

- API on `http://localhost:8000`
- PostgreSQL on `localhost:5432`
- Independent worker in its own container

Run without Docker:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
python -m worker.main
```

## AWS Deployment Plan

### API

- Deploy the FastAPI app on a small EC2 instance.
- Run it behind `gunicorn` with `uvicorn.workers.UvicornWorker`.
- Put Nginx in front for reverse proxying.

### Database

- Use PostgreSQL on Amazon RDS.
- Point `DATABASE_URL` to the RDS instance.

### Storage

- Use S3 for final rendered videos.
- Switch `STORAGE_BACKEND=s3` and configure the bucket credentials.

### Worker

- For the MVP, run the worker on a developer machine.
- Later, move the worker to another EC2 host or ECS without changing API contracts.

### Recommended Low-Cost Baseline

- One small EC2 API host
- One RDS PostgreSQL instance
- Final videos stored in S3
- No GPU dependency
- No microservice sprawl

See [DEPLOYMENT_AWS.md](../DEPLOYMENT_AWS.md) for the full production deployment setup.

## Portfolio Talking Points

- Async SaaS backend with explicit job state transitions
- Clear separation between API, worker, providers, pipeline, and storage
- Provider-based TTS system with Piper as the default offline engine
<<<<<<< HEAD
- AWS-ready deployment path without needing to redesign the application later
=======
- AWS-ready deployment path without needing to redesign the application later
>>>>>>> d67fd6b7fa836cfad41557c64a59ea947487770f
