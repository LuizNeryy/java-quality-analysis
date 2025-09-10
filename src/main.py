from src.collectors.rest_collector import RestDataCollector
from src.collectors.graphql_collector import GraphQLDataCollector
from src.modules.data_analyzer import DataAnalyzer
from src.modules.data_visualizer import DataVisualizer
from src.modules.report_generator import ReportGenerator
from src import config

def main():
    print("=====================================================")
    print("=== ANALISADOR DE REPOSITÓRIOS POPULARES DO GITHUB ===")
    print(f"=== Método de Coleta: {config.API_METHOD} ===")
    print(f"=== Repositórios: {config.TOTAL_REPOS_TO_FETCH} ===")
    print("=====================================================\n")

    collector = RestDataCollector()

    print("--- Etapa 1: Coletando dados da API do GitHub ---")
    if collector:
        collector.run()
    print("-----------------------------------------------------\n")

if __name__ == "__main__":
    main()