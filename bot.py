import os
import requests
import tweepy
from dotenv import load_dotenv
from datetime import datetime
from google import genai # Import the official Gemini SDK
from google.genai import types

load_dotenv()

# --- Configuration for X/Twitter ---
# Initialize the Twitter client (added try/except for safer execution)
try:
    client = tweepy.Client(
        consumer_key=os.getenv("X_CONSUMER_KEY"),
        consumer_secret=os.getenv("X_CONSUMER_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET")
    )
except Exception as e:
    print(f"Warning: Twitter client setup failed. Tweets will not be posted. Error: {e}")
    client = None

# --- Configuration for Gemini API ---
# Get the key from the environment variable GEMINI_API_KEY
# You can get a key at Google AI Studio or Google Cloud Console.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")

# Initialize the Gemini Client
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    gemini_client = None

# --- Prompt for the AI ---
PROMPT = """
Give me the top 5 most important worldwide news stories right now in this exact format (no extra text, strictly follow the format):

1. [Short engaging headline]
[One-sentence summary]
Source: [Main source]
Link: [Direct URL]

2. [Short engaging headline]
[One-sentence summary]
Source: [Main source]
Link: [Direct URL]

3. ... (Continue up to 5)

Rank by global impact and recency.
"""

def fetch_news_gemini():
    if gemini_client is None:
        return []
        
    print("Fetching real-time news using Gemini and Google Search tool...")
    
    try:
        # Use the generate_content method and enable the google_search tool
        # Gemini 2.5 Flash is fast and capable of using the search tool.
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=PROMPT,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}] # This enables the real-time search
            )
        )
    except Exception as e:
        print(f"Gemini API request failed: {e}")
        return []

    content = response.text
    print(f"Successfully received response from Gemini. Content length: {len(content)}")
    
    # --- Robust Parsing (Adapted for consistent output) ---
    stories = []
    # Split content into blocks, using an aggressive delimiter that handles extra newlines
    blocks = [b.strip() for b in content.split('\n\n') if b.strip()]
    
    for block in blocks:
        # Check if the block starts with a number followed by a dot (e.g., "1.")
        if block.startswith(('1.', '2.', '3.', '4.', '5.')):
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            
            # Simple check for minimum expected lines
            if len(lines) < 4:
                continue

            try:
                # 1. Headline (from the first line, after the number and dot)
                headline = lines[0].split('.', 1)[1].strip()
                
                # 2. Summary (usually the second line)
                summary = lines[1]
                
                # 3. Source (find the line starting with "Source:")
                source = next((line.replace("Source:", "").strip() for line in lines if line.startswith("Source:")), "N/A")
                
                # 4. Link (find the line starting with "Link:")
                link = next((line.replace("Link:", "").strip() for line in lines if line.startswith("Link:")), "N/A")
                
                stories.append({"headline": headline, "summary": summary, "source": source, "link": link})
            except (IndexError, AttributeError):
                print(f"Warning: Skipping malformed story block: {block[:50]}...")
                continue
                
    return stories

def post_thread(stories):
    if not stories:
        print("No stories to post.")
        return
    
    if client is None:
        print("Twitter client not initialized. Skipping posting.")
        return
        
    print(f"Posting {len(stories)} stories to X/Twitter...")

    # --- Post Tweet 1 (The main tweet/thread starter) ---
    intro = f"🌍 Top World News This Hour – {datetime.utcnow().strftime('%b %d, %H:%M UTC')}\n\n"
    story_1 = stories[0]
    
    # Construct the text for the first tweet
    text = (
        intro + 
        f"🔥 1. {story_1['headline']}\n\n"
        f"{story_1['summary']}\n\n"
        f"🔗 {story_1['link']}\n"
        f"Source: {story_1['source']}\n"
        f"\n#WorldNews #Breaking"
    )
    
    # Truncate text to Twitter's limit
    if len(text) > 280:
        text = text[:277] + "..."

    try:
        resp = client.create_tweet(text=text)
        prev_id = resp.data.id
        print(f"Posted Tweet 1: {text[:30]}...")
    except tweepy.TweepyException as e:
        print(f"Error posting Tweet 1: {e}")
        return


    # --- Post Subsequent Replies ---
    for i, s in enumerate(stories[1:], 2):
        reply_text = (
            f"👇 {i}. {s['headline']}\n\n"
            f"{s['summary']}\n\n"
            f"🔗 {s['link']}\n"
            f"Source: {s['source']}\n"
            f"\n#NewsUpdate"
        )
        
        if len(reply_text) > 280:
             reply_text = reply_text[:277] + "..."
             
        try:
            resp = client.create_tweet(text=reply_text, in_reply_to_tweet_id=prev_id)
            prev_id = resp.data.id
            print(f"Posted Tweet {i}: {reply_text[:30]}...")
        except tweepy.TweepyException as e:
            print(f"Error posting Tweet {i}: {e}")
            break # Stop the thread if a tweet fails

    # --- Post Final Reply ---
    try:
        client.create_tweet(text="Which story do you find most impactful? 👇", in_reply_to_tweet_id=prev_id)
        print("Posted final engagement tweet.")
    except tweepy.TweepyException as e:
        print(f"Error posting final tweet: {e}")


if __name__ == "__main__":
    stories = fetch_news_gemini()
    print("-" * 50)
    print(f"Successfully Parsed {len(stories)} Stories:")
    for s in stories:
        print(f"  - {s['headline']} (Source: {s['source']})")
    print("-" * 50)
    
    post_thread(stories)
