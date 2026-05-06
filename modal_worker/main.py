from pathlib import Path
import modal

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SAAS_ROOT = BACKEND_ROOT.parent

app = modal.App("saas-worker")

# jrottenberg/ffmpeg ships a pre-built FFmpeg with NVDEC/NVENC support linked against
# the CUDA toolkit — the standard Ubuntu apt package does NOT include GPU hw-accel.
image = (
    modal.Image.from_registry(
        "jrottenberg/ffmpeg:6.1-cuda12.1-ubuntu22",
        add_python="3.11",
    )
    .apt_install("libass9", "libsndfile1", "fontconfig")
    .pip_install_from_requirements(str(BACKEND_ROOT / "requirements.txt"))
    .add_local_dir(str(BACKEND_ROOT / "fonts"), "/usr/share/fonts/truetype/custom", copy=True)
    .run_commands("fc-cache -f -v")
    .env(
        {
            "MINECRAFT_CLIP_PATH": "/assets/minecraft_loop.mp4",
            # jrottenberg image puts ffmpeg at /usr/local/bin/ffmpeg
            "IMAGEIO_FFMPEG_EXE": "/usr/local/bin/ffmpeg",
            "FFMPEG_BINARY": "/usr/local/bin/ffmpeg",
            "RENDER_BACKEND": "ffmpeg",
            "RENDER_VIDEO_CODEC": "h264_nvenc",
            "RENDER_AUDIO_CODEC": "aac",
            # p4 = good quality/speed balance for NVENC; replaces the CPU 'fast' preset
            "RENDER_PRESET": "p4",
            # 6 threads: leaves 2 cores for Python overhead and libass subtitle burn
            "FFMPEG_THREADS": "6",
            # Tells render_service_ffmpeg.py to use the NVDEC+NVENC code path
            "HWACCEL_DEVICE": "cuda",
            "TITLE_FONT_PATH": "/usr/share/fonts/truetype/custom/LuckiestGuy-Regular.ttf",
            "HANDLE_FONT_PATH": "/usr/share/fonts/truetype/custom/LuckiestGuy-Regular.ttf",
            "SUBTITLE_FONT_PATH": "/usr/share/fonts/truetype/custom/LuckiestGuy-Regular.ttf",
        }
    )
    # Local mounts stay at the end (fixes build-cache invalidation)
    .add_local_python_source("worker", "app", "modal_worker")
    .add_local_file(str(SAAS_ROOT / "minecraft_loop.mp4"), "/assets/minecraft_loop.mp4")
)

secrets = [modal.Secret.from_name("saas-worker-secrets")]

@app.function(
    image=image,
    secrets=secrets,
    timeout=1800,
    gpu="T4",
    # 8 CPUs: 6 for FFmpeg threads + 2 for Python/libass overhead.
    # With only 4 CPUs the software overlay + libass subtitle burn starved NVENC.
    cpu=8,
    # 12 GB: headroom for Whisper model + large frame buffers during two-pass render.
    memory=12288,
    # 60 s scaledown window reduces cold-starts when jobs arrive in bursts.
    scaledown_window=10,
)
@modal.concurrent(max_inputs=3)
def process_job(job_data):
    from modal_worker.pipeline import run_job_pipeline
    return run_job_pipeline(job_data)

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

    print("Launching job on Modal...")
    result = process_job.remote(job_data)
    print(f"Job finished! Result: {result}")
