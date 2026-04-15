import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from app.utils.text import sanitize_filename
from worker.api_client import WorkerApiClient, WorkerStopError
from worker.config import WorkerSettings
from worker.services.reddit_service import RedditScraperService
from worker.services.render_service import VideoRenderService
from worker.services.script_service import GeminiScriptService
from worker.services.storage_service import S3UploadService
from worker.services.subtitle_service import SubtitleService
from worker.services.tts_service import TTSProviderFactory
from worker.types import WorkerJob


LOGGER = logging.getLogger(__name__)


class WorkerPipeline:
    def __init__(self, settings: WorkerSettings, api_client: WorkerApiClient):
        self.settings = settings
        self.api_client = api_client
        self.scraper = RedditScraperService()
        self.script_service = GeminiScriptService()
        self.subtitle_service = SubtitleService()
        self.renderer = VideoRenderService()
        self.storage = S3UploadService(settings)
        self.tts_factory = TTSProviderFactory()

    def run(self, job: WorkerJob) -> None:
        with TemporaryDirectory(prefix=f"job-{job.id}-", dir=str(self.settings.local_work_dir)) as temp_dir:
            temp_dir_path = Path(temp_dir)

            LOGGER.info("Job %s: scraping Reddit content", job.id)
            story = self.scraper.fetch_top_post(job.subreddit)
            self.api_client.update_job(
                job.id,
                status="generating_script",
                progress=30,
                message=f"Selected post: {story['title']}",
                source_title=story["title"],
            )

            LOGGER.info("Job %s: generating script", job.id)
            script = self.script_service.generate_script(story["title"], story["text"])
            self.api_client.update_job(
                job.id,
                status="generating_tts",
                progress=55,
                message=f"Generating audio with {job.tts_provider}",
                source_title=story["title"],
                script=script,
            )

            LOGGER.info("Job %s: generating TTS", job.id)
            audio_path = temp_dir_path / f"{sanitize_filename(story['title'])}.wav"
            self.tts_factory.get_provider(job.tts_provider).generate(script, audio_path)
            self.api_client.update_job(
                job.id,
                status="generating_subtitles",
                progress=75,
                message="Generating subtitles",
                source_title=story["title"],
                script=script,
            )

            LOGGER.info("Job %s: generating subtitles", job.id)
            subtitles = self.subtitle_service.generate(audio_path, script, story["title"])
            self.api_client.update_job(
                job.id,
                status="rendering_video",
                progress=90,
                message="Rendering final video",
                source_title=story["title"],
                script=script,
            )

            LOGGER.info("Job %s: rendering video", job.id)
            local_video_path = temp_dir_path / self.renderer.build_output_name(story["title"])
            rendered_path, duration_seconds = self.renderer.render(
                title_text=story["title"],
                tiktok_handle=self.renderer.settings.tiktok_handle,
                audio_path=audio_path,
                subtitles=subtitles,
                output_path=local_video_path,
            )

            LOGGER.info("Job %s: uploading final video to S3", job.id)
            target_name = f"{job.id}/final.mp4"
            video_url = self.storage.upload_video(rendered_path, target_name)

            LOGGER.info("Job %s: completing job", job.id)
            self._complete_with_retry(job.id, video_url, duration_seconds)

    def _complete_with_retry(self, job_id: int, video_url: str, duration_seconds: float | None) -> None:
        while True:
            try:
                self.api_client.complete_job(job_id, video_url, duration_seconds=duration_seconds)
                return
            except WorkerStopError:
                raise
            except Exception:
                LOGGER.warning("Job %s: completion failed after upload, retrying", job_id, exc_info=True)
                time.sleep(max(self.settings.poll_interval_seconds, self.settings.api_retry_backoff_seconds))
