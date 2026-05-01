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
from app.services.script_service import GroqScriptService
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
        self.script_service = GroqScriptService()
        self.subtitle_service = SubtitleService()
        self.renderer = VideoRenderService()
        self.storage = StorageFactory.create()
        self.tts_factory = TTSProviderFactory()

    def run(self, job: Job) -> None:
        with TemporaryDirectory(prefix=f"job-{job.id}-") as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Use custom story if provided, otherwise scrape Reddit
            if job.source_text and job.source_title:
                story = {"title": job.source_title, "text": job.source_text}
                self.jobs.update_status(job, JobStatus.SCRAPING, "Using custom story provided by user")
                self.db.add(JobLog(job_id=job.id, stage=JobStatus.SCRAPING.value, message=f"Custom story: {story['title']}"))
                self.db.commit()
            else:
                self.jobs.update_status(job, JobStatus.SCRAPING, f"Fetching Reddit content from r/{job.subreddit}")
                story = self.scraper.fetch_top_post(job.subreddit)
                job.source_title = story["title"]
                job.source_text = story["text"]
                self.db.add(job)
                self.db.add(JobLog(job_id=job.id, stage=JobStatus.SCRAPING.value, message=f"Selected post: {story['title']}"))
                self.db.commit()

        # rest of pipeline continues unchanged from here...

            storage_name = f"job-{job.id}-{sanitize_filename(local_video_path.name)}"
            video_url = self.storage.store_video(rendered_path, storage_name)
            job.video_url = video_url
            self.db.add(job)
            self.db.add(Video(job_id=job.id, url=video_url, duration=duration))
            self.db.commit()

            self.jobs.update_status(job, JobStatus.COMPLETED, f"Video stored at {video_url}")
