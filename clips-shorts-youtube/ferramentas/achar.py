#!/usr/bin/env python3
"""Acha as maiores lives de um assunto no YouTube que já terminaram e estão com o replay no ar.

Uso:
  python3 achar.py "gta 6" [--quando hoje|semana|mes] [--minutos 60] [--quantas 10] [--lingua pt]

Procura o assunto de alguns jeitos ("gta 6 live", "gta 6 ao vivo"...), fica só com vídeos longos (lives
gravadas), tira as repetidas e mostra as mais vistas primeiro, com o link de cada uma.
Escreve a lista em lives-achadas.json na pasta atual.
Lives da Twitch e do Kick não têm busca aqui: passe o link direto para o ouvir.py.
"""
import argparse
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

comum.no_ambiente()

QUANDO = {"hoje": "EgIIAg%253D%253D", "semana": "EgIIAw%253D%253D", "mes": "EgIIBA%253D%253D"}
JEITOS = {"pt": ["%s live", "%s ao vivo", "%s live completa", "%s gameplay ao vivo"],
          "en": ["%s live", "%s live stream", "%s full stream", "%s gameplay live"],
          "es": ["%s en vivo", "%s directo", "%s live", "%s directo completo"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assunto")
    ap.add_argument("--quando", default="semana", choices=list(QUANDO))
    ap.add_argument("--minutos", type=int, default=60, help="duração mínima para contar como live")
    ap.add_argument("--quantas", type=int, default=10)
    ap.add_argument("--lingua", default="pt", choices=list(JEITOS))
    a = ap.parse_args()
    vistos = {}
    for jeito in JEITOS[a.lingua]:
        busca = urllib.parse.quote(jeito % a.assunto)
        r = comum.ytdlp("--flat-playlist", "--playlist-end", "40", "--print",
                        "%(id)s\t%(duration)s\t%(view_count)s\t%(channel)s\t%(title)s",
                        "https://www.youtube.com/results?search_query=%s&sp=%s" % (busca, QUANDO[a.quando]), tempo=120)
        for linha in (r.stdout or "").splitlines():
            p = linha.split("\t")
            if len(p) < 5 or p[0] in vistos:
                continue
            try:
                dur, vis = float(p[1]), int(float(p[2]))
            except ValueError:
                continue  # still live, or no numbers
            if dur >= a.minutos * 60:
                vistos[p[0]] = {"link": "https://www.youtube.com/watch?v=" + p[0], "duracao": dur, "visualizacoes": vis,
                                "canal": p[3], "titulo": p[4]}
    lista = sorted(vistos.values(), key=lambda x: -x["visualizacoes"])[: a.quantas]
    if not lista:
        sys.exit("Não achei lives de \"%s\" com mais de %d minutos (%s). Tente --quando mes." % (a.assunto, a.minutos, a.quando))
    comum.escrever_json("lives-achadas.json", lista)
    for i, x in enumerate(lista, 1):
        print("%2d. %s | %s | %s visualizações\n    %s\n    %s" % (
            i, x["canal"], comum.duracao_falada(x["duracao"]), ("%d" % x["visualizacoes"]).replace(",", "."), x["titulo"], x["link"]))


if __name__ == "__main__":
    main()
