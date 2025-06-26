import requests
import os
from datetime import datetime, timedelta
import time

# --- Configuration ---
# Your GitHub Personal Access Token. It's highly recommended to use one to avoid rate limits.
# You can create a token here: https://github.com/settings/tokens
# The script will prompt for the token. It can also use a GITHUB_TOKEN environment variable if set.
REPO = "llvm/llvm-project"
API_URL = "https://api.github.com"
TOKEN_FILE = ".github_token"

# --- Helper Functions ---

def get_github_token():
    """
    Gets the GitHub token from environment variables, a local cache file, or prompts the user.
    The token is cached locally for subsequent runs.
    """
    # 1. Check for environment variable (highest priority)
    token_env = os.environ.get("GITHUB_TOKEN")
    if token_env:
        print("Found GITHUB_TOKEN environment variable. Using it for authentication.")
        return token_env

    # 2. Check for cached token file
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token = f.read().strip()
            if token:
                print(f"Using cached GitHub token from '{TOKEN_FILE}'.")
                return token
        except IOError as e:
            print(f"Warning: Could not read token file '{TOKEN_FILE}': {e}")

    # 3. If no token, prompt user and cache it
    print("\nPlease provide a GitHub Personal Access Token.")
    print("This is recommended to avoid API rate limits and access private data if needed.")
    print(f"Your token will be saved to '{TOKEN_FILE}' for future use.")
    
    try:
        # Prompt for the token with visible input
        token = input("Enter token (or press Enter to proceed without one): ").strip()
        if token:
            try:
                with open(TOKEN_FILE, 'w') as f:
                    f.write(token)
                print(f"Token saved to '{TOKEN_FILE}'.")
            except IOError as e:
                print(f"Warning: Could not save token to file '{TOKEN_FILE}': {e}")
        return token
    except EOFError:
        print("\nCould not read from input. Proceeding without a token.")
        return None


def handle_rate_limit_error(response):
    """
    Parses rate limit headers from a GitHub API response and prints a helpful message.
    """
    headers = response.headers
    resource = headers.get('X-RateLimit-Resource', 'N/A')
    reset_timestamp = headers.get('X-RateLimit-Reset')

    print("\n--- GitHub API Rate Limit Exceeded ---")
    
    if reset_timestamp:
        try:
            reset_time = datetime.fromtimestamp(int(reset_timestamp)).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"The rate limit for the '{resource.replace('_', ' ').title()}' API has been reached.")
            print(f"Your limit will reset at: {reset_time}")
        except (ValueError, TypeError):
            print("Could not parse the rate limit reset time from the API response.")
    else:
        print("A rate limit was exceeded, but the reset time could not be determined.")
    
    print("Please wait until the reset time or use a different GitHub Personal Access Token.")
    print("You can reset your token in this program by entering 'resettoken'.")
    print("--------------------------------------\n")


def count_search_results(query, headers):
    """
    Performs a search query and returns the total count of results.
    This is more efficient than fetching all items if we only need the count.
    """
    search_url = f"{API_URL}/search/issues"
    params = {'q': query}
    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get('total_count', 0)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            handle_rate_limit_error(e.response)
        else:
            print(f"Error making search request for query '{query}': {e}")
            if e.response.status_code == 401:
                print("This indicates an invalid GitHub token. Please check your token or run without one.")
        return 0
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
        return 0


def count_commit_results(query, headers):
    """
    Performs a search query for commits and returns the total count of results.
    """
    search_url = f"{API_URL}/search/commits"
    params = {'q': query}
    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get('total_count', 0)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            handle_rate_limit_error(e.response)
        else:
            print(f"Error making commit search request for query '{query}': {e}")
            if e.response.status_code == 401:
                print("This indicates an invalid GitHub token. Please check your token or run without one.")
        return 0
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred during commit search: {e}")
        return 0


def check_rate_limit(headers):
    """
    Checks the GitHub API rate limit status and prints only the limits that have been used.
    """
    print("\nChecking GitHub API Rate Limit Status for Used Endpoints...")
    url = f"{API_URL}/rate_limit"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        rate_limit_data = response.json()

        resources = rate_limit_data.get('resources', {})
        
        active_limits = []
        for resource, limits in resources.items():
            limit = limits.get('limit')
            remaining = limits.get('remaining')
            if limit is not None and remaining is not None and remaining < limit:
                reset_time = datetime.fromtimestamp(limits.get('reset')).strftime('%Y-%m-%d %H:%M:%S UTC')
                active_limits.append({
                    'name': resource.replace('_', ' ').title(),
                    'remaining': remaining,
                    'limit': limit,
                    'reset': reset_time
                })

        if active_limits:
            print("\n" + "="*40)
            print("Active API Rate Limits (Used)")
            print("="*40)
            for limits in active_limits:
                print(f"{limits['name']:<25}: {limits['remaining']}/{limits['limit']} remaining")
                print(f"{'Resets at':<25}: {limits['reset']}")
                print("-" * 40)
        else:
            print("No API rate limits have been consumed yet.")

    except requests.exceptions.HTTPError as e:
        print(f"Error checking rate limit: {e}")
    except requests.exceptions.RequestException as e:
        print(f"A network error occurred while checking rate limit: {e}")


# --- Main Logic ---

