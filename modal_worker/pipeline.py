import logging
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import time
from typing import Any

# Import from project
from app.utils.text import sanitize_filename, sanitize_generated_script_for_tts
from worker.api_client import WorkerApiClient, WorkerStopError
from worker.config import WorkerSettings
from worker.services.reddit_service import RedditScraperService
from worker.services.render_service import create_video_renderer
from worker.services.script_service import GroqScriptService
from worker.services.storage_service import S3UploadService
from worker.services.subtitle_service import SubtitleService
from worker.services.tts_service import TTSProviderFactory
from worker.types import WorkerJob


class LocalWorkerApiClient:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings

    def update_job(
        self,
        job_id: int,
        status: str,
        progress: int,
        message: str,
        source_title: str | None = None,
        source_post_id: str | None = None,
        source_permalink: str | None = None,
        script: str | None = None,
    ) -> dict[str, Any]:
        LOGGER.info(
            "[local test] update_job: %s %s %s %s",
            job_id,
            status,
            progress,
            message,
        )
        return {}

    def complete_job(self, job_id: int, video_url: str, duration_seconds: float | None = None) -> dict[str, Any]:
        LOGGER.info("[local test] complete_job: %s %s %s", job_id, video_url, duration_seconds)
        return {"video_url": video_url}

    def fail_job(self, job_id: int, error_message: str) -> dict[str, Any]:
        LOGGER.info("[local test] fail_job: %s %s", job_id, error_message)
        return {"error_message": error_message}


class LocalStorageService:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings

    def upload_video(self, source_path: Path, target_name: str) -> str:
        target_dir = self.settings.local_preview_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / Path(target_name).name
        shutil.copy2(source_path, target_path)
        LOGGER.info("[local test] saved video to %s", target_path)
        return str(target_path.resolve())


LOGGER = logging.getLogger(__name__)


def get_modal_settings() -> WorkerSettings:
    """Get settings for Modal environment from secrets/env vars."""
    # Assume secrets set env vars
    local_work_dir = Path("/tmp/modal-worker").resolve()
    local_work_dir.mkdir(parents=True, exist_ok=True)
    local_preview_dir = local_work_dir / "previews"
    local_preview_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_binary = Path("/usr/bin/ffmpeg")  # Installed in image

    return WorkerSettings(
        api_base_url=os.getenv("API_BASE_URL", "").rstrip("/"),
        worker_api_key=os.getenv("WORKER_API_KEY", ""),
        worker_id=os.getenv("WORKER_ID", "modal-worker-1"),
        poll_interval_seconds=5,
        request_timeout_seconds=30,
        api_retry_attempts=3,
        api_retry_backoff_seconds=1.5,
        heartbeat_interval_seconds=30,
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        s3_bucket=os.getenv("S3_BUCKET", ""),
        s3_prefix=os.getenv("S3_PREFIX", ""),
        public_s3_base_url=os.getenv("PUBLIC_S3_BASE_URL"),
        local_work_dir=local_work_dir,
        local_preview_dir=local_preview_dir,
        ffmpeg_binary=ffmpeg_binary,
    )


