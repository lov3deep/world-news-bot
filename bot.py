import tweepy
import datetime
import os
from typing import List, Tuple

# === CONFIGURATION ===
# Fill in your X/Twitter API credentials (get them from https://developer.x.com)
CONSUMER_KEY = "your_consumer_key"
CONSUMER_SECRET = "your_consumer_secret"
ACCESS_TOKEN = "your_access_token"
ACCESS_SECRET = "your_access_secret"
BEARER_TOKEN = "your_bearer_token"  # Optional but recommended

# List of reputable worldwide news accounts (balanced sources)
NEWS_ACCOUNTS = [
    "Reuters", "AP", "BBCWorld", "AFP", "AlJazeera", 
    "nytimes", "guardian", "WSJ", "CNN", "FoxNews"
]

# How many top stories to post in the thread
TOP_N = 5

# Engagement weight: likes + retweets + replies + quotes
def calculate_engagement(metrics: dict) -> int:
    return (metrics['like_count'] +
            metrics['retweet_count'] +
            metrics['reply_count'] +
            metrics['quote_count'])

# === BOT LOGIC ===
def fetch_top_news_last_hour() -> List[Tuple[int, str, str, str, str]]:
    """
    Fetch recent tweets from news accounts in the last completed hour,
    sort by engagement, and return top stories with:
    (engagement_score, headline_text, article_url, source_username)
    """
    client = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_secret=ACCESS_SECRET,
        wait_on_rate_limit=True
    )

    # Calculate time window for the previous completed hour (UTC)
    now = datetime.datetime.utcnow()
    end_time = now.replace(minute=0, second=0, microsecond=0)
    start_time = end_time - datetime.timedelta(hours=1)

    # Build query: from any of the news accounts, exclude retweets
    accounts_query = " OR ".join([f"from:{acc}" for acc in NEWS_ACCOUNTS])
    query = f"({accounts_query}) -is:retweet"

    # Search recent tweets
    tweets = []
    for response in tweepy.Paginator(
        client.search_recent_tweets,
        query=query,
        start_time=start_time,
        end_time=end_time,
        tweet_fields=["public_metrics", "entities", "author_id"],
        expansions=["author_id"],
        max_results=100
    ):
        if not response.data:
            continue

        users = {u.id: u for u in response.includes.get("users", [])}

        for tweet in response.data:
            author = users.get(tweet.author_id)
            if not author:
                continue

            # Extract first URL if present (usually the article link)
            url = ""
            if tweet.entities and "urls" in tweet.entities and tweet.entities["urls"]:
                url = tweet.entities["urls"][0].get("expanded_url", "")

            engagement = calculate_engagement(tweet.public_metrics)

            tweets.append({
                "engagement": engagement,
                "text": tweet.text.strip(),
                "url": url,
                "username": author.username
            })

    # Sort by engagement descending
    tweets.sort(key=lambda x: x["engagement"], reverse=True)

    # Return top N
    top_stories = []
    for t in tweets[:TOP_N]:
        top_stories.append((
            t["engagement"],
            t["text"],
            t["url"],
            t["username"]
        ))

    return top_stories

def post_engaging_thread(top_stories: List[Tuple[int, str, str, str]]):
    if not top_stories:
        print("No top news found for this hour.")
        return

    client = tweepy.Client(
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_secret=ACCESS_SECRET,
        wait_on_rate_limit=True
    )

    # First tweet (intro + #1 story)
    story = top_stories[0]
    intro_text = "🌍 Top World News This Hour:\n\n"
    story_text = f"🔥 1. {story[1]}\n\nSource: @{story[3]}"
    if story[2]:
        story_text += f"\n🔗 {story[2]}"
    story_text += "\n\n#WorldNews #BreakingNews"
    full_text = intro_text + story_text

    response = client.create_tweet(text=full_text)
    if not response.data:
        print("Failed to post intro tweet.")
        return
    previous_id = response.data["id"]
    print(f"Posted intro tweet: {previous_id}")

    # Remaining stories as thread replies
    for i, story in enumerate(top_stories[1:], start=2):
        story_text = f"{i}. {story[1]}\n\nSource: @{story[3]}"
        if story[2]:
            story_text += f"\n🔗 {story[2]}"
        story_text += f"\n\n(Thread {i}/{len(top_stories)}) #WorldNews"

        response = client.create_tweet(
            text=story_text,
            in_reply_to_tweet_id=previous_id
        )
        if response.data:
            previous_id = response.data["id"]
            print(f"Posted thread tweet {i}: {previous_id}")
        else:
            print(f"Failed to post thread tweet {i}")

    # Optional final tweet to boost engagement
    client.create_tweet(
        text="Which story shocked you the most? 👇 Reply below!\n#News",
        in_reply_to_tweet_id=previous_id
    )

# === RUN THE BOT ===
if __name__ == "__main__":
    print("Fetching top news for the last hour...")
    top_stories = fetch_top_news_last_hour()
    
    print(f"Found {len(top_stories)} top stories.")
    for i, s in enumerate(top_stories, 1):
        print(f"{i}. [{s[0]} engagement] @{s[3]}: {s[1][:80]}...")

    print("\nPosting engaging thread...")
    post_engaging_thread(top_stories)
