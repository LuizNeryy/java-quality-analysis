import os
import requests
import pandas as pd
import subprocess
import shutil
import time
from datetime import datetime
from config import config 

class RestDataCollector:

    def __init__(self, ck_jar_path):
        self.base_api_url = 'https://api.github.com'
        self.headers = config.HEADERS
        self.total_repos_to_fetch = config.TOTAL_REPOS_TO_FETCH
        self.repos_per_page = config.REPOS_PER_PAGE
        self.csv_filepath = config.CSV_FILEPATH
        self.ck_jar_path = ck_jar_path
        
        self.raw_data = []
        self.dataframe = None

    def _make_api_request(self, url, params=None):
        """
        Função auxiliar para fazer requisições com retentativa.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:

                if e.response.status_code == 403 and 'rate limit' in e.response.text.lower():
                    print("!!! Atingiu o limite de requisições da API. Aguardando 60 segundos...")
                    time.sleep(60)
                    continue

                if 500 <= e.response.status_code < 600:
                    print(f"!!! Erro de servidor ({e.response.status_code}). Tentando novamente em 5s...")
                    time.sleep(5)
                    continue
                else:
                    print(f"Erro HTTP não recuperável: {e}")
                    return None
            except requests.exceptions.RequestException as e:
                print(f"Erro de requisição: {e}")
                time.sleep(5)
        
        print("!!! Todas as tentativas de conexão falharam.")
        return None

    def _fetch_repo_list(self):
        """
        Busca a lista inicial de repositórios populares.
        """
        search_url = f"{self.base_api_url}/search/repositories"
        repo_list = []
        total_pages = self.total_repos_to_fetch // self.repos_per_page
        
        print(f"Buscando a lista de {self.total_repos_to_fetch} repositórios via REST...")
        
        for page in range(1, total_pages + 1):
            params = {
                'q': 'language:java stars:>1', 'sort': 'stars', 'order': 'desc',
                'per_page': self.repos_per_page, 'page': page
            }
            response = self._make_api_request(search_url, params=params)
            
            if response:
                repo_list.extend(response.json().get('items', []))
                print(f"Página de lista {page}/{total_pages} (REST) coletada com sucesso.")
                time.sleep(1)
            else:
                print(f"❌ Falha ao buscar a página {page} da API.")
                return None
        return repo_list

    def _fetch_detailed_data(self, repo_list):
        """
        Busca dados detalhados para cada repositório da lista,
        coletando métricas de processo e de qualidade:
        """
        detailed_repos = []
        total_repos = len(repo_list)
        print(f"\nIniciando a coleta de dados detalhados para {total_repos} repositórios...")

        # Pasta temporária central
        base_temp_dir = "temp_repos"
        os.makedirs(base_temp_dir, exist_ok=True)

        for i, repo in enumerate(repo_list):
            repo_name = repo['full_name']
            print(f"Coletando detalhes de '{repo_name}' ({i+1}/{total_repos})...")

            repo_dir = os.path.join(base_temp_dir, repo_name.replace("/", "_"))
            ck_output_dir = os.path.join(base_temp_dir, f"{repo_name.replace('/', '_')}_metrics")

            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(ck_output_dir, ignore_errors=True)
            os.makedirs(ck_output_dir, exist_ok=True)

            # Clonar repositório
            try:
                subprocess.run(["git", "clone", "--depth", "1", repo['clone_url'], repo_dir], check=True)
            except subprocess.CalledProcessError:
                print(f"⚠️ Falha ao clonar {repo_name}, pulando este repositório.")
                continue

            # Métricas de Processo
            popularity = repo.get('stargazers_count', 0)

            release_count = 0
            try:
                releases_url = f"{self.base_api_url}/repos/{repo_name}/releases"
                releases_response = self._make_api_request(releases_url, params={'per_page': 1})
                if releases_response and 'Link' in releases_response.headers:
                    link_header = releases_response.headers['Link']
                    last_page_link = [s for s in link_header.split(',') if 'rel="last"' in s]
                    if last_page_link:
                        release_count = int(last_page_link[0].split('page=')[1].split('>')[0])
                elif releases_response:
                    release_count = len(releases_response.json())
            except Exception:
                release_count = 0

            created_at = repo.get('created_at')
            maturity_years = 0
            if created_at:
                created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                maturity_years = round((datetime.utcnow() - created_date).days / 365, 2)

            # Métricas de Qualidade (CK)
            loc, loc_comments, cbo, dit, lcom = 0, 0, 0, 0, 0
            try:
                subprocess.run([
                    "java", "-jar",
                    self.ck_jar_path,
                    repo_dir,
                    ck_output_dir
                ], check=True)

                class_metrics_path = os.path.join(ck_output_dir, "class.csv")
                if os.path.exists(class_metrics_path):
                    df = pd.read_csv(class_metrics_path)
                    loc = df["loc"].sum()
                    loc_comments = df["locComment"].sum()
                    cbo = df["cbo"].mean()
                    dit = df["dit"].mean()
                    lcom = df["lcom"].mean()
            except subprocess.CalledProcessError:
                print(f"⚠️ CK falhou no repo {repo_name}, métricas de qualidade zeradas.")

            # Salvar no dicionário
            repo['popularity'] = int(popularity)
            repo['release_count'] = int(release_count)
            repo['maturity_years'] = maturity_years
            repo['loc'] = int(loc)
            repo['loc_comments'] = int(loc_comments)
            repo['cbo'] = round(cbo, 2)
            repo['dit'] = round(dit, 2)
            repo['lcom'] = round(lcom, 2)

            detailed_repos.append(repo)

            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(ck_output_dir, ignore_errors=True)

            time.sleep(1)

        shutil.rmtree(base_temp_dir, ignore_errors=True)
        return detailed_repos

    def _parse_data(self):
        """
        Processa os dados detalhados para o DataFrame.
        """
        parsed_list = []
        for repo in self.raw_data:
            parsed_list.append({
                'name': repo.get('full_name'),
                'stars': repo.get('stargazers_count'),
                'popularity': repo.get('popularity'),
                'loc': repo.get('loc'),
                'loc_comments': repo.get('loc_comments'),
                'releases': repo.get('release_count', 0),
                'maturity_years': repo.get('maturity_years'),
                'cbo': repo.get('cbo'),
                'dit': repo.get('dit'),
                'lcom': repo.get('lcom'),
                'contributors': repo.get('contributor_count', 0),
                'merged_pull_requests': repo.get('merged_pulls_count', 0),
                'language': repo.get('language'),
                'license': repo.get('license', {}).get('spdx_id') if repo.get('license') else 'No License',
                'url': repo.get('html_url'),
                'description': repo.get('description'),
                'created_at': repo.get('created_at'),
                'updated_at': repo.get('updated_at')
            })
        self.dataframe = pd.DataFrame(parsed_list)

    def _save_to_csv(self):
        """Salva o DataFrame em um arquivo CSV."""
        os.makedirs(os.path.dirname(self.csv_filepath), exist_ok=True)
        self.dataframe.to_csv(self.csv_filepath, index=False)
        print(f"\nDados salvos com sucesso em: {self.csv_filepath}")

    def run(self):
        """
        Método principal que executa todo o fluxo de coleta e salvamento.
        """
        repo_list = self._fetch_repo_list()
        if not repo_list:
            print("❌ Falha ao buscar a lista de repositórios.")
            return

        self.raw_data = self._fetch_detailed_data(repo_list)
        if not self.raw_data:
            print("❌ Falha ao coletar dados detalhados.")
            return

        self._parse_data()
        self._save_to_csv()
