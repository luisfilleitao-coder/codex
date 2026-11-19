#!/usr/bin/env python3
"""Ouve uma live inteira no seu computador e deixa tudo pronto para escolher os momentos.

Uso:
  python3 ouvir.py <link da live> [--pasta lives] [--lingua pt] [--cookies chrome] [--sem-chat]

O que faz:
  1. Baixa só o áudio (uma live de 4 horas vira umas centenas de MB, não um vídeo gigante).
  2. Transcreve a live inteira com o Whisper, aqui no computador.
  3. Mede o volume segundo a segundo e marca onde o streamer ficou bem mais alto que o normal.
  4. Se a live tiver replay do chat, conta as mensagens e marca onde o chat disparou.

Escreve em <pasta>/<id da live>/:
  info.json          o título, o canal, a duração, o link
  transcricao.json   cada frase com o segundo em que começa e termina
  sinais.json        o volume, os gritos e os picos do chat
  janelas/           a transcrição em janelas de 12 minutos, com ALTO nos gritos e CHAT nos picos do chat
  resumo.md          os números da live e os maiores picos
  tempos.json        quanto tempo cada passo levou
"""
import argparse
import json
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

comum.no_ambiente()
import numpy as np  # noqa: E402

BLOCO = 600   # seconds of audio handed to Whisper at a time
FOLGA = 20    # the cut between two blocks falls on the quietest half second inside this stretch


def baixar_info(link, pasta, cookies):
    r = comum.ytdlp("-J", "--skip-download", link, cookies=cookies)
    if r.returncode:
        sys.exit("Não consegui ler a live:\n" + r.stderr[-1200:] +
                 "\nSe o site pede login ou a live tem restrição de idade, rode de novo com --cookies chrome")
    d = json.loads(r.stdout)
    info = {"id": d.get("id"), "titulo": d.get("title"), "canal": d.get("channel") or d.get("uploader"),
            "duracao": d.get("duration"), "link": d.get("webpage_url") or link, "site": d.get("extractor_key"),
            "lingua": (d.get("language") or "")[:2] or None, "visualizacoes": d.get("view_count"),
            "ao_vivo": d.get("live_status")}
    if info["ao_vivo"] == "is_live":
        sys.exit("Essa live ainda está no ar. Espere ela terminar e o replay aparecer.")
    destino = Path(pasta) / re.sub(r"[^A-Za-z0-9_-]", "_", str(info["id"]))
    destino.mkdir(parents=True, exist_ok=True)
    comum.escrever_json(destino / "info.json", info)
    return info, destino


def baixar_audio(info, destino, cookies):
    pronto = [p for p in destino.glob("audio.*") if p.suffix not in (".part", ".ytdl")]
    if pronto:
        return pronto[0], False
    # never a "drc" format: it flattens the loud moments we are looking for.
    # a site with no audio-only format (Kick) gives its smallest video instead of its biggest
    r = comum.ytdlp("-f", "ba[abr<=70][format_id!*=drc][protocol^=http]/ba[format_id!*=drc][protocol^=http]/ba[format_id!*=drc]/ba/w",
                    "-o", str(destino / "audio.%(ext)s"), info["link"], cookies=cookies)
    pronto = [p for p in destino.glob("audio.*") if p.suffix not in (".part", ".ytdl")]
    if r.returncode or not pronto:
        sys.exit("Não consegui baixar o áudio:\n" + r.stderr[-1200:])
    return pronto[0], True


def baixar_chat(info, destino, cookies, limite):
    """YouTube and Twitch keep a replay of the chat for some streams. Best effort, never stops the run."""
    if any(p.suffix == ".json" and p.name != "chat-contagem.json" for p in destino.glob("chat*")):
        return  # already here from an earlier run
    lingua = {"Youtube": "live_chat", "TwitchVod": "rechat"}.get(info.get("site") or "", "live_chat")
    comum.ytdlp("--skip-download", "--write-subs", "--sub-langs", lingua, "-o", str(destino / "chat"),
                info["link"], cookies=cookies, tempo=limite)


