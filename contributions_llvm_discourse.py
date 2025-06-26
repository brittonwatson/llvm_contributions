import requests
import os
from datetime import datetime, timedelta
import time
import json

# --- Configuration ---
# Discourse instance to query
DISCOURSE_URL = "https://discourse.llvm.org"
API_URL = f"{DISCOURSE_URL}" # Base URL for the Discourse API

# File to cache the API key.
# It's recommended to use an API key to avoid being rate-limited.
# You can generate a key from your user profile: /admin/api/keys
TOKEN_FILE = ".discourse_api_credentials"

# --- Helper Functions ---

def get_discourse_api_credentials():
    """
    Gets the Discourse API Key and Username from environment variables, a local cache file, or prompts the user.
    The credentials are cached locally for subsequent runs.
    Returns a tuple of (api_key, api_username).
    """
    # 1. Check for environment variables (highest priority)
    api_key_env = os.environ.get("DISCOURSE_API_KEY")
    api_username_env = os.environ.get("DISCOURSE_API_USERNAME")
    if api_key_env and api_username_env:
        print("Found DISCOURSE_API_KEY and DISCOURSE_API_USERNAME environment variables.")
        return api_key_env, api_username_env

    # 2. Check for cached credentials file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                content = f.read().strip()
                if ':' in content:
                    api_username, api_key = content.split(':', 1)
                    if api_key and api_username:
                        print(f"Using cached Discourse API credentials from '{TOKEN_FILE}'.")
                        return api_key, api_username
        except IOError as e:
            print(f"Warning: Could not read credentials file '{TOKEN_FILE}': {e}")
        except ValueError:
            print(f"Warning: Credentials file '{TOKEN_FILE}' has an invalid format. Expected 'api_username:api_key'.")

    # 3. If no credentials, prompt user and cache them
    print("\nPlease provide Discourse API credentials.")
    print("This is recommended to avoid being rate-limited.")
    print(f"You can generate these from your user admin panel at {DISCOURSE_URL}/admin/api/keys")
    print(f"Your credentials will be saved to '{TOKEN_FILE}' for future use (format: api_username:api_key).")
    
    try:
        api_username = input("Enter your Discourse API Username (e.g., your username or 'system'): ").strip()
        api_key = input("Enter your Discourse API Key: ").strip()
        
        if api_key and api_username:
            try:
                with open(TOKEN_FILE, 'w') as f:
                    f.write(f"{api_username}:{api_key}")
                print(f"Credentials saved to '{TOKEN_FILE}'.")
            except IOError as e:
                print(f"Warning: Could not save credentials to file '{TOKEN_FILE}': {e}")
            return api_key, api_username
    except EOFError:
        print("\nCould not read from input. Proceeding without authentication.")
    
    return None, None

def handle_discourse_rate_limit(response):
    """
    Handles rate limit errors from the Discourse API.
    """
    headers = response.headers
    retry_after = headers.get('Retry-After')
    
    print("\n--- Discourse API Rate Limit Exceeded ---")
    if retry_after:
        print(f"You have been rate-limited. Please try again after {retry_after} seconds.")
    else:
        print("You have been rate-limited, but the API did not provide a cool-down period.")
    print("-----------------------------------------\n")


def get_user_details(username, headers):
    """
    Fetches the main user profile data from Discourse to get creation date.
    """
    url = f"{API_URL}/users/{username}.json"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching user details for '{username}': {e}")
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred while fetching user details: {e}")
    return None

def get_user_summary(username, headers):
    """
    Fetches the user summary data, which includes contribution stats.
    This summary provides most of the counts we need.
    """
    url = f"{API_URL}/users/{username}/summary.json"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            print(f"User '{username}' not found on {DISCOURSE_URL}.")
            return None
            
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            handle_discourse_rate_limit(e.response)
        else:
            print(f"Error fetching user summary for '{username}': {e}")
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred while fetching user summary: {e}")
        
    return None

def get_user_posts(username, headers, from_date=None):
    """
    Fetches all posts created by a user, paginating through the results.
    Optionally filters posts from a given date using the search endpoint.
    """
    posts = []
    page = 0
    while True:
        # Use the 'after:' filter for date-based searches
        query = f"@{username} in:posts"
        if from_date:
            query += f" after:{from_date}"
        
        search_url = f"{API_URL}/search.json"
        params = {'q': query, 'page': page}

        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # The search can sometimes include posts mentioning the user, so we filter to be sure.
            user_posts = [p for p in data.get('posts', []) if p['username'].lower() == username.lower()]
            posts.extend(user_posts)

            # The search API doesn't have a simple 'more' flag.
            # We stop when the 'posts' array in the response is empty.
            if not data.get('posts'):
                break
            
            page += 1
            # Add a small delay to be kind to the API
            time.sleep(0.5)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                handle_discourse_rate_limit(e.response)
                # wait before retrying
                time.sleep(int(e.response.headers.get('Retry-After', 60)))
            else:
                print(f"Error fetching user posts for '{username}': {e}")
                break
        except requests.exceptions.RequestException as e:
            print(f"A network error occurred while fetching user posts: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from response: {e}")
            print(f"Response text: {response.text}")
            break

    return posts

