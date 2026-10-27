
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO = BASE_DIR / "data" / "oportunidades.json"

FONTES = [
    {
        "municipio": "Passo Fundo",
        "url": "https://www.pmpf.rs.gov.br/transparencia/concurso-publico/",
    },
    {
        "municipio": "Igrejinha",
        "url": "https://www.igrejinha.rs.gov.br/seletivos.php",
    },
]

CABECALHOS = {
    "User-Agent": "VagasRS/1.0 (coletor de editais públicos)"
}


def extrair_data(texto):
    datas = re.findall(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
        texto,
    )

    if not datas:
        return None

    try:
        dia, mes, ano = map(int, datas[-1])
        return date(ano, mes, dia)
    except ValueError:
        return None


def coletar_fonte(fonte):
    resposta = requests.get(
        fonte["url"],
        headers=CABECALHOS,
        timeout=30,
    )
    resposta.raise_for_status()

    soup = BeautifulSoup(resposta.text, "html.parser")
    hoje = datetime.now(timezone.utc).date()
    encontrados = {}

    for link in soup.find_all("a", href=True):
        texto_link = link.get_text(" ", strip=True)
        if not texto_link:
            continue

        contexto = link
        texto_contexto = ""

        for _ in range(7):
            if contexto is None:
                break

            texto_contexto = contexto.get_text(" ", strip=True)

            if (
                re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", texto_contexto)
                and re.search(
                    r"inscriç(?:ão|ões)\s+abertas|período",
                    texto_contexto,
                    re.IGNORECASE,
                )
            ):
                break

            contexto = contexto.parent

        if not texto_contexto:
            continue

        if not re.search(
            r"inscriç(?:ão|ões)\s+abertas",
            texto_contexto,
            re.IGNORECASE,
        ):
            continue

        prazo = extrair_data(texto_contexto)
        if prazo is None or prazo < hoje:
            continue

        url_edital = urljoin(fonte["url"], link["href"])

        if not url_edital.startswith("https://"):
            continue

        if url_edital.rstrip("/") == fonte["url"].rstrip("/"):
            continue

        titulo = texto_link

        for tag in contexto.find_all(
            ["h1", "h2", "h3", "h4", "strong", "b"]
        ):
            candidato = tag.get_text(" ", strip=True)
            if candidato and re.search(
                r"edital|processo seletivo|concurso",
                candidato,
                re.IGNORECASE,
            ):
                titulo = candidato
                break

        titulo = re.sub(r"\s+", " ", titulo).strip()

        if len(titulo) < 4:
            continue

        item = {
            "id": url_edital,
            "titulo": titulo,
            "municipio": fonte["municipio"],
            "orgao": fonte["municipio"],
            "categoria": "seletivo",
            "url": url_edital,
            "link": url_edital,
            "prazo_inscricao": prazo.isoformat(),
            "fonte_oficial": True,
            "fonte_nome": fonte["municipio"],
            "origem": fonte["url"],
        }

        encontrados[url_edital] = item

    print(
        f'{fonte["municipio"]}: '
        f'{len(encontrados)} oportunidade(s) encontrada(s)'
    )

    return list(encontrados.values())


def main():
    todas = []

    # Se uma fonte falhar, interrompe sem apagar os dados existentes.
    for fonte in FONTES:
        oportunidades = coletar_fonte(fonte)
        todas.extend(oportunidades)

    # Remove duplicatas e mantém apenas prazos válidos.
    hoje = datetime.now(timezone.utc).date()
    validas = {}

    for item in todas:
        try:
            prazo = date.fromisoformat(item["prazo_inscricao"])
        except (ValueError, KeyError, TypeError):
            continue

        if prazo >= hoje and item.get("fonte_oficial") is True:
            validas[item["url"]] = item

    dados = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "publicacoes": sorted(
            validas.values(),
            key=lambda item: item["prazo_inscricao"],
        ),
    }

    temporario = ARQUIVO.with_suffix(".tmp")

    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    temporario.replace(ARQUIVO)

    print(f"Total de oportunidades válidas: {len(validas)}")


if __name__ == "__main__":
    main()
    