def tempos_do_chat(destino):
    """Seconds into the stream of every chat message, from whatever chat file yt-dlp left."""
    tempos = []
    for arq in sorted(destino.glob("chat*")):
        if arq.suffix == ".md" or arq.name == "chat-contagem.json":
            continue
        try:
            texto = arq.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "rechat" in arq.name:  # Twitch: one JSON list
            try:
                for m in json.loads(texto):
                    tempos.append(float(m.get("content_offset_seconds", 0)))
            except Exception:
                pass
            continue
        for linha in texto.splitlines():  # YouTube: one JSON per line
            m = re.search(r'"videoOffsetTimeMsec":\s*"?(-?\d+)', linha)
            if m and int(m.group(1)) >= 0 and '"addChatItemAction"' in linha:
                tempos.append(int(m.group(1)) / 1000.0)
    return sorted(tempos)


def volume_por_segundo(arq):
    """The level of every second of the stream, in dB, counted on the stream's own clock (no second is skipped)."""
    niveis, resto = [], np.zeros(0, dtype=np.int16)
    for pedaco in comum.audio_em_blocos(arq, bloco=comum.TAXA * 60):
        junto = np.concatenate([resto, pedaco])
        n = len(junto) // comum.TAXA * comum.TAXA
        if n:
            x = junto[:n].astype(np.float32) / 32768.0
            rms = np.sqrt((x.reshape(-1, comum.TAXA) ** 2).mean(axis=1) + 1e-10)
            niveis.extend((20 * np.log10(rms)).round(1).tolist())
        resto = junto[n:]
    if len(resto) >= comum.TAXA // 2:
        x = resto.astype(np.float32) / 32768.0
        niveis.append(round(float(20 * np.log10(np.sqrt((x ** 2).mean() + 1e-10))), 1))
    return niveis


def mediana_que_anda(x, meia):
    n = len(x)
    out = np.zeros(n)
    for i in range(n):
        out[i] = np.median(x[max(0, i - meia): i + meia + 1])
    return out


