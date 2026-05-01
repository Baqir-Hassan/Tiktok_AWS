from app.services.reddit_service import RedditScraperService


def get_reddit_posts(subreddits, limit=1):
    service = RedditScraperService()
    posts = []
    for subreddit in subreddits[:limit]:
        posts.append(service.fetch_top_post(subreddit))
    return posts