def run_job_pipeline(job_data: dict) -> dict:
    """Run the job pipeline for a given job data."""
    # Create settings
    settings = get_modal_settings()
    
    # Local test mode bypasses API/state updates and S3 upload.
    use_local_mode = os.getenv("LOCAL_MODAL_TEST", "0") == "1" or not os.getenv("API_BASE_URL")
    api_client = LocalWorkerApiClient(settings) if use_local_mode else WorkerApiClient(settings)
    
    # Convert job_data to WorkerJob
    job = WorkerJob.from_api(job_data)
    
    # Initialize services
    scraper = RedditScraperService()
    script_service = GroqScriptService()
    subtitle_service = SubtitleService()
    renderer = create_video_renderer()
    storage = LocalStorageService(settings) if use_local_mode else S3UploadService(settings)
    tts_factory = TTSProviderFactory()
    
    try:
        with TemporaryDirectory(prefix=f"job-{job.id}-", dir=str(settings.local_work_dir)) as temp_dir:
            temp_dir_path = Path(temp_dir)

            if job.custom_story:
                LOGGER.info("Job %s: using custom story", job.id)
                story = {
                    "title": job.custom_story_title or "Custom Story",
                    "text": job.custom_story,
                    "post_id": None,
                    "permalink": None,
                }
            else:  
                LOGGER.info("Job %s: scraping Reddit content", job.id)
                story = scraper.fetch_top_post(
                    job.subreddit,
                    excluded_post_ids=set(job.excluded_reddit_post_ids or []),
                )
            api_client.update_job(
                job.id,
                status="generating_script",
                progress=30,
                message=f"Selected post: {story['title']}",
                source_title=story["title"],
                source_post_id=story.get("post_id"),
                source_permalink=story.get("permalink"),
            )

            LOGGER.info("Job %s: generating script", job.id)
            script = script_service.generate_script(story["title"], story["text"])
            cleaned_script = sanitize_generated_script_for_tts(script)
            if cleaned_script != script:
                LOGGER.info(
                    "Job %s: sanitized narration script (raw_len=%s cleaned_len=%s)",
                    job.id,
                    len(script),
                    len(cleaned_script),
                )
            script_for_narration = cleaned_script or script
            spoken_script = _build_spoken_script(story["title"], script_for_narration)
            api_client.update_job(
                job.id,
                status="generating_tts",
                progress=55,
                message=f"Generating audio with {job.tts_provider}",
                source_title=story["title"],
                script=script_for_narration,
            )

            LOGGER.info("Job %s: generating TTS", job.id)
            audio_path = temp_dir_path / f"{sanitize_filename(story['title'])}.wav"
            tts_factory.get_provider(job.tts_provider).generate(spoken_script, audio_path)
            api_client.update_job(
                job.id,
                status="generating_subtitles",
                progress=75,
                message="Generating subtitles",
                source_title=story["title"],
                script=script_for_narration,
            )

            LOGGER.info("Job %s: generating subtitles", job.id)
            subtitles = subtitle_service.generate(audio_path, spoken_script, story["title"])
            LOGGER.info(
                "Job %s: subtitle chunks=%s title_duration=%.3fs",
                job.id,
                len(subtitles.chunks),
                subtitles.title_duration,
            )
            api_client.update_job(
                job.id,
                status="rendering_video",
                progress=90,
                message="Rendering final video",
                source_title=story["title"],
                script=script_for_narration,
            )

            LOGGER.info("Job %s: rendering video", job.id)
            LOGGER.info(
                "Job %s: rendering with codec=%s preset=%s amf_usage=%s",
                job.id,
                renderer.settings.render_video_codec,
                renderer.settings.render_amf_quality
                if renderer.settings.render_video_codec.endswith("_amf")
                else renderer.settings.render_preset,
                renderer.settings.render_amf_usage
                if renderer.settings.render_video_codec.endswith("_amf")
                else "n/a",
            )
            local_video_path = temp_dir_path / renderer.build_output_name(story["title"])
            rendered_path, duration_seconds = renderer.render(
                title_text=story["title"],
                tiktok_handle=renderer.settings.tiktok_handle,
                audio_path=audio_path,
                subtitles=subtitles,
                output_path=local_video_path,
            )
            # Note: No local preview in Modal, as ephemeral

            LOGGER.info("Job %s: uploading final video to S3", job.id)
            target_name = f"{job.id}/final.mp4"
            video_url = storage.upload_video(rendered_path, target_name)

            LOGGER.info("Job %s: completing job", job.id)
            _complete_with_retry(api_client, settings, job.id, video_url, duration_seconds)
            
            return {"status": "completed", "video_url": video_url}
    
    except Exception as e:
        LOGGER.error(f"Job {job.id} failed: {e}", exc_info=True)
        try:
            api_client.update_job(job.id, status="failed", message=str(e))
        except:
            pass
        raise


def _complete_with_retry(api_client: WorkerApiClient, settings: WorkerSettings, job_id: int, video_url: str, duration_seconds: float | None) -> None:
    while True:
        try:
            api_client.complete_job(job_id, video_url, duration_seconds=duration_seconds)
            return
        except WorkerStopError:
            raise
        except Exception:
            LOGGER.warning("Job %s: completion failed after upload, retrying", job_id, exc_info=True)
            time.sleep(max(settings.poll_interval_seconds, settings.api_retry_backoff_seconds))


def _build_spoken_script(title_text: str, script: str) -> str:
    normalized_title = title_text.strip()
    normalized_script = script.strip()
    if not normalized_title:
        return normalized_script
    if not normalized_script:
        return normalized_title
    return f"{normalized_title}\n\n{normalized_script}"