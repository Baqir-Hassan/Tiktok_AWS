import logging
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import time

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


LOGGER = logging.getLogger(__name__)


class WorkerPipeline:
    def __init__(self, settings: WorkerSettings, api_client: WorkerApiClient):
        self.settings = settings
        self.api_client = api_client
        self.scraper = RedditScraperService()
        self.script_service = GroqScriptService()
        self.subtitle_service = SubtitleService()
        self.renderer = create_video_renderer()
        self.storage = S3UploadService(settings)
        self.tts_factory = TTSProviderFactory()

    def run(self, job: WorkerJob) -> None:
        with TemporaryDirectory(prefix=f"job-{job.id}-", dir=str(self.settings.local_work_dir)) as temp_dir:
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
                story = self.scraper.fetch_top_post(
                    job.subreddit,
                    excluded_post_ids=set(job.excluded_reddit_post_ids or []),
                )
            self.api_client.update_job(
                job.id,
                status="generating_script",
                progress=30,
                message=f"Selected post: {story['title']}",
                source_title=story["title"],
                source_post_id=story.get("post_id"),
                source_permalink=story.get("permalink"),
            )

            LOGGER.info("Job %s: generating script", job.id)
            script = self.script_service.generate_script(story["title"], story["text"])
            cleaned_script = sanitize_generated_script_for_tts(script)
            if cleaned_script != script:
                LOGGER.info(
                    "Job %s: sanitized narration script (raw_len=%s cleaned_len=%s)",
                    job.id,
                    len(script),
                    len(cleaned_script),
                )
            script_for_narration = cleaned_script or script
            spoken_script = self._build_spoken_script(story["title"], script_for_narration)
            self.api_client.update_job(
                job.id,
                status="generating_tts",
                progress=55,
                message=f"Generating audio with {job.tts_provider}",
                source_title=story["title"],
                script=script_for_narration,
            )

            LOGGER.info("Job %s: generating TTS", job.id)
            audio_path = temp_dir_path / f"{sanitize_filename(story['title'])}.wav"
            self.tts_factory.get_provider(job.tts_provider).generate(spoken_script, audio_path)
            self.api_client.update_job(
                job.id,
                status="generating_subtitles",
                progress=75,
                message="Generating subtitles",
                source_title=story["title"],
                script=script_for_narration,
            )

            LOGGER.info("Job %s: generating subtitles", job.id)
            subtitles = self.subtitle_service.generate(audio_path, spoken_script, story["title"])
            LOGGER.info(
                "Job %s: subtitle chunks=%s title_duration=%.3fs",
                job.id,
                len(subtitles.chunks),
                subtitles.title_duration,
            )
            self.api_client.update_job(
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
                self.renderer.settings.render_video_codec,
                self.renderer.settings.render_amf_quality
                if self.renderer.settings.render_video_codec.endswith("_amf")
                else self.renderer.settings.render_preset,
                self.renderer.settings.render_amf_usage
                if self.renderer.settings.render_video_codec.endswith("_amf")
                else "n/a",
            )
            local_video_path = temp_dir_path / self.renderer.build_output_name(story["title"])
            rendered_path, duration_seconds = self.renderer.render(
                title_text=story["title"],
                tiktok_handle=self.renderer.settings.tiktok_handle,
                audio_path=audio_path,
                subtitles=subtitles,
                output_path=local_video_path,
            )
            preview_path = self.settings.local_preview_dir / f"job-{job.id}-preview.mp4"
            shutil.copy2(rendered_path, preview_path)
            LOGGER.info("Job %s: local preview saved to %s", job.id, preview_path)

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

    def _build_spoken_script(self, title_text: str, script: str) -> str:
        normalized_title = title_text.strip()
        normalized_script = script.strip()
        if not normalized_title:
            return normalized_script
        if not normalized_script:
            return normalized_title
        return f"{normalized_title}\n\n{normalized_script}"