def main():
    """
    Main function to run the contribution counter in a loop.
    """
    print("--- LLVM GitHub Contribution Counter ---")

    # Get the token and set up headers once at the start.
    token = get_github_token()
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        print("\nUsing provided GitHub token for authentication.")
    else:
        print("\nProceeding without a GitHub token. You may encounter rate limits.")

    while True:
        try:
            username_input = input("\nEnter a username (or 'ratelimit', 'resettoken', 'stop'): ")
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
                        print(f"Cached token '{TOKEN_FILE}' has been removed.")
                except OSError as e:
                    print(f"Error removing token file: {e}")
                
                # Get a new token and update headers
                token = get_github_token()
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    print("\nAuthentication headers have been updated with the new token.")
                else:
                    if "Authorization" in headers:
                        del headers["Authorization"]
                    print("\nProceeding without a GitHub token.")
                continue

        except EOFError:
            print("\nCould not read username. Exiting.")
            break

        # If it's not a command, proceed to fetch contributions.
        print(f"\nFetching contributions for '{username}' in '{REPO}'. This may take a moment...")

        # Define queries for the GitHub search API
        base_query = f"repo:{REPO} author:{username}"
        merged_pr_query = f"{base_query} is:pr is:merged"
        open_pr_query = f"{base_query} is:pr is:open"
        closed_pr_query = f"{base_query} is:pr is:closed is:unmerged"
        issues_query = f"{base_query} is:issue"
        
        # This query counts PRs the user has reviewed.
        reviews_query = f"repo:{REPO} reviewed-by:{username} is:pr"

        # Query for commits.
        commits_query = f"repo:{REPO} author:{username}"

        # Comments are split to count threads commented on, which is a GitHub API limitation.
        issue_comments_query = f"repo:{REPO} is:issue commenter:{username}"
        pr_comments_query = f"repo:{REPO} is:pr commenter:{username}"


        # Get counts using the search API for efficiency
        merged_prs = count_search_results(merged_pr_query, headers)
        open_prs = count_search_results(open_pr_query, headers)
        closed_prs = count_search_results(closed_pr_query, headers)
        issues_opened = count_search_results(issues_query, headers)
        reviews = count_search_results(reviews_query, headers)
        commits = count_commit_results(commits_query, headers)
        
        # Get comment counts and add them together
        issue_comments = count_search_results(issue_comments_query, headers)
        pr_comments = count_search_results(pr_comments_query, headers)
        threads_commented_on = issue_comments + pr_comments
        
        # --- Display Results ---
        print("\n" + "="*40)
        print(f"Contribution Summary for: {username}")
        print("="*40)
        total_authored = merged_prs + open_prs + closed_prs
        print(f"{'Pull Requests (Authored)':<30}: {total_authored}")
        print(f"{'  - Merged':<28}: {merged_prs}")
        print(f"{'  - Open':<28}: {open_prs}")
        print(f"{'  - Closed/Unmerged':<28}: {closed_prs}")
        print("-" * 40)
        print(f"{'Pull Request Reviews':<30}: {reviews}")
        print("-" * 40)
        print(f"{'Commits':<30}: {commits}")
        print("-" * 40)
        print(f"{'Issues Opened':<30}: {issues_opened}")
        print("-" * 40)
        print(f"{'Threads Commented On':<30}: {threads_commented_on}")
        print("="*40)
        grand_total = total_authored + reviews + issues_opened + threads_commented_on + commits
        print(f"{'TOTAL CONTRIBUTIONS':<30}: {grand_total}")
        print("="*40)

        # --- Contributions in the last 12 months ---
        print("\nCalculating contributions in the last 12 months...")
        
        today = datetime.now()
        one_year_ago = today.replace(year=today.year - 1)
        one_year_ago_str = one_year_ago.strftime('%Y-%m-%d')

        # Date-filtered queries for the last 12 months
        merged_prs_yearly_query = f"{base_query} is:pr is:merged merged:>{one_year_ago_str}"
        open_pr_yearly_query = f"{base_query} is:pr is:open created:>{one_year_ago_str}"
        closed_pr_yearly_query = f"{base_query} is:pr is:closed is:unmerged closed:>{one_year_ago_str}"
        issues_yearly_query = f"{base_query} is:issue created:>{one_year_ago_str}"
        reviews_yearly_query = f"repo:{REPO} reviewed-by:{username} is:pr updated:>{one_year_ago_str}"
        commits_yearly_query = f"repo:{REPO} author:{username} author-date:>{one_year_ago_str}"
        # For comments, we use 'updated' as a proxy for recent activity, as the API can't filter comments by creation date.
        issue_comments_yearly_query = f"repo:{REPO} is:issue commenter:{username} updated:>{one_year_ago_str}"
        pr_comments_yearly_query = f"repo:{REPO} is:pr commenter:{username} updated:>{one_year_ago_str}"

        # Get yearly counts
        merged_prs_yearly = count_search_results(merged_prs_yearly_query, headers)
        open_prs_yearly = count_search_results(open_pr_yearly_query, headers)
        closed_prs_yearly = count_search_results(closed_pr_yearly_query, headers)
        issues_opened_yearly = count_search_results(issues_yearly_query, headers)
        reviews_yearly = count_search_results(reviews_yearly_query, headers)
        commits_yearly = count_commit_results(commits_yearly_query, headers)
        issue_comments_yearly = count_search_results(issue_comments_yearly_query, headers)
        pr_comments_yearly = count_search_results(pr_comments_yearly_query, headers)
        threads_commented_on_yearly = issue_comments_yearly + pr_comments_yearly
        
        total_authored_yearly = merged_prs_yearly + open_prs_yearly + closed_prs_yearly
        grand_total_yearly = total_authored_yearly + reviews_yearly + issues_opened_yearly + threads_commented_on_yearly + commits_yearly

        print("\n" + "="*40)
        print("Contribution Summary (Last 12 Months)")
        print("="*40)
        print(f"{'Pull Requests (Authored)':<30}: {total_authored_yearly}")
        print(f"{'  - Merged':<28}: {merged_prs_yearly}")
        print(f"{'  - Open':<28}: {open_prs_yearly}")
        print(f"{'  - Closed/Unmerged':<28}: {closed_prs_yearly}")
        print("-" * 40)
        print(f"{'Pull Request Reviews':<30}: {reviews_yearly}")
        print("-" * 40)
        print(f"{'Commits':<30}: {commits_yearly}")
        print("-" * 40)
        print(f"{'Issues Opened':<30}: {issues_opened_yearly}")
        print("-" * 40)
        print(f"{'Threads Commented On*':<30}: {threads_commented_on_yearly}")
        print("="*40)
        print(f"{'TOTAL YEARLY CONTRIBUTIONS':<30}: {grand_total_yearly}")
        print("="*40)

        print("\nNote: 'Total Contributions' is a sum of commits, PRs (authored/reviewed), issues opened, and threads commented on.")
        print("*Due to API limitations, the script counts threads (issues/PRs) with comments, not individual comments.")


if __name__ == "__main__":
    main() 