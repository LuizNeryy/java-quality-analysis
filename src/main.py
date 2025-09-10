from collectors.rest_collector import RestDataCollector

def main():
    print("=== ANALISADOR DE REPOSITÓRIOS POPULARES DO GITHUB ===\n")

    ck_jar_path = r"C:\Users\Nery\Desktop\ck\target\ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar"
    collector = RestDataCollector(ck_jar_path=ck_jar_path)

    collector.run()

if __name__ == "__main__":
    main()
