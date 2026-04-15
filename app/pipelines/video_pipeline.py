from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.models.job_log import JobLog
from app.models.video import Video
from app.core.config import get_settings
from app.services.job_service import JobService
from app.services.reddit_service import RedditScraperService
from app.services.render_service import VideoRenderService
from app.services.script_service import GeminiScriptService
from app.services.storage_service import StorageFactory
from app.services.subtitle_service import SubtitleService
from app.services.tts_service import TTSProviderFactory
from app.utils.text import sanitize_filename


class VideoGenerationPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.jobs = JobService(db)
        self.scraper = RedditScraperService()
        self.script_service = GeminiScriptService()
        self.subtitle_service = SubtitleService()
        self.renderer = VideoRenderService()
        self.storage = StorageFactory.create()
        self.tts_factory = TTSProviderFactory()

    def run(self, job: Job) -> None:
        with TemporaryDirectory(prefix=f"job-{job.id}-") as temp_dir:
            temp_dir_path = Path(temp_dir)

            self.jobs.update_status(job, JobStatus.SCRAPING, f"Fetching Reddit content from r/{job.subreddit}")
            story = self.scraper.fetch_top_post(job.subreddit)
            job.source_title = story["title"]
            job.source_text = story["text"]
            self.db.add(job)
            self.db.add(JobLog(job_id=job.id, stage=JobStatus.SCRAPING.value, message=f"Selected post: {story['title']}"))
            self.db.commit()

            self.jobs.update_status(job, JobStatus.GENERATING_SCRIPT, "Generating narration script with Gemini")
            job.script = self.script_service.generate_script(story["title"], story["text"])
            self.db.add(job)
            self.db.commit()

            self.jobs.update_status(job, JobStatus.GENERATING_TTS, f"Generating audio with {job.tts_provider}")
            audio_path = temp_dir_path / f"{sanitize_filename(story['title'])}.wav"
            self.tts_factory.get_provider(job.tts_provider).generate(job.script, audio_path)

            self.jobs.update_status(job, JobStatus.GENERATING_SUBTITLES, "Generating subtitles")
            subtitles = self.subtitle_service.generate(audio_path, job.script, story["title"])

            self.jobs.update_status(job, JobStatus.RENDERING_VIDEO, "Rendering final video")
            local_video_path = temp_dir_path / self.renderer.build_output_name(story["title"])
            rendered_path, duration = self.renderer.render(
                title_text=story["title"],
                tiktok_handle=self.settings.tiktok_handle,
                audio_path=audio_path,
                subtitles=subtitles,
                output_path=local_video_path,
            )

            storage_name = f"job-{job.id}-{sanitize_filename(local_video_path.name)}"
            video_url = self.storage.store_video(rendered_path, storage_name)
            job.video_url = video_url
            self.db.add(job)
            self.db.add(Video(job_id=job.id, url=video_url, duration=duration))
            self.db.commit()

            self.jobs.update_status(job, JobStatus.COMPLETED, f"Video stored at {video_url}")
