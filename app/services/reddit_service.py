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

    def fetch_top_post(self, subreddit_name: str, excluded_post_ids: set[str] | None = None) -> dict:
        excluded_post_ids = excluded_post_ids or set()
        subreddit = self.client.subreddit(subreddit_name)
        candidate_windows = [("day", 75), ("week", 100), ("month", 100)]

        for time_filter, limit in candidate_windows:
            for post in subreddit.top(time_filter=time_filter, limit=limit):
                post_id = str(post.id)
                if post_id in excluded_post_ids:
                    continue
                if post.stickied or not post.selftext:
                    continue
                return {
                    "post_id": post_id,
                    "subreddit": subreddit_name,
                    "title": post.title,
                    "text": clean_text_for_narration(post.selftext),
                    "permalink": f"https://reddit.com{post.permalink}",
                }

        raise ValueError(
            f"No suitable unique Reddit post found for r/{subreddit_name}. "
            "Try another subreddit or broaden post-history limits."
        )
