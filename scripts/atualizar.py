
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO = BASE_DIR / "data" / "oportunidades.json"

FONTE_RSS = (
    "https://news.google.com/rss/search?"
    "q=%28concurso+OR+%22processo+seletivo%22+OR+"
    "%22vagas+de+emprego%22%29+"
    "%22Rio+Grande+do+Sul%22"
    "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
)

PALAVRAS_RS = (
    "rio grande do sul", "rs", "porto alegre", "pelotas",
    "canoas", "caxias do sul", "santa maria", "gravataí",
    "novo hamburgo", "são leopoldo", "passo fundo", "uruguaiana",
    "bagé", "erechim", "santo ângelo", "rio grande",
    "bento gonçalves", "ljuí", "ijui", "taquara",
)

PALAVRAS_EXCLUIDAS = (
    "inscrições encerradas", "inscricoes encerradas",
    "resultado final", "homologação do resultado",
    "homologacao do resultado", "convocação de aprovados",
    "convocacao de aprovados", "gabarito definitivo",
)

def normalizar_url(url):
    partes = urlparse(url.strip())
    return urlunparse((
        partes.scheme.lower(),
        partes.netloc.lower(),
        partes.path.rstrip("/"),
        "",
        "",
        "",
    ))

def gerar_id(url, titulo):
    base = normalizar_url(url) or titulo.strip().lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]

def identificar_categoria(texto):
    texto = texto.lower()

    if "concurso" in texto:
        return "concurso"

    if "processo seletivo" in texto or "seleção simplificada" in texto:
        return "processo_seletivo"

    if "emprego" in texto or "vagas de emprego" in texto:
        return "emprego"

    return None

def carregar_dados():
    if not ARQUIVO.exists():
        raise FileNotFoundError(f"Arquivo ausente: {ARQUIVO}")

    with ARQUIVO.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados, dict):
        raise ValueError("O JSON deve conter um objeto.")

    if not isinstance(dados.get("publicacoes"), list):
        raise ValueError("O campo publicacoes deve ser uma lista.")

    if not all(isinstance(p, dict) for p in dados["publicacoes"]):
        raise ValueError("Existe publicação com formato inválido.")

    return dados


def coletar():
    resposta = requests.get(
        FONTE_RSS,
        timeout=30,
        headers={"User-Agent": "VagasRS/1.0"},
    )
    resposta.raise_for_status()
    feed = feedparser.parse(resposta.content)

    if not feed.entries:
        raise RuntimeError("A fonte RSS não retornou resultados.")

    resultados = []

    for item in feed.entries:
        titulo = re.sub(
            r"\s+", " ", item.get("title", "")
        ).strip()
        link = item.get("link", "").strip()
        resumo = re.sub(
            r"<[^>]+>", " ", item.get("summary", "")
        )
        resumo = re.sub(r"\s+", " ", resumo).strip()

        if not titulo or not link:
            continue

        texto = f"{titulo} {resumo}".lower()

        menciona_rs = any(
            p != "rs" and p in texto
            for p in PALAVRAS_RS
        ) or bool(re.search(r"\bRS\b", f"{titulo} {resumo}"))

        if not menciona_rs:
            continue

        categoria = identificar_categoria(texto)
        if not categoria:
            continue

        if any(p in texto for p in PALAVRAS_EXCLUIDAS):
            continue

        resultados.append({
            "id": gerar_id(link, titulo),
            "titulo": titulo,
            "orgao": "",
            "local": "Rio Grande do Sul",
            "categoria": categoria,
            "link": link,
            "resumo": resumo[:500],
            "publicado_em": item.get("published", ""),
            "origem": "Google News RSS",
        })

    return resultados
    

def main():
    dados = carregar_dados()

    # Se a fonte falhar, o script para sem alterar o arquivo.
    novas = coletar()
    publicacoes = dados["publicacoes"]

    ids = {
        p.get("id") or gerar_id(
            p.get("link", ""), p.get("titulo", "")
        )
        for p in publicacoes
    }

    adicionadas = 0

    for item in novas:
        if item["id"] in ids:
            continue

        publicacoes.append(item)
        ids.add(item["id"])
        adicionadas += 1

    dados["publicacoes"] = publicacoes
    dados["atualizado_em"] = datetime.now(
        timezone.utc
    ).isoformat()

    temporario = ARQUIVO.with_suffix(".tmp")

    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    temporario.replace(ARQUIVO)

    print(f"Novas publicações: {adicionadas}")
    print(f"Total no banco: {len(publicacoes)}")

if __name__ == "__main__":
    main()
    
