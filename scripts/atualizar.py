
import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_DADOS = BASE_DIR / "data" / "oportunidades.json"

FONTES_RSS = [
    "https://www.google.com/alerts/feeds/00000000000000000000/00000000000000000000",
]

CATEGORIAS = {
    "concurso": "concurso",
    "concursos": "concurso",
    "processo seletivo": "processo_seletivo",
    "processos seletivos": "processo_seletivo",
    "emprego": "emprego",
    "empregos": "emprego",
    "vagas": "emprego",
    "seleção simplificada": "processo_seletivo",
    "selecao simplificada": "processo_seletivo",
}

PALAVRAS_RELEVANTES = (
    "concurso público",
    "concurso publico",
    "processo seletivo",
    "seleção simplificada",
    "selecao simplificada",
    "edital",
    "vagas de emprego",
    "oportunidade de emprego",
)

def carregar_dados():
    if not ARQUIVO_DADOS.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {ARQUIVO_DADOS}")

    with ARQUIVO_DADOS.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados, dict):
        raise ValueError("O JSON precisa conter um objeto.")

    if not isinstance(dados.get("publicacoes"), list):
        raise ValueError("O campo 'publicacoes' precisa ser uma lista.")

    return dados

def normalizar_url(url):
    if not url:
        return ""

    partes = urlparse(url.strip())
    return urlunparse((
        partes.scheme.lower(),
        partes.netloc.lower(),
        partes.path.rstrip("/"),
        "",
        "",
        "",
    ))

def identificar_categoria(texto):
    texto = texto.lower()

    if "concurso" in texto:
        return "concurso"

    if any(p in texto for p in (
        "processo seletivo",
        "seleção simplificada",
        "selecao simplificada",
    )):
        return "processo_seletivo"

    if any(p in texto for p in (
        "emprego",
        "vagas de emprego",
        "oportunidade de emprego",
    )):
        return "emprego"

    return None

def obter_id(url, titulo):
    base = normalizar_url(url) or titulo.strip().lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]

def coletar_publicacoes():
    novas = []

    for fonte in FONTES_RSS:
        try:
            resposta = requests.get(
                fonte,
                timeout=20,
                headers={"User-Agent": "VagasRS/1.0"},
            )
            resposta.raise_for_status()
            feed = feedparser.parse(resposta.content)
        except requests.RequestException as erro:
            print(f"Fonte indisponível: {erro}")
            continue

        for item in feed.entries:
            titulo = re.sub(r"\s+", " ", item.get("title", "")).strip()
            link = item.get("link", "").strip()
            resumo = re.sub(
                r"<[^>]+>", " ", item.get("summary", "")
            )
            resumo = re.sub(r"\s+", " ", resumo).strip()

            if not titulo or not link:
                continue

            texto = f"{titulo} {resumo}".lower()

            if not any(p in texto for p in PALAVRAS_RELEVANTES):
                continue

            categoria = identificar_categoria(texto)
            if not categoria:
                continue

            novas.append({
                "id": obter_id(link, titulo),
                "titulo": titulo,
                "orgao": "",
                "local": "Rio Grande do Sul",
                "categoria": categoria,
                "link": link,
                "resumo": resumo[:500],
                "publicado_em": item.get("published", ""),
                "origem": "Google News/RSS",
            })

    return novas

def main():
    dados = carregar_dados()
    existentes = dados["publicacoes"]

    if not all(isinstance(item, dict) for item in existentes):
        raise ValueError("Há publicações com formato inválido no JSON.")

    ids_existentes = {
        item.get("id") or obter_id(item.get("link", ""), item.get("titulo", ""))
        for item in existentes
    }

    novas = coletar_publicacoes()
    adicionadas = 0

    for item in novas:
        if item["id"] in ids_existentes:
            continue

        existentes.append(item)
        ids_existentes.add(item["id"])
        adicionadas += 1

    dados["atualizado_em"] = datetime.now(timezone.utc).isoformat()
    dados["publicacoes"] = existentes

    temporario = ARQUIVO_DADOS.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    temporario.replace(ARQUIVO_DADOS)
    print(f"Publicações novas adicionadas: {adicionadas}")
    print(f"Total de publicações: {len(existentes)}")

if __name__ == "__main__":
    main()
