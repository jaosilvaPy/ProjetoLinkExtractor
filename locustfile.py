"""
=============================================================================
locustfile.py — Teste de Desempenho: Link Extractor API
=============================================================================

CENÁRIOS SUPORTADOS (altere --host ao iniciar o Locust):
  Cenário 1 — Python sem cache : --host http://localhost:5001
  Cenário 2 — Python com cache : --host http://localhost:5002
  Cenário 3 — Ruby sem cache   : --host http://localhost:5003
  Cenário 4 — Ruby com cache   : --host http://localhost:5004

COMO EXECUTAR (via docker-compose):
  Altere o campo `command` no docker-compose.yml para o host desejado:
    command: -f /mnt/locust/locustfile.py --host http://api-py-nocache:5000

COMO EXECUTAR (localmente, sem Docker):
  locust -f locustfile.py --host http://localhost:5001

CARGAS RECOMENDADAS PARA OS CENÁRIOS:
  Baixa  → 100 usuários,  spawn rate 10
  Média  → 200 usuários,  spawn rate 20
  Alta   → 350 usuários,  spawn rate 35

EXPORTAR RESULTADOS:
  Via UI  → http://localhost:8089 → botão "Download Data"
  Via CLI → adicione as flags abaixo ao comando locust:
    --headless
    --users 20
    --spawn-rate 5
    --run-time 2m
    --csv resultados/py_nocache_medio
=============================================================================
"""

import os
import logging
from locust import HttpUser, task, between, events

# ---------------------------------------------------------------------------
# Lista de 10 URLs usadas em cada sequência de teste
# Escolhidas por serem públicas, estáveis e com conteúdo variado de links
# ---------------------------------------------------------------------------
URLS_TO_TEST = [
    "http://example.com/",
    "https://books.toscrape.com/",
    "https://httpbin.org/",
    "https://www.python.org/",
    "https://docs.docker.com/",
    "https://flask.palletsprojects.com/",
    "https://redis.io/",
    "https://locust.io/",
    "https://github.com/ibnesayeed/linkextractor",
    "https://training.play-with-docker.com/",
]

# ---------------------------------------------------------------------------
# Logger dedicado para registrar erros de forma legível no terminal
# ---------------------------------------------------------------------------
logger = logging.getLogger("linkextractor")


# ===========================================================================
# Classe principal do usuário virtual
# ===========================================================================
class LinkExtractorUser(HttpUser):
    """
    Simula um usuário que invoca o serviço de extração de links
    passando 10 URLs diferentes em sequência, uma por vez.

    O tempo de espera entre ciclos completos (10 chamadas) é de 1 a 3 segundos,
    simulando um usuário humano navegando entre requisições.
    """

    wait_time = between(1, 3)  # pausa entre ciclos completos (segundos)

    @task
    def extract_links_sequence(self):
        """
        Tarefa principal: itera sobre as 10 URLs em sequência.

        Cada chamada é nomeada individualmente no Locust (parâmetro `name`)
        para que as métricas apareçam agrupadas por URL nos relatórios,
        facilitando a análise de P50, P95 e P99 por endpoint.
        """
        for url in URLS_TO_TEST:
            # Endpoint da API: GET /api/<url>
            # O Flask usa <path:url>, então a URL vai direto no path
            endpoint = f"/api/{url}"

            with self.client.get(
                endpoint,
                name=f"GET /api/ -> {url}",   # rótulo no relatório Locust
                catch_response=True,          # permite inspecionar a resposta
                # timeout por requisição (segundos)
                timeout=30,
            ) as response:

                # Validação da resposta
                if response.status_code == 200:
                    try:
                        data = response.json()

                        # Verifica se a resposta contém a estrutura esperada
                        if not isinstance(data, (list, dict)):
                            response.failure(
                                f"Resposta inesperada para {url}: {str(data)[:100]}"
                            )
                        else:
                            response.success()

                    except ValueError:
                        response.failure(
                            f"Resposta não é JSON válido para {url}"
                        )

                elif response.status_code == 404:
                    response.failure(f"URL não encontrada (404): {url}")

                elif response.status_code >= 500:
                    response.failure(
                        f"Erro interno do servidor ({response.status_code}) para {url}"
                    )

                else:
                    # Outros códigos são registrados mas não marcados como falha
                    logger.warning(
                        f"Status inesperado {response.status_code} para {url}"
                    )
                    response.success()


# ===========================================================================
# Eventos de ciclo de vida — usados para logging e organização dos resultados
# ===========================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Executado uma vez quando o teste começa."""
    host = environment.host or os.environ.get("TARGET_HOST", "não definido")
    users = environment.parsed_options.num_users if environment.parsed_options else "?"
    logger.info("=" * 60)
    logger.info("  TESTE INICIADO")
    logger.info(f"  Host alvo   : {host}")
    logger.info(f"  Usuários    : {users}")
    logger.info(f"  URLs/ciclo  : {len(URLS_TO_TEST)}")
    logger.info("=" * 60)
    print(f"\n[Locust] Iniciando teste contra: {host}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Executado uma vez quando o teste termina."""
    logger.info("=" * 60)
    logger.info("  TESTE FINALIZADO")
    logger.info("  Acesse http://localhost:8089 para ver os resultados")
    logger.info("  Ou use --csv <prefixo> para exportar automaticamente")
    logger.info("=" * 60)
    print("\n[Locust] Teste concluído. Verifique os resultados na UI.\n")
