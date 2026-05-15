"""
=============================================================================
run_tests.py — Execução Automática de Todos os Cenários de Carga
=============================================================================

Executa 12 testes no total:
  4 cenários × 3 níveis de carga = 12 runs

Uso:
  python run_tests.py                  # roda tudo
  python run_tests.py --scenario py_cache          # só um cenário
  python run_tests.py --scenario py_cache --load media  # só um teste

Pré-requisitos:
  pip install locust requests
  docker-compose up -d
=============================================================================
"""

import argparse
import csv
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ---------------------------------------------------------------------------

LOCUSTFILE = Path("./locustfile.py")
RESULTS_DIR = Path("./resultados")
RUN_TIME = "2m"
SPAWN_RATE = 5
COOLDOWN_SECONDS = 15
REDIS_CONTAINER = "linkextractor_redis"

# ---------------------------------------------------------------------------
# DEFINIÇÃO DOS CENÁRIOS E CARGAS
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    name:       str
    host:       str
    redis_db:   int | None   # None = sem cache; int = banco a limpar antes do teste


@dataclass
class LoadLevel:
    name:  str
    users: int


SCENARIOS: list[Scenario] = [
    Scenario("py_nocache", "http://localhost:5001", redis_db=None),
    Scenario("py_cache",   "http://localhost:5002", redis_db=1),
    Scenario("rb_nocache", "http://localhost:5003", redis_db=None),
    Scenario("rb_cache",   "http://localhost:5004", redis_db=2),
]

LOAD_LEVELS: list[LoadLevel] = [
    LoadLevel("baixa", users=100),
    LoadLevel("media", users=200),
    LoadLevel("alta",  users=350),
]

# ---------------------------------------------------------------------------
# COLUNAS DO CSV GERADO PELO LOCUST (resultado_stats.csv)
# Referência: https://docs.locust.io/en/stable/retrieving-stats.html
# ---------------------------------------------------------------------------

CSV_COLUMNS = {
    "requests":  2,
    "failures":  3,
    "median":    4,
    "p90":       5,
    "p95":       6,
    "p99":       7,
    "avg":       8,
    "min":       9,
    "max":       10,
    "rps":       11,
}

# ---------------------------------------------------------------------------
# SAÍDA COLORIDA
# ---------------------------------------------------------------------------


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"


def log(level: str, msg: str) -> None:
    colors = {
        "INFO":  C.CYAN,
        "OK":    C.GREEN,
        "WARN":  C.YELLOW,
        "ERROR": C.RED,
        "RUN":   C.YELLOW,
        "HEAD":  C.BLUE + C.BOLD,
    }
    color = colors.get(level, C.RESET)
    tag = f"[{level:^5}]"
    print(f"{color}{tag}{C.RESET}  {msg}")


def section(title: str) -> None:
    bar = "═" * 52
    print(f"\n{C.BOLD}{C.BLUE}{bar}{C.RESET}")
    print(f"{C.BOLD}{C.BLUE}  {title}{C.RESET}")
    print(f"{C.BOLD}{C.BLUE}{bar}{C.RESET}")

# ---------------------------------------------------------------------------
# VERIFICAÇÃO DE PRÉ-REQUISITOS
# ---------------------------------------------------------------------------


def check_locust() -> None:
    """Garante que o Locust está instalado e acessível."""
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "locust", "--version"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log("ERROR", "Locust não encontrado. Execute: pip install locust")
        sys.exit(1)
    log("OK", f"Locust encontrado: {result.stdout.strip()}")


def check_locustfile() -> None:
    """Garante que o locustfile.py existe."""
    if not LOCUSTFILE.exists():
        log("ERROR", f"locustfile.py não encontrado em: {LOCUSTFILE}")
        sys.exit(1)
    log("OK", f"locustfile.py encontrado: {LOCUSTFILE}")


def check_service(scenario: Scenario) -> bool:
    """Verifica se a API do cenário está respondendo."""
    test_url = f"{scenario.host}/api/http://example.com/"
    try:
        resp = requests.get(test_url, timeout=5)
        if resp.status_code in (200, 400, 422):  # qualquer resposta = serviço vivo
            log("OK", f"{scenario.name:12} → respondendo em {scenario.host}")
            return True
        log("WARN",
            f"{scenario.name:12} → status {resp.status_code} em {scenario.host}")
        return False
    except requests.exceptions.ConnectionError:
        log("ERROR", f"{scenario.name:12} → sem resposta em {scenario.host}")
        return False


def preflight(scenarios: list[Scenario]) -> None:
    """Executa todas as verificações antes de iniciar os testes."""
    section("Verificações Iniciais")
    check_locust()
    check_locustfile()

    failed = [s for s in scenarios if not check_service(s)]
    if failed:
        names = ", ".join(s.name for s in failed)
        log("ERROR", f"Serviços não respondendo: {names}")
        log("ERROR", "Execute: docker-compose up -d  e aguarde ~10s")
        sys.exit(1)

    log("OK", "Todos os serviços prontos.")

# ---------------------------------------------------------------------------
# GERENCIAMENTO DO REDIS
# ---------------------------------------------------------------------------


def flush_redis(db: int) -> None:
    """Limpa um banco Redis via docker exec."""
    result = subprocess.run(
        ["docker", "exec", REDIS_CONTAINER,
            "redis-cli", "-n", str(db), "FLUSHDB"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        log("OK",
            f"Redis db={db} limpo (cache zerado para estado inicial limpo)")
    else:
        log("WARN",
            f"Não foi possível limpar Redis db={db}: {result.stderr.strip()}")

# ---------------------------------------------------------------------------
# EXECUÇÃO DO LOCUST
# ---------------------------------------------------------------------------


def run_locust(scenario: Scenario, load: LoadLevel) -> Path:
    """
    Executa um único teste Locust em modo headless.
    Retorna o caminho para o diretório de saída.
    """
    import sys
    out_dir = RESULTS_DIR / scenario.name / load.name
    csv_prefix = str(out_dir / "resultado")
    log_file = out_dir / "locust.log"

    out_dir.mkdir(parents=True, exist_ok=True)

    # Limpa cache
    if scenario.redis_db is not None:
        flush_redis(scenario.redis_db)

    cmd = [
        sys.executable, "-m",
        "locust",
        "-f",            str(LOCUSTFILE),
        "--host",        scenario.host,
        "--headless",
        "--users",       str(load.users),
        "--spawn-rate",  str(SPAWN_RATE),
        "--run-time",    RUN_TIME,
        "--csv",         csv_prefix,
        "--csv-full-history",
        "--only-summary",
    ]

    log("RUN", f"{scenario.name} | carga={load.name} | usuários={load.users}")

    with open(log_file, "w") as lf:
        result = subprocess.run(cmd, stdout=lf, stderr=lf, text=True)

    if result.returncode == 0:
        log("OK", f"Concluído → {out_dir}/")
    else:
        log("WARN",
            f"Locust retornou código {result.returncode} — veja {log_file}")

    return out_dir

# ---------------------------------------------------------------------------
# PARSING DOS RESULTADOS
# ---------------------------------------------------------------------------


def parse_stats(out_dir: Path) -> dict | None:
    """
    Lê o arquivo resultado_stats.csv gerado pelo Locust e retorna
    as métricas da linha 'Aggregated' (totais do teste).
    """
    stats_file = out_dir / "resultado_stats.csv"
    if not stats_file.exists():
        log("WARN", f"Stats não encontrado: {stats_file}")
        return None

    with open(stats_file, newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, None)  # descarta cabeçalho

        for row in reader:
            if row and row[1].strip().lower() == "aggregated":
                try:
                    return {
                        col: row[idx].strip()
                        for col, idx in CSV_COLUMNS.items()
                    }
                except IndexError:
                    log("WARN",
                        f"Linha Aggregated com colunas insuficientes em {stats_file}")
                    return None

    log("WARN", f"Linha 'Aggregated' não encontrada em {stats_file}")
    return None

# ---------------------------------------------------------------------------
# GERAÇÃO DO RESUMO CONSOLIDADO
# ---------------------------------------------------------------------------


def generate_summary(results: list[dict]) -> Path:
    """Grava o resumo_geral.csv com todos os resultados."""
    summary_file = RESULTS_DIR / "resumo_geral.csv"

    fieldnames = [
        "cenario", "carga", "usuarios",
        "requisicoes", "falhas",
        "mediana_ms", "p90_ms", "p95_ms", "p99_ms",
        "media_ms", "min_ms", "max_ms", "rps",
        "timestamp",
    ]

    with open(summary_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    log("OK", f"Resumo consolidado salvo em {summary_file}")
    return summary_file


def print_summary_table(results: list[dict]) -> None:
    """Exibe uma tabela resumida no terminal."""
    section("Resumo dos Resultados")

    header = f"{'Cenário':<14} {'Carga':<7} {'Users':>5} {'Reqs':>6} {'Falhas':>6} {'Mediana':>8} {'P95':>8} {'RPS':>6}"
    print(f"\n{C.BOLD}{header}{C.RESET}")
    print("─" * len(header))

    for r in results:
        falhas = int(r.get("falhas", 0) or 0)
        cor = C.RED if falhas > 0 else C.RESET
        print(
            f"{cor}"
            f"{r['cenario']:<14} "
            f"{r['carga']:<7} "
            f"{r['usuarios']:>5} "
            f"{r['requisicoes']:>6} "
            f"{r['falhas']:>6} "
            f"{r['mediana_ms']:>7}ms "
            f"{r['p95_ms']:>7}ms "
            f"{r['rps']:>6}"
            f"{C.RESET}"
        )

    print("")

# ---------------------------------------------------------------------------
# PONTO DE ENTRADA
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa suite completa de testes de desempenho do Link Extractor"
    )
    parser.add_argument(
        "--scenario",
        choices=[s.name for s in SCENARIOS],
        help="Rodar apenas um cenário específico",
    )
    parser.add_argument(
        "--load",
        choices=[l.name for l in LOAD_LEVELS],
        help="Rodar apenas um nível de carga específico",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Filtra cenários e cargas conforme argumentos
    scenarios = [
        s for s in SCENARIOS if not args.scenario or s.name == args.scenario]
    loads = [l for l in LOAD_LEVELS if not args.load or l.name == args.load]

    total = len(scenarios) * len(loads)

    section("Link Extractor — Suite de Testes de Desempenho")
    log("INFO", f"Cenários  : {[s.name for s in scenarios]}")
    log("INFO", f"Cargas    : {[l.name for l in loads]}")
    log("INFO", f"Duração   : {RUN_TIME} por teste")
    log("INFO", f"Total     : {total} teste(s)")
    log("INFO", f"Resultados: {RESULTS_DIR}/")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Verificações iniciais
    preflight(scenarios)

    # Loop principal
    all_results: list[dict] = []
    test_num = 0
    start_time = datetime.now()

    for scenario in scenarios:
        section(f"Cenário: {scenario.name}")

        for load in loads:
            test_num += 1
            print(f"\n{C.BOLD}  [ Teste {test_num}/{total} ]{C.RESET}")

            out_dir = run_locust(scenario, load)
            metrics = parse_stats(out_dir)

            if metrics:
                all_results.append({
                    "cenario":     scenario.name,
                    "carga":       load.name,
                    "usuarios":    load.users,
                    "requisicoes": metrics["requests"],
                    "falhas":      metrics["failures"],
                    "mediana_ms":  metrics["median"],
                    "p90_ms":      metrics["p90"],
                    "p95_ms":      metrics["p95"],
                    "p99_ms":      metrics["p99"],
                    "media_ms":    metrics["avg"],
                    "min_ms":      metrics["min"],
                    "max_ms":      metrics["max"],
                    "rps":         metrics["rps"],
                    "timestamp":   datetime.now().isoformat(timespec="seconds"),
                })

            if test_num < total:
                log("INFO",
                    f"Aguardando {COOLDOWN_SECONDS}s para o sistema estabilizar...")
                time.sleep(COOLDOWN_SECONDS)

    # Resultados finais
    elapsed = datetime.now() - start_time
    section(f"Testes Concluídos em {str(elapsed).split('.')[0]}")

    if all_results:
        print_summary_table(all_results)
        summary_file = generate_summary(all_results)
        print(f"\n  {C.BOLD}Próximo passo:{C.RESET} importe")
        print(f"  {C.CYAN}{summary_file}{C.RESET}")
        print("  no Excel / Google Sheets para gerar os gráficos comparativos.\n")
    else:
        log("WARN", "Nenhum resultado coletado — verifique os logs em resultados/*/locust.log")


if __name__ == "__main__":
    main()