def juntar(marcas, vao, minimo):
    """Indexes that are on -> list of (first, last), joining gaps up to vao and dropping runs shorter than minimo."""
    eventos = []
    for i in np.flatnonzero(marcas):
        if eventos and i - eventos[-1][1] <= vao:
            eventos[-1][1] = i
        else:
            eventos.append([i, i])
    return [(a, b) for a, b in eventos if b - a + 1 >= minimo]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("link")
    ap.add_argument("--pasta", default="lives")
    ap.add_argument("--lingua", default="", help="pt, en, es... (vazio = a da live, ou descobre sozinho)")
    ap.add_argument("--cookies", default="", help="navegador de onde ler o login: chrome, safari, firefox")
    ap.add_argument("--sem-chat", action="store_true")
    ap.add_argument("--tempo-chat", type=int, default=900, help="segundos no máximo esperando o replay do chat")
    ap.add_argument("--janela", type=int, default=12, help="minutos por janela de transcrição")
    ap.add_argument("--modelo", default="", help="modelo do Whisper (vazio = o melhor para este computador)")
    a = ap.parse_args()

    info, destino = baixar_info(a.link, a.pasta, a.cookies)
    tempos = comum.Tempos(destino)
    print("Live: %s | %s | %s" % (info["canal"], info["titulo"], comum.duracao_falada(info["duracao"] or 0)))

    fio = None
    if not a.sem_chat:
        fio = threading.Thread(target=baixar_chat, args=(info, destino, a.cookies, a.tempo_chat), daemon=True)
        fio.start()

    tempos.comeca("baixar_audio")
    arq, novo = baixar_audio(info, destino, a.cookies)
    if novo:
        print("1/4 áudio baixado: %.0f MB em %s" % (arq.stat().st_size / 1e6, comum.duracao_falada(tempos.termina())))
    else:
        print("1/4 áudio já estava aqui: %.0f MB" % (arq.stat().st_size / 1e6))

    # 2 and 3: one pass over the audio, block by block: the volume of every second and the transcript
    tempos.comeca("ouvir")
    feito = comum.ler_json(destino / "transcricao.json")
    if feito and feito.get("completa"):
        segs, lingua = feito["frases"], feito["lingua"]
        if feito.get("versao") != 2:  # an older run counted the seconds per block and drifted
            feito.update({"volume": volume_por_segundo(arq), "versao": 2})
            comum.escrever_json(destino / "transcricao.json", feito)
        volume = np.array(feito["volume"])
        levou = tempos.dado.get("ouvir", 0)  # a second run keeps the time the real listening took
    else:
        segs = []
        lingua = a.lingua or info.get("lingua") or None
        total = info["duracao"] or 0
        fila = np.zeros(0, dtype=np.int16)
        andado = 0  # samples already handed to Whisper
        fonte = comum.audio_em_blocos(arq)
        acabou = False
        while not acabou or len(fila):
            while not acabou and len(fila) < (BLOCO + FOLGA) * comum.TAXA:
                try:
                    fila = np.concatenate([fila, next(fonte)])
                except StopIteration:
                    acabou = True
            if len(fila) >= (BLOCO + FOLGA) * comum.TAXA:
                trecho = fila[BLOCO * comum.TAXA:(BLOCO + FOLGA) * comum.TAXA].astype(np.float32)
                meio = comum.TAXA // 2
                energia = (trecho[: len(trecho) // meio * meio].reshape(-1, meio) ** 2).mean(axis=1)
                corte = BLOCO * comum.TAXA + int(np.argmin(energia)) * meio + meio // 2
            else:
                corte = len(fila)
            pedaco, fila = fila[:corte], fila[corte:]
            if not len(pedaco):
                break
            base = andado / comum.TAXA
            achados, lingua_achada = comum.transcrever(pedaco, lingua=lingua, modelo=a.modelo or None)
            lingua = lingua or lingua_achada
            for s in achados:
                if s["t"]:
                    segs.append({"s": round(base + s["s"], 2), "e": round(base + s["e"], 2), "t": s["t"]})
            andado += len(pedaco)
            print("    ouvido até %s%s" % (comum.relogio(andado / comum.TAXA), " de " + comum.relogio(total) if total else ""), flush=True)
        niveis = volume_por_segundo(arq)
        volume = np.array(niveis)
        comum.escrever_json(destino / "transcricao.json", {"completa": True, "versao": 2, "lingua": lingua, "frases": segs, "volume": niveis})
        levou = tempos.termina()
    horas = len(volume) / 3600.0
    print("2/4 live ouvida: %s de áudio, %d frases, em %s" % (comum.duracao_falada(len(volume)), len(segs), comum.duracao_falada(levou)))

    # 3: where the streamer got much louder than the minutes around
    base = mediana_que_anda(volume, 150)
    sobra = volume - base
    falado = volume > np.percentile(volume, 40)
    limite = max(6.0, float(np.percentile(sobra[falado], 97))) if falado.any() else 6.0
    gritos = [{"s": int(a_), "e": int(b_) + 1, "db": round(float(sobra[a_:b_ + 1].max()), 1)}
              for a_, b_ in juntar((sobra >= limite) & falado, 2, 1)]
    print("3/4 volume medido: %d momentos bem acima do normal (%.1f dB ou mais)" % (len(gritos), limite))

    # 4: where the chat suddenly ran much faster than the minutes around
    picos, mensagens = [], 0
    if fio is not None:
        fio.join(timeout=a.tempo_chat + 30)
        marcas = tempos_do_chat(destino)
        mensagens = len(marcas)
        if mensagens >= 200:
            caixas = np.bincount((np.array(marcas) // 10).astype(int), minlength=int(len(volume) // 10) + 1).astype(float)
            normal = np.maximum(mediana_que_anda(caixas, 15), 1.0)
            vezes = caixas / normal
            coberto = int(max(marcas) // 10)
            minimo = max(5.0, float(np.percentile(caixas[: coberto + 1], 90)))
            caixas[0] = 0  # everything typed before the stream began lands on second zero
            for a_, b_ in juntar((vezes >= 2.5) & (caixas >= minimo), 1, 1):
                picos.append({"s": int(a_) * 10, "e": (int(b_) + 1) * 10, "vezes": round(float(vezes[a_:b_ + 1].max()), 1),
                              "mensagens": int(caixas[a_:b_ + 1].sum())})
            comum.escrever_json(destino / "chat-contagem.json", {"mensagens": mensagens, "ate": round(max(marcas)), "por_10s": caixas.astype(int).tolist()})
            print("4/4 chat lido: %d mensagens até %s, %d picos" % (mensagens, comum.relogio(max(marcas)), len(picos)))
        else:
            print("4/4 essa live não tem replay do chat (ou ele não veio): sigo com a transcrição e o volume")
    else:
        print("4/4 chat pulado")

    comum.escrever_json(destino / "sinais.json", {"gritos": gritos, "chat": picos, "limite_db": round(limite, 1), "mensagens": mensagens})

    # the transcript in windows, with the marks on the lines
    def marca(s, e):
        m = ""
        g = [x for x in gritos if x["s"] <= e and x["e"] >= s]
        if g:
            m += "ALTO+%.0fdB " % max(x["db"] for x in g)
        c = [x for x in picos if x["s"] <= e + 15 and x["e"] >= s]
        if c:
            m += "CHAT x%.1f " % max(x["vezes"] for x in c)
        return m + "| " if m else ""

    pasta_j = destino / "janelas"
    pasta_j.mkdir(exist_ok=True)
    for velho in pasta_j.glob("janela-*.md"):
        velho.unlink()
    passo = a.janela * 60
    n = int(np.ceil(len(volume) / passo)) or 1
    for i in range(n):
        ini, fim = i * passo, (i + 1) * passo
        linhas = ["# Janela %d de %d: %s a %s" % (i + 1, n, comum.relogio(ini), comum.relogio(min(fim, len(volume)))),
                  "%s | %s" % (info["canal"], info["titulo"]), "",
                  "ALTO+9dB = o streamer ficou 9 dB acima do normal daqueles minutos. CHAT x3.1 = o chat andou 3,1 vezes mais rápido.", ""]
        for s in segs:
            if ini <= s["s"] < fim:
                linhas.append("[%s] %s%s" % (comum.relogio(s["s"]), marca(s["s"], s["e"]), s["t"]))
        (pasta_j / ("janela-%02d.md" % (i + 1))).write_text("\n".join(linhas) + "\n", encoding="utf-8")

    def frase_em(t):
        perto = [s for s in segs if s["s"] - 4 <= t <= s["e"] + 4]
        return (perto[0]["t"] if perto else "")[:90]

    linhas = ["# %s" % info["titulo"], "", "- Canal: %s" % info["canal"], "- Link: %s" % info["link"],
              "- Duração: %s" % comum.duracao_falada(len(volume)), "- Frases transcritas: %d" % len(segs),
              "- Momentos de volume alto: %d" % len(gritos),
              "- Chat: %s" % ("%d mensagens, %d picos" % (mensagens, len(picos)) if picos or mensagens >= 200 else "sem replay"),
              "- Janelas para ler: %d (pasta janelas/)" % n, "", "## Os 25 maiores picos de volume", ""]
    for g in sorted(gritos, key=lambda x: -x["db"])[:25]:
        linhas.append("- [%s] +%.0f dB, %d s: %s" % (comum.relogio(g["s"]), g["db"], g["e"] - g["s"], frase_em(g["s"])))
    if picos:
        linhas += ["", "## Os 25 maiores picos do chat", ""]
        for c in sorted(picos, key=lambda x: -x["vezes"])[:25]:
            linhas.append("- [%s] %.1fx o normal, %d mensagens: %s" % (comum.relogio(c["s"]), c["vezes"], c["mensagens"], frase_em(c["s"] - 8)))
    (destino / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\nPronto: %s" % destino)
    print("Agora leia resumo.md e cada arquivo de janelas/, e escreva momentos.json (veja referencias/como-escolher.md).")
    gasto = sum(v for k, v in tempos.dado.items() if k in ("baixar_audio", "ouvir"))
    print("Baixar e ouvir levou %s (%.0f vezes mais rápido que assistir)" % (comum.duracao_falada(gasto), horas * 3600 / max(1.0, gasto)))


if __name__ == "__main__":
    main()
