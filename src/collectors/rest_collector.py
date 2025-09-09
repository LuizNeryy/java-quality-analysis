import os
import requests
import pandas as pd
import time
from .. import config

class RestDataCollector:
    def __init__(self):
        self.base_api_url = 'https://api.github.com'
        self.headers = config.HEADERS
        self.total_repos_to_fetch = config.TOTAL_REPOS_TO_FETCH
        self.repos_per_page = config.REPOS_PER_PAGE
        self.csv_filepath = config.CSV_FILEPATH
        
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
                # Se o erro for de "rate limit", esperamos e tentamos novamente
                if e.response.status_code == 403 and 'rate limit' in e.response.text.lower():
                    print("!!! Atingiu o limite de requisições da API. Aguardando 60 segundos...")
                    time.sleep(60)
                    continue # Tenta novamente
                # Outros erros 5xx
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
                'q': 'stars:>1', 'sort': 'stars', 'order': 'desc',
                'per_page': self.repos_per_page, 'page': page
            }
            response = self._make_api_request(search_url, params=params)
            
            if response:
                repo_list.extend(response.json().get('items', []))
                print(f"Página de lista {page}/{total_pages} (REST) coletada com sucesso.")
                time.sleep(1) # Delay para não sobrecarregar a API
            else:
                return None # Falha ao buscar a lista
        return repo_list

    def _fetch_detailed_data(self, repo_list):
        """
        Busca dados detalhados para cada repositório da lista.
        """
        detailed_repos = []
        total_repos = len(repo_list)
        
        print(f"\nIniciando a coleta de dados detalhados para {total_repos} repositórios...")
        
        for i, repo in enumerate(repo_list):
            repo_name = repo['full_name']
            print(f"Coletando detalhes de '{repo_name}' ({i+1}/{total_repos})...")
            
            # 1. Obter dados de releases
            releases_url = f"{self.base_api_url}/repos/{repo_name}/releases"
            releases_response = self._make_api_request(releases_url, params={'per_page': 1})
            release_count = 0
            if releases_response and 'Link' in releases_response.headers:
                # A API retorna o número total de páginas no cabeçalho 'Link'
                try:
                    link_header = releases_response.headers['Link']
                    last_page_link = [s for s in link_header.split(',') if 'rel="last"' in s]
                    if last_page_link:
                        release_count = int(last_page_link[0].split('page=')[1].split('>')[0])
                except (IndexError, ValueError):
                    release_count = len(releases_response.json()) if releases_response else 0
            elif releases_response:
                release_count = len(releases_response.json())

            # 2. Obter dados de contribuidores
            contributors_url = f"{self.base_api_url}/repos/{repo_name}/contributors"
            contributors_response = self._make_api_request(contributors_url, params={'per_page': 1, 'anon': 'true'})
            contributor_count = 0
            if contributors_response and 'Link' in contributors_response.headers:
                try:
                    link_header = contributors_response.headers['Link']
                    last_page_link = [s for s in link_header.split(',') if 'rel="last"' in s]
                    if last_page_link:
                        contributor_count = int(last_page_link[0].split('page=')[1].split('>')[0])
                except (IndexError, ValueError):
                    contributor_count = len(contributors_response.json()) if contributors_response else 0
            elif contributors_response:
                contributor_count = len(contributors_response.json())

            # 3. Obter dados de pull requests aceitas
            pulls_url = f"{self.base_api_url}/repos/{repo_name}/pulls"
            pulls_response = self._make_api_request(pulls_url, params={'state': 'closed', 'per_page': 1})
            merged_pulls_count = 0
            if pulls_response and 'Link' in pulls_response.headers:
                try:
                    link_header = pulls_response.headers['Link']
                    last_page_link = [s for s in link_header.split(',') if 'rel="last"' in s]
                    if last_page_link:
                        merged_pulls_count = int(last_page_link[0].split('page=')[1].split('>')[0])
                except (IndexError, ValueError):
                    # Se não conseguir parsear, conta manualmente os PRs mergeados
                    all_pulls = self._make_api_request(pulls_url, params={'state': 'closed', 'per_page': 100})
                    if all_pulls:
                        merged_pulls_count = len([pr for pr in all_pulls.json() if pr.get('merged_at')])
            elif pulls_response:
                merged_pulls_count = len([pr for pr in pulls_response.json() if pr.get('merged_at')])

            # 4. Obter dados de issues fechadas
            issues_url = f"{self.base_api_url}/repos/{repo_name}/issues"
            closed_issues_response = self._make_api_request(issues_url, params={'state': 'closed', 'per_page': 1})
            closed_issues_count = 0
            if closed_issues_response and 'Link' in closed_issues_response.headers:
                try:
                    link_header = closed_issues_response.headers['Link']
                    last_page_link = [s for s in link_header.split(',') if 'rel="last"' in s]
                    if last_page_link:
                        closed_issues_count = int(last_page_link[0].split('page=')[1].split('>')[0])
                except (IndexError, ValueError):
                    closed_issues_count = len(closed_issues_response.json()) if closed_issues_response else 0
            elif closed_issues_response:
                closed_issues_count = len(closed_issues_response.json())

            # Adiciona os novos dados ao dicionário do repositório
            repo['release_count'] = release_count
            repo['contributor_count'] = contributor_count
            repo['merged_pulls_count'] = merged_pulls_count
            repo['closed_issues_count'] = closed_issues_count
            detailed_repos.append(repo)
            
            time.sleep(0.5) # Pequeno delay para ser gentil com a API
            
        return detailed_repos

    def _parse_data(self):
        """
        Processa os dados detalhados para o DataFrame.
        """
        parsed_list = []
        for repo in self.raw_data:
            # Calculando total de issues para RQ06
            open_issues = repo.get('open_issues_count', 0)
            closed_issues = repo.get('closed_issues_count', 0)
            total_issues = open_issues + closed_issues
            
            parsed_list.append({
                'name': repo.get('full_name'),
                'stars': repo.get('stargazers_count'),
                'forks': repo.get('forks_count'),
                'language': repo.get('language'),
                'license': repo.get('license', {}).get('spdx_id') if repo.get('license') else 'No License',
                'open_issues': open_issues,
                'closed_issues': closed_issues,
                'total_issues': total_issues,
                'created_at': repo.get('created_at'),
                'updated_at': repo.get('updated_at'),
                'description': repo.get('description'),
                'url': repo.get('html_url'),
                'releases': repo.get('release_count', 0),
                'contributors': repo.get('contributor_count', 0),
                'merged_pull_requests': repo.get('merged_pulls_count', 0)
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
        if repo_list:
            self.raw_data = self._fetch_detailed_data(repo_list)
            if self.raw_data:
                self._parse_data()
                self._save_to_csv()