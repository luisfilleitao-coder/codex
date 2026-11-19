#!/usr/bin/env python3
"""Confere os momentos escolhidos antes de cortar: acerta o começo e o fim nas frases, mede cada um e mostra o texto exato.

Uso:
  python3 conferir.py <pasta da live> [--manter 3] [--minimo 15] [--maximo 60]

Lê <pasta da live>/momentos.json, escrito depois de ler as janelas:
  {"momentos": [{"inicio": "1:23:45", "fim": "1:24:20", "nota": 87, "tipo": "reação",
                 "titulo": "o título que aparece no corte", "motivo": "por que alguém compartilharia",
                 "legenda": "a legenda do post", "hashtags": ["#gta6", "#cortes"]}]}

Para cada momento: puxa o começo para o início da frase e o fim para o final da frase, confere a duração,
vê se dois momentos se cruzam e mostra o que é dito, palavra por palavra, para ler se ele se sustenta sozinho.
Escreve momentos-conferidos.json com os melhores marcados para o corte (--manter).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

MULETAS = ("é...", "então", "aí", "e aí", "tipo", "mas", "e ", "só que", "enfim", "ou seja", "so ", "and ", "but ", "uh", "um ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--manter", type=int, default=3)
    ap.add_argument("--minimo", type=float, default=15)
    ap.add_argument("--maximo", type=float, default=60)
    a = ap.parse_args()
    pasta = Path(a.pasta)
    dado = comum.ler_json(pasta / "momentos.json")
    if not dado or not dado.get("momentos"):
        sys.exit("Não achei momentos em %s" % (pasta / "momentos.json"))
    frases = comum.ler_json(pasta / "transcricao.json")["frases"]
    sinais = comum.ler_json(pasta / "sinais.json", {"gritos": [], "chat": []})
    saida, avisos_gerais = [], 0
    for n, m in enumerate(dado["momentos"], 1):
        ini, fim = comum.segundos(m["inicio"]), comum.segundos(m["fim"])
        avisos = []
        # the start goes to the beginning of the sentence that holds it, the end to the end of the sentence that holds it
        dentro = [f for f in frases if f["e"] > ini + 0.5 and f["s"] < fim - 0.5]
        if not dentro:
            avisos.append("não há fala nesse trecho")
            dentro = []
        else:
            if abs(dentro[0]["s"] - ini) <= 4:
                ini = dentro[0]["s"]
            if abs(dentro[-1]["e"] - fim) <= 4:
                fim = dentro[-1]["e"]
        ini, fim = max(0.0, ini - 0.25), fim + 0.35
        dur = fim - ini
        if dur < a.minimo:
            avisos.append("curto demais (%.0f s)" % dur)
        if dur > a.maximo:
            avisos.append("longo demais (%.0f s): corte o que não precisa" % dur)
        texto = " ".join(f["t"] for f in dentro)
        primeira = texto.lower().lstrip("¿¡ ")
        if any(primeira.startswith(x) for x in MULETAS):
            avisos.append("começa no meio de um raciocínio (\"%s\")" % texto[:25])
        if len(m.get("titulo", "")) > 60:
            avisos.append("título com mais de 60 letras")
        if not m.get("titulo"):
            avisos.append("sem título")
        for outro in saida:
            if ini < outro["fim_s"] and fim > outro["inicio_s"]:
                avisos.append("cruza com o momento %d" % outro["n"])
        grito = max([g["db"] for g in sinais["gritos"] if g["s"] <= fim and g["e"] >= ini] or [0])
        chat = max([c["vezes"] for c in sinais["chat"] if c["s"] <= fim + 15 and c["e"] >= ini] or [0])
        item = dict(m)
        item.update({"n": n, "inicio_s": round(ini, 2), "fim_s": round(fim, 2), "duracao": round(dur, 1),
                     "inicio": comum.relogio(ini), "fim": comum.relogio(fim), "grito_db": grito, "chat_vezes": chat,
                     "texto": texto, "avisos": avisos, "nota": float(m.get("nota", 0))})
        saida.append(item)
        avisos_gerais += len(avisos)
    ordem = sorted(saida, key=lambda x: -x["nota"])
    bons = [x for x in ordem if not any(("cruza" in w or "não há fala" in w or "demais" in w) for w in x["avisos"])]
    mantidos = {x["n"] for x in bons[: a.manter]}
    for x in saida:
        x["manter"] = x["n"] in mantidos
    comum.escrever_json(pasta / "momentos-conferidos.json", {"momentos": saida})
    print("%d momentos conferidos, %d mantidos para o corte\n" % (len(saida), len(mantidos)))
    for x in ordem:
        sinal = ("ALTO+%.0fdB " % x["grito_db"] if x["grito_db"] else "") + ("CHAT x%.1f" % x["chat_vezes"] if x["chat_vezes"] else "")
        print("%s %2d | nota %3.0f | %s a %s | %2.0f s | %s %s" % ("CORTA" if x["manter"] else "     ", x["n"], x["nota"], x["inicio"], x["fim"], x["duracao"], x.get("tipo", ""), sinal))
        print("        título: %s" % x.get("titulo", ""))
        print("        fala:   %s" % x["texto"])
        for w in x["avisos"]:
            print("        AVISO:  %s" % w)
        print()
    if avisos_gerais:
        print("Há avisos. Arrume momentos.json (ou troque o momento) e rode de novo antes de cortar.")


if __name__ == "__main__":
    main()
