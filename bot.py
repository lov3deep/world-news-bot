import os
import datetime
import requests
import json

# === CONFIGURATION ===
XAI_API_KEY = "your_xai_api_key_here"  # From console.x.ai
X_CONSUMER_KEY = "your_x_consumer_key"
X_CONSUMER_SECRET = "your_x_consumer_secret"
X_ACCESS_TOKEN = "your_x_access_token"
X_ACCESS_SECRET = "your_x_access_token_secret"  # Fixed name

TOP_N = 5
MODEL = "grok-4"  # Or "grok-beta" / latest available

# Grok prompt to get top news
NEWS_PROMPT = """
Provide a concise list of the top 5 most important worldwide news stories right now (last hour if possible).
For each story:
- Number it (1 to 5)
- Give a short engaging headline (under 20 words)
- One-sentence summary
- Main source (e.g., Reuters, BBC) if known
- Direct article link if available

Focus on global impact, breaking events, politics, tech, disasters, etc.
Rank by worldwide discussion and importance.
Output only the numbered list — no intro text.
"""

def fetch_top_news_via_grok():
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": NEWS_PROMPT}],
        "temperature": 0.7,
        "max_tokens": 800,
        # Enable real-time search/tools for fresh news
        "search_parameters": {"mode": "auto"}  # Or enable_search: true if needed
    }

    response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} {response.text}")
        return []

    content = response.json()["choices"][0]["message"]["content"].strip()
    lines = [line.strip() for line in content.split("\n") if line.strip() and not line.startswith("**")]
    
    stories = []
    current = {}
    for line in lines:
        if line.startswith(("1.", "2.", "3.", "4.", "5.")):
            if current:
                stories.append(current)
            current = {"num": line.split(".", 1)[0], "text": line.split(".", 1)[1].strip()}
        elif "http" in line:
            current["url"] = line
        elif "Source:" in line.lower():
            current["source"] = line
        else:
            current["text"] += " " + line
    if current:
        stories.append(current)
    
    return stories[:TOP_N]

def post_engaging_thread(stories):
    if not stories:
        print("No news stories fetched.")
        return

    # Use requests for posting (simple v2 endpoint)
    auth_headers = {
        "Authorization": f"Bearer {os.getenv('X_BEARER_TOKEN', '')}",  # If you have it
        "Content-Type": "application/json"
    }
    # Better: Use OAuth1 for posting (install requests-oauthlib or keep tweepy for posting only)
    # Keeping tweepy for posting since it's easy
    import tweepy
    client = tweepy.Client(
        consumer_key=X_CONSUMER_KEY,
        consumer_secret=X_CONSUMER_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

    intro = "🌍 Top World News This Hour (via Grok real-time search):\n\n"
    first_text = intro + f"🔥 {stories[0].get('num', '1')}. {stories[0].get('text', '')}"
    if "url" in stories[0]:
        first_text += f"\n🔗 {stories[0]['url']}"
    first_text += "\n\n#WorldNews #BreakingNews"

    resp = client.create_tweet(text=first_text)
    if not resp.data:
        return
    prev_id = resp.data.id

    for story in stories[1:]:
        text = f"{story.get('num', '')}. {story.get('text', '')}"
        if "url" in story:
            text += f"\n🔗 {story['url']}"
        text += f"\n\n(Thread) #WorldNews"
        
        resp = client.create_tweet(text=text, in_reply_to_tweet_id=prev_id)
        if resp.data:
            prev_id = resp.data.id

    # Engagement booster
    client.create_tweet(text="Which story surprises you most? Reply below! 👇", in_reply_to_tweet_id=prev_id)

if __name__ == "__main__":
    print("Fetching top news via Grok API...")
    stories = fetch_top_news_via_grok()
    print(f"Found {len(stories)} stories.")
    for s in stories:
        print(s)
    
    print("\nPosting thread to X...")
    post_engaging_thread(stories)
