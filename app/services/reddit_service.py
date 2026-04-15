import praw

from app.core.config import get_settings
from app.utils.text import clean_text_for_narration


class RedditScraperService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

    def fetch_top_post(self, subreddit_name: str) -> dict:
        subreddit = self.client.subreddit(subreddit_name)
        for post in subreddit.top(time_filter="day", limit=10):
            if not post.stickied and post.selftext:
                return {
                    "subreddit": subreddit_name,
                    "title": post.title,
                    "text": clean_text_for_narration(post.selftext),
                    "permalink": f"https://reddit.com{post.permalink}",
                }
        raise ValueError(f"No suitable Reddit post found for r/{subreddit_name}")
