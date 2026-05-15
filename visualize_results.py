"""
=============================================================================
visualize_results.py — Visualização dos Resultados de Desempenho
=============================================================================

Lê o arquivo resultados/resumo_geral.csv gerado pelo run_tests.py
e produz 6 gráficos prontos para relatório com foco direto na 
comparação entre as linguagens (Ruby vs Python):

  1. P95 Ruby x Python (Sem Cache)
  2. P95 Ruby x Python (Com Cache)
  3. RPS Ruby x Python (Sem Cache)
  4. RPS Ruby x Python (Com Cache)
  5. Percentis Carga Alta (Sem Cache)
  6. Percentis Carga Alta (Com Cache)

Uso:
  python visualize_results.py
=============================================================================
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES
# ---------------------------------------------------------------------------

RESULTS_DIR  = Path("./resultados")
GRAPHICS_DIR = RESULTS_DIR / "graficos"
CSV_FILE     = RESULTS_DIR / "resumo_geral.csv"

LOAD_LABELS = {
    "baixa": "Baixa\n(100 users)",
    "media": "Média\n(200 users)",
    "alta":  "Alta\n(350 users)",
}

LOAD_ORDER     = ["baixa", "media", "alta"]
SCENARIO_ORDER = ["py_nocache", "py_cache", "rb_nocache", "rb_cache"]

# ---------------------------------------------------------------------------
# PALETA E ESTILO
# ---------------------------------------------------------------------------

# Cores fixas para as linguagens
COLOR_RUBY   = "#E8634C" # Vermelho
COLOR_PYTHON = "#4C9BE8" # Azul

BACKGROUND = "#F7F8FA"
GRID_COLOR = "#E0E3EA"
TEXT_COLOR = "#1C1C2E"

def apply_style() -> None:
    """Aplica estilo global consistente a todos os gráficos."""
    plt.rcParams.update({
        "figure.facecolor":   BACKGROUND,
        "axes.facecolor":     BACKGROUND,
        "axes.edgecolor":     GRID_COLOR,
        "axes.grid":          True,
        "axes.grid.axis":     "y",
        "grid.color":         GRID_COLOR,
        "grid.linewidth":     0.8,
        "text.color":         TEXT_COLOR,
        "axes.labelcolor":    TEXT_COLOR,
        "xtick.color":        TEXT_COLOR,
        "ytick.color":        TEXT_COLOR,
        "font.family":        "DejaVu Sans",
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.spines.left":   False,
        "axes.spines.bottom": True,
        "figure.dpi":         130,
    })

# ---------------------------------------------------------------------------
# CARREGAMENTO DOS DADOS
# ---------------------------------------------------------------------------

def load_data(csv_path: Path) -> pd.DataFrame:
    """Carrega e valida o CSV de resultados."""
    if not csv_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)

    # Converte colunas numéricas
    num_cols = ["p95_ms", "mediana_ms", "p90_ms", "p99_ms",
                "rps", "requisicoes", "falhas", "media_ms"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Garante ordem categórica
    df["carga"]   = pd.Categorical(df["carga"],   categories=LOAD_ORDER,     ordered=True)
    df["cenario"] = pd.Categorical(df["cenario"], categories=SCENARIO_ORDER, ordered=True)
    return df.sort_values(["cenario", "carga"])

# ---------------------------------------------------------------------------
# UTILITÁRIOS DE PLOT
# ---------------------------------------------------------------------------

def add_value_labels(ax, fmt="{:.0f}", fontsize=9, pad=3, color=TEXT_COLOR):
    """Adiciona rótulos de valor no topo de cada barra."""
    for bar in ax.patches:
        h = bar.get_height()
        if h > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + pad,
                fmt.format(h),
                ha="center", va="bottom",
                fontsize=fontsize, color=color, fontweight="bold",
            )

def style_ax(ax, title, ylabel, xlabel=None):
    """Aplica estilo padrão a um eixo."""
    ax.set_title(title, fontsize=13, fontweight="bold",
                 color=TEXT_COLOR, pad=14, loc="left")
    ax.set_ylabel(ylabel, fontsize=10, color=TEXT_COLOR)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, color=TEXT_COLOR)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

def save(fig, name: str, pdf: PdfPages) -> Path:
    """Salva figura como PNG e adiciona ao PDF."""
    path = GRAPHICS_DIR / name
    fig.savefig(path, bbox_inches="tight", dpi=150)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK]  Salvo: {path}")
    return path

# ---------------------------------------------------------------------------
# GRÁFICOS: COMPARAÇÃO DIRETA RUBY vs PYTHON
# ---------------------------------------------------------------------------

def plot_comparacao_metrica(df: pd.DataFrame, pdf: PdfPages, metrica: str, titulo: str, ylabel: str, arquivo: str, com_cache: bool) -> None:
    """Plota comparação direta entre Ruby e Python para uma métrica."""
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(BACKGROUND)

    rb_cenario = "rb_cache" if com_cache else "rb_nocache"
    py_cenario = "py_cache" if com_cache else "py_nocache"
    sufixo = "COM CACHE" if com_cache else "SEM CACHE"

    data_rb = df[df["cenario"] == rb_cenario].sort_values("carga")
    data_py = df[df["cenario"] == py_cenario].sort_values("carga")

    loads = [LOAD_LABELS[l].replace("\n", " ") for l in LOAD_ORDER]
    x     = range(len(loads))
    width = 0.35

    val_rb = [data_rb[data_rb["carga"]==l][metrica].values[0] if not data_rb[data_rb["carga"]==l].empty else 0 for l in LOAD_ORDER]
    val_py = [data_py[data_py["carga"]==l][metrica].values[0] if not data_py[data_py["carga"]==l].empty else 0 for l in LOAD_ORDER]

    # As barras dentro do gráfico agora são explicitamente as Linguagens
    ax.bar([xi - width/2 for xi in x], val_rb, width=width, color=COLOR_RUBY, label="Ruby", zorder=3)
    ax.bar([xi + width/2 for xi in x], val_py, width=width, color=COLOR_PYTHON, label="Python", zorder=3)

    add_value_labels(ax)

    ax.set_xticks(list(x))
    ax.set_xticklabels(loads, fontsize=10)
    ax.legend(fontsize=11, framealpha=0.9, title="Linguagem")
    style_ax(ax, title=f"{titulo}: Ruby vs Python ({sufixo})", ylabel=ylabel)

    fig.tight_layout()
    save(fig, arquivo, pdf)

def plot_percentis_carga_alta(df: pd.DataFrame, pdf: PdfPages, com_cache: bool, arquivo: str) -> None:
    """Plota distribuição de percentis (Mediana, P95, P99) focando Ruby vs Python."""
    df_alta = df[df["carga"] == "alta"].copy()
    if df_alta.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(BACKGROUND)

    rb_cenario = "rb_cache" if com_cache else "rb_nocache"
    py_cenario = "py_cache" if com_cache else "py_nocache"
    sufixo = "COM CACHE" if com_cache else "SEM CACHE"

    metrics   = ["mediana_ms", "p95_ms", "p99_ms"]
    labels    = ["Mediana (P50)", "P95", "P99"]
    x         = range(len(metrics))
    width     = 0.35

    val_rb = [df_alta.loc[df_alta["cenario"] == rb_cenario, m].values[0] if rb_cenario in df_alta["cenario"].values else 0 for m in metrics]
    val_py = [df_alta.loc[df_alta["cenario"] == py_cenario, m].values[0] if py_cenario in df_alta["cenario"].values else 0 for m in metrics]

    ax.bar([xi - width/2 for xi in x], val_rb, width=width, color=COLOR_RUBY, label="Ruby", zorder=3)
    ax.bar([xi + width/2 for xi in x], val_py, width=width, color=COLOR_PYTHON, label="Python", zorder=3)

    add_value_labels(ax)

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(fontsize=11, framealpha=0.9, title="Linguagem")
    style_ax(ax, title=f"Distribuição de Percentis (Carga Alta): Ruby vs Python ({sufixo})", ylabel="Tempo de Resposta (ms)")

    fig.tight_layout()
    save(fig, arquivo, pdf)

# ---------------------------------------------------------------------------
# PONTO DE ENTRADA
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera gráficos comparativos Ruby vs Python.")
    parser.add_argument("--csv", type=Path, default=CSV_FILE, help=f"Caminho para o CSV (padrão: {CSV_FILE})")
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    apply_style()
    GRAPHICS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[INFO] Carregando dados...")
    df = load_data(args.csv)

    pdf_path = GRAPHICS_DIR / "relatorio_comparativo_linguagens.pdf"
    print(f"[INFO] Gerando gráficos em {GRAPHICS_DIR}/\n")

    with PdfPages(pdf_path) as pdf:

        # 1. P95: Ruby vs Python (Sem Cache)
        plot_comparacao_metrica(df, pdf, metrica="p95_ms", titulo="Tempo de Resposta P95", 
                                ylabel="P95 (ms)", arquivo="1_p95_sem_cache.png", com_cache=False)
        
        # 2. P95: Ruby vs Python (Com Cache)
        plot_comparacao_metrica(df, pdf, metrica="p95_ms", titulo="Tempo de Resposta P95", 
                                ylabel="P95 (ms)", arquivo="2_p95_com_cache.png", com_cache=True)

        # 3. RPS: Ruby vs Python (Sem Cache)
        plot_comparacao_metrica(df, pdf, metrica="rps", titulo="Throughput (RPS)", 
                                ylabel="Requisições por Segundo", arquivo="3_rps_sem_cache.png", com_cache=False)
        
        # 4. RPS: Ruby vs Python (Com Cache)
        plot_comparacao_metrica(df, pdf, metrica="rps", titulo="Throughput (RPS)", 
                                ylabel="Requisições por Segundo", arquivo="4_rps_com_cache.png", com_cache=True)

        # 5. Percentis Carga Alta (Sem Cache)
        plot_percentis_carga_alta(df, pdf, com_cache=False, arquivo="5_percentis_alta_sem_cache.png")

        # 6. Percentis Carga Alta (Com Cache)
        plot_percentis_carga_alta(df, pdf, com_cache=True, arquivo="6_percentis_alta_com_cache.png")

    print(f"\n[OK]  PDF completo salvo em: {pdf_path}")
    print("\n  Gráficos gerados:")
    for f in sorted(GRAPHICS_DIR.glob("*.png")):
        print(f"    {f}")
    print(f"    {pdf_path}\n")

if __name__ == "__main__":
    main()