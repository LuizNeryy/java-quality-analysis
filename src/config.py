import os
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

if not GITHUB_TOKEN:
    raise ValueError("Token do GitHub não encontrado.")

REST_API_URL = 'https://api.github.com/search/repositories'
GRAPHQL_API_URL = 'https://api.github.com/graphql'

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'Content-Type': 'application/json',
    'User-Agent': 'GitHub-Lab-Experiment/1.0'
}

REPOS_PER_PAGE = 10
TOTAL_REPOS_TO_FETCH = 50

OUTPUT_DIR = "output"
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
PLOTS_DIR = os.path.join(OUTPUT_DIR, "plots")
CSV_FILEPATH = os.path.join(DATA_DIR, f"top_{TOTAL_REPOS_TO_FETCH}_repos.csv")