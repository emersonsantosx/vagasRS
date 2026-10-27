
import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
ARQUIVO = BASE_DIR / "data" / "oportunidades.json"

def main():
    with ARQUIVO.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    hoje = datetime.now(timezone.utc).date()
    anteriores = dados.get("publicacoes", [])
    validas = []
    ids = set()

    for item in anteriores:
        if not isinstance(item, dict):
            continue

        prazo = item.get("prazo_inscricao")
        url = item.get("link") or item.get("url") or ""

        if item.get("fonte_oficial") is not True:
            continue

        if not url.startswith("https://"):
            continue

        try:
            data_limite = date.fromisoformat(str(prazo)[:10])
        except (ValueError, TypeError):
            continue

        if data_limite < hoje:
            continue

        identificador = item.get("id") or url
        if identificador in ids:
            continue

        ids.add(identificador)
        validas.append(item)

    dados["publicacoes"] = validas
    dados["atualizado_em"] = datetime.now(
        timezone.utc
    ).isoformat()

    temporario = ARQUIVO.with_suffix(".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")

    temporario.replace(ARQUIVO)

    print(f"Oportunidades confirmadas: {len(validas)}")
    print(f"Publicações removidas: {len(anteriores) - len(validas)}")

if __name__ == "__main__":
    main()
    