def check_rate_limit(headers):
    """
    Checks the Discourse API rate limit status.
    Discourse doesn't have a dedicated rate_limit endpoint like GitHub.
    We rely on headers from responses (RateLimit-*, X-RateLimit-*).
    This function will be a placeholder or can be adapted if a specific Discourse plugin provides this.
    """
    print("\nDiscourse API rate limits are included in response headers.")
    print("This script will notify you if a rate limit is hit.")
    print("With an API key, you should generally have a high limit (e.g., 60 reqs/min by default).")

# --- Main Logic ---

def main():
    """
    Main function to run the Discourse contribution counter in a loop.
    """
    print("--- LLVM Discourse Contribution Counter ---")

    # Get the API credentials and set up headers.
    api_key, api_username = get_discourse_api_credentials()
    headers = {
        "Accept": "application/json"
    }
    if api_key and api_username:
        headers["Api-Key"] = api_key
        headers["Api-Username"] = api_username
        print(f"\nUsing API credentials for user '{api_username}'.")
    else:
        print("\nProceeding without authentication. You may be rate-limited.")

    while True:
        try:
            username_input = input("\nEnter a Discourse username (or 'ratelimit', 'resettoken', 'stop'): ")
            username = username_input.strip()

            if not username:
                print("Username cannot be empty. Please try again.")
                continue
            
            # Command handling
            if username.lower() == 'stop':
                print("Exiting program. Goodbye!")
                break
            if username.lower() == 'ratelimit':
                check_rate_limit(headers)
                continue
            if username.lower() == 'resettoken':
                try:
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)
                        print(f"Cached credentials '{TOKEN_FILE}' have been removed.")
                except OSError as e:
                    print(f"Error removing credentials file: {e}")
                
                # Get new credentials and update headers
                api_key, api_username = get_discourse_api_credentials()
                if api_key and api_username:
                    headers["Api-Key"] = api_key
                    headers["Api-Username"] = api_username
                    print("\nAPI headers updated.")
                else:
                    headers.pop("Api-Key", None)
                    headers.pop("Api-Username", None)
                    print("\nProceeding without authentication.")
                continue

        except EOFError:
            print("\nCould not read username. Exiting.")
            break

        # If it's not a command, proceed to fetch contributions.
        print(f"\nFetching contributions for '{username}' from {DISCOURSE_URL}. This may take a moment...")

        summary_data = get_user_summary(username, headers)
        user_details = get_user_details(username, headers)

        if not summary_data or not user_details:
            continue
            
        # Extract data from summary
        user_summary = summary_data.get('user_summary', {})
        topics_created = user_summary.get('topic_count', 0)
        replies_created = user_summary.get('post_count', 0)
        likes_given = user_summary.get('likes_given', 0)
        likes_received = user_summary.get('likes_received', 0)
        solutions = user_summary.get('solved_count', 0)
        
        # --- Display Results (All Time) ---
        print("\n" + "="*40)
        print(f"Contribution Summary for: {username}")
        print("="*40)
        print(f"{'Topics Created':<30}: {topics_created}")
        print(f"{'Replies Created':<30}: {replies_created}")
        print("-" * 40)
        print(f"{'Likes Given':<30}: {likes_given}")
        print(f"{'Likes Received':<30}: {likes_received}")
        print("-" * 40)
        print(f"{'Solutions Given':<30}: {solutions}")
        print("="*40)
        total_contributions = topics_created + replies_created + solutions
        print(f"{'TOTAL CONTRIBUTIONS':<30}: {total_contributions}")
        print("="*40)

        # --- Contributions in the last 12 months (if user is older than a year) ---
        created_at_str = user_details.get('user', {}).get('created_at')
        if created_at_str:
            user_created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            today = datetime.now()
            one_year_ago = today.replace(year=today.year - 1)

            if user_created_at < one_year_ago:
                print("\nCalculating post activity in the last 12 months...")
                one_year_ago_str = one_year_ago.strftime('%Y-%m-%d')
                
                print(f"Fetching posts since {one_year_ago_str}. This can be slow...")
                yearly_posts = get_user_posts(username, headers, from_date=one_year_ago_str)

                yearly_topics = 0
                yearly_replies = 0
                if yearly_posts:
                    for post in yearly_posts:
                        if post.get('post_number') == 1:
                            yearly_topics += 1
                        else:
                            yearly_replies += 1

                print("\n" + "="*40)
                print("Yearly Post Activity (Last 12 Months)")
                print("="*40)
                print(f"{'Topics Created':<30}: {yearly_topics}")
                print(f"{'Replies Created':<30}: {yearly_replies}")
                print("="*40)
                total_yearly = yearly_topics + yearly_replies
                print(f"{'TOTAL POSTS':<30}: {total_yearly}")
                print("="*40)

        print("\nNote: 'Total Contributions' is a sum of topics, replies, and solutions for all time.")
        print("Note: Yearly activity only includes topics and replies due to API limitations.")

if __name__ == "__main__":
    main()