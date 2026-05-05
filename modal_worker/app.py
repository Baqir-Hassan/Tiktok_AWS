from pathlib import Path

import modal

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAAS_ROOT = BACKEND_ROOT.parent

app = modal.App("saas-worker")

image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg", "libass9", "libsndfile1")
    .pip_install_from_requirements(str(BACKEND_ROOT / "requirements.txt"))
    .add_local_file(str(SAAS_ROOT / "minecraft_loop.mp4"), "/assets/minecraft_loop.mp4")
    .env(
        {
            "MINECRAFT_CLIP_PATH": "/assets/minecraft_loop.mp4",
            "IMAGEIO_FFMPEG_EXE": "/usr/bin/ffmpeg",
            "FFMPEG_BINARY": "/usr/bin/ffmpeg",
            "RENDER_BACKEND": "ffmpeg",
            "RENDER_VIDEO_CODEC": "libx264",
            "RENDER_AUDIO_CODEC": "aac",
            "RENDER_PRESET": "veryfast",
            "FFMPEG_THREADS": "4",
        }
    )
    .add_local_python_source("worker", "app", "modal_worker")
)

secrets = [modal.Secret.from_name("saas-worker-secrets")]

@app.function(
    image=image,
    secrets=secrets,
    timeout=1800,
)
def process_job(job_data):
    from modal_worker.pipeline import run_job_pipeline

    return run_job_pipeline(job_data)


@app.local_entrypoint()
def main():
    import os

    os.environ.setdefault("LOCAL_MODAL_TEST", "1")
    job_data = {
        "id": 1,
        "user_id": 1,
        "status": "queued",
        "subreddit": "test",
        "script": None,
        "tts_provider": "edge",
        "source_title": None,
        "source_text": None,
        "source_post_id": None,
        "source_permalink": None,
        "excluded_reddit_post_ids": [],
        "video_url": None,
        "uploaded_video_url": None,
        "video_upload_status": "pending",
        "error_message": None,
        "progress": 0,
        "attempts": 0,
        "claimed_by": None,
        "claimed_at": None,
        "heartbeat_at": None,
        "lease_expires_at": None,
        "created_at": "2026-05-05T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "custom_story": None,
        "custom_story_title": None,
    }
    from modal_worker.pipeline import run_job_pipeline
    result = run_job_pipeline(job_data)
    print(result)
