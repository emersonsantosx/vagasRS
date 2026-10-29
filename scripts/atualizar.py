
import json
from datetime import date, datetime, timezone
from pathlib import Path

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

HEADERS = {"User-Agent": "Mozilla/5.0 VagasRS/1.0"}


def coletar(fonte):
    resposta = requests.get(
        fonte["url"], headers=HEADERS, timeout=25
    )
    resposta.raise_for_status()
    soup = BeautifulSoup(resposta.text, "html.parser")
    hoje = datetime.now(timezone.utc).date()
    encontrados = {}

    for link in soup.find_all("a", href=True):
        titulo = link.get_text(" ", strip=True)
        if len(titulo) < 8:
            continue

        contexto = link.parent
        texto = ""

        for _ in range(5):
            if contexto is None:
                break
            texto = contexto.get_text(" ", strip=True)
            if len(texto) > len(titulo) + 20:
                break
            contexto = contexto.parent

        texto_lower = texto.lower()
        palavras = (
            "concurso", "processo seletivo",
            "edital", "inscrições abertas"
        )
        if not any(p in texto_lower for p in palavras):
            continue

        url = requests.compat.urljoin(fonte["url"], link["href"])
        if not url.startswith("https://"):
            continue

        # Só registra quando encontra um prazo explícito no contexto.
        import re
        datas = re.findall(
            r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", texto
        )
        prazo = None

        for dia, mes, ano in reversed(datas):
            try:
                candidata = date(int(ano), int(mes), int(dia))
                if candidata >= hoje:
                    prazo = candidata
                    break
            except ValueError:
                continue

        if prazo is None:
            continue

        if url.rstrip("/") == fonte["url"].rstrip("/"):
            continue

        categoria = (
            "concurso" if "concurso" in texto_lower
            else "seletivo"
        )

        encontrados[url] = {
            "id": url,
            "titulo": titulo,
            "municipio": fonte["municipio"],
            "orgao": fonte["municipio"],
            "categoria": categoria,
            "url": url,
            "link": url,
            "prazo_inscricao": prazo.isoformat(),
            "fonte_oficial": True,
            "fonte_nome": fonte["municipio"],
            "origem": fonte["url"],
        }

    print(f'{fonte["municipio"]}: {len(encontrados)} resultado(s)')
    return list(encontrados.values())


def main():
    anteriores = []

    if ARQUIVO.exists():
        try:
            with ARQUIVO.open(encoding="utf-8") as f:
                anteriores = json.load(f).get("publicacoes", [])
        except (json.JSONDecodeError, OSError):
            anteriores = []

    coletadas = []

    # Se uma fonte falhar, não substitui os dados atuais.
    for fonte in FONTES:
        coletadas.extend(coletar(fonte))

    # Nunca apaga o arquivo por uma coleta vazia.
    if not coletadas:
        print("Nenhum resultado novo. Arquivo atual preservado.")
        return

    hoje = datetime.now(timezone.utc).date()
    combinadas = {}

    for item in anteriores + coletadas:
        url = item.get("url") or item.get("link")
        if not url or not url.startswith("https://"):
            continue

        try:
            prazo = date.fromisoformat(item.get("prazo_inscricao", ""))
        except (ValueError, TypeError):
            continue

        if prazo < hoje:
            continue

        if item.get("fonte_oficial") is not True:
            continue

        item["url"] = url
        item["link"] = url
        combinadas[url] = item

    dados = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "publicacoes": sorted(
            combinadas.values(),
            key=lambda x: x["prazo_inscricao"],
        ),
    }

    temporario = ARQUIVO.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")

    temporario.replace(ARQUIVO)
    print(f"Total salvo: {len(combinadas)}")


if __name__ == "__main__":
    main()
    
