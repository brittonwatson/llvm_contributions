# LLVM Contribution Tracking Scripts

This repository contains Python scripts designed to track user contributions to the LLVM project across different platforms.

## Scripts

1.  `contributions_llvm_github.py`
2.  `contributions_llvm_discourse.py`

---

## 1. GitHub Contribution Tracker (`contributions_llvm_github.py`)

This script tracks a user's contributions to the `llvm/llvm-project` repository on GitHub.

### Features
-   Calculates all-time and last-12-months contributions.
-   Breaks down contributions by:
    -   Pull Requests (authored, merged, open, closed)
    -   Pull Request Reviews
    -   Commits
    -   Issues Opened
    -   Threads Commented On

### Authentication
The script uses the GitHub API. To avoid rate limits, it's highly recommended to use a GitHub Personal Access Token.
-   **On first run**, the script will prompt you to enter a token.
-   The token is cached in a local `.github_token` file for future use.
-   Alternatively, you can set a `GITHUB_TOKEN` environment variable, which the script will use automatically.

### Usage
Run the script from your terminal:
```bash
python3 contributions_llvm_github.py
```
You will be prompted to enter a GitHub username.

---

## 2. Discourse Contribution Tracker (`contributions_llvm_discourse.py`)

This script tracks a user's contributions on the official LLVM Discourse forum (`discourse.llvm.org`).

### Features
-   Calculates all-time contributions.
-   Breaks down contributions by:
    -   Topics Created
    -   Replies Created
    -   Likes Given / Received
    -   Solutions Marked
-   Includes a "Yearly Post Activity" summary for users older than one year.

### Authentication
The script uses the Discourse API. Authentication is recommended to avoid being rate-limited.
-   **On first run**, the script will prompt you for an **API Username** and **API Key**. You can generate these from your user admin panel on the Discourse site (`/admin/api/keys`).
-   Your credentials are cached in a local `.discourse_api_credentials` file (format: `username:key`).
-   Alternatively, you can set `DISCOURSE_API_USERNAME` and `DISCOURSE_API_KEY` environment variables.

### Usage
Run the script from your terminal:
```bash
python3 contributions_llvm_discourse.py
```
You will be prompted to enter a Discourse username.

---

## General Usage

### Prerequisites
Both scripts require Python 3 and the `requests` library.

Install the `requests` library using pip:
```bash
pip install requests
```

### Interactive Commands
While a script is running, you can enter the following commands instead of a username:
-   `stop`: Exits the program.
-   `ratelimit`: Checks the current API rate limit status.
-   `resettoken`: Deletes the cached token/API key and prompts for a new one.