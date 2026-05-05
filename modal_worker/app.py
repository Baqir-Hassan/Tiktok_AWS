import modal
import os

# Define the Modal app
app = modal.App("saas-worker")

# Define the image with dependencies and local source packages
image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .apt_install("ffmpeg")  # Install FFmpeg
    .run_commands(
        "apt-get update && apt-get install -y libsndfile1",  # For audio processing
    )
    .add_local_python_source("worker", "app", "modal_worker")
)

# Secrets for API keys, etc.
# In local testing, we skip Modal-managed secrets and rely on environment variables.
# For deployed Modal usage, add Modal secrets here and enable the `secrets` list.
secrets = []

# Placeholder for job processing function
@app.function(
    image=image,
    secrets=secrets,
    timeout=1800  # 30 minutes timeout for video processing
)
def process_job(job_data):
    # Import and run pipeline
    from modal_worker.pipeline import run_job_pipeline
    return run_job_pipeline(job_data)

# Local test entrypoint
@app.local_entrypoint()
def main():
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