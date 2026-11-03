"""Baixa dados abertos da Câmara dos Deputados e monta uma base DuckDB.

Instalação:  pip install requests duckdb
Uso:         python coletar_camara.py --inicio 2023 --fim 2026
"""
import argparse
import sys
from pathlib import Path

import duckdb
import requests

BASE = "https://dadosabertos.camara.leg.br/arquivos"
CONJUNTOS = {
    "proposicoes": "proposicoes",
    "proposicoesAutores": "autores",
    "proposicoesTemas": "temas",
    "votacoes": "votacoes",
    "votacoesVotos": "votos",
    "votacoesProposicoes": "votacoes_proposicoes",
}
PASTA = Path("dados/brutos")


def baixar(conjunto: str, ano: int) -> Path | None:
    destino = PASTA / conjunto / f"{conjunto}-{ano}.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{conjunto}/csv/{conjunto}-{ano}.csv"
    try:
        with requests.get(url, stream=True, timeout=(15, 300)) as resposta:
            resposta.raise_for_status()
            temporario = destino.with_suffix(".parcial")
            with temporario.open("wb") as arquivo:
                for bloco in resposta.iter_content(1024 * 1024):
                    arquivo.write(bloco)
        temporario.replace(destino)  # só substitui se o download terminou
        print(f"OK     {destino.name}")
        return destino
    except requests.RequestException as erro:
        print(f"FALHA  {conjunto}-{ano}: {erro}", file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio", type=int, default=2023)
    parser.add_argument("--fim", type=int, default=2026)
    parser.add_argument("--base", default="camara.duckdb")
    args = parser.parse_args()

    banco = duckdb.connect(args.base)
    falhas = 0
    for conjunto, tabela in CONJUNTOS.items():
        arquivos = []
        for ano in range(args.inicio, args.fim + 1):
            arquivo = baixar(conjunto, ano)
            if arquivo:
                arquivos.append(str(arquivo))
            else:
                falhas += 1
        if not arquivos:
            continue
        banco.execute(
            f"CREATE OR REPLACE TABLE {tabela} AS "
            "SELECT * FROM read_csv(?, union_by_name=true, all_varchar=true, "
            "filename=true)",
            [arquivos],
        )
        total = banco.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
        print(f"Tabela {tabela}: {total} linhas")

    banco.close()
    print(f"Base salva em {args.base}. Downloads com falha: {falhas}")
    if falhas:
        sys.exit(1)


if __name__ == "__main__":
    main()
