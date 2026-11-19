#!/usr/bin/env python3
"""Faz os cortes prontos para postar: vertical, a câmera do streamer em cima, o jogo embaixo, o título e a legenda palavra por palavra.

Uso:
  python3 cortar.py <pasta da live> [--so 2] [--cookies chrome] [--camera x,y,l,a] [--modo facecam|cheia|sem]

Lê <pasta da live>/momentos-conferidos.json (do conferir.py) e, para cada momento marcado:
  1. Baixa só aquele trecho da live, não a live inteira.
  2. Acerta o trecho com o áudio da live, para o corte começar na palavra certa.
  3. Acha a câmera do streamer sozinho (o rosto que fica parado no mesmo lugar) e acompanha quando ele troca a tela no
     meio do momento.
  4. Transcreve o trecho palavra por palavra para a legenda.
  5. Monta o vídeo 1080x1920 e acerta o volume.

Escreve em <pasta da live>/cortes/:
  NN-titulo.mp4            o corte
  NN-titulo.txt            o título, a legenda do post, as hashtags e de onde veio
  NN-titulo-conferir.jpg   seis quadros do corte, para olhar antes de postar
  cortes.json              a lista

O modo comentário: grave a sua fala e salve em <pasta da live>/comentarios/ como NN-abre.m4a (toca antes do
corte) e NN-fecha.m4a (toca depois), com NN o número do momento. O corte sai como NN-titulo-comentado.mp4, com a sua
voz por cima da primeira e da última imagem do corte, paradas e escurecidas, e a sua fala legendada em outra cor.

O visual muda em <pasta da live>/estilo.json (as chaves estão em ESTILO, aqui embaixo).
Se a câmera sair errada, olhe trechos/NN-quadro.jpg e passe --camera x,y,largura,altura.
"""
import argparse
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

comum.no_ambiente()
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass

L, A, FPS = 1080, 1920, 30
MARGEM = 8  # seconds downloaded before and after each moment

ESTILO = {
    "cor_destaque": "#FFD60A",       # the word being said, the title box, the progress bar
    "cor_comentario": "#4ADE80",     # the word being said in the person's own comment
    "cor_legenda": "#FFFFFF",
    "cor_contorno": "#000000",
    "cor_titulo_texto": "#111111",
    "tamanho_legenda": 92,
    "tamanho_titulo": 62,
    "palavras_por_legenda": 3,
    "letras_por_legenda": 18,
    "altura_legenda": 0.68,          # 0 = top of the video, 1 = bottom
    "titulo": True,
    "barra": True,
    "maiusculas": True,
    "volume": -14,                   # LUFS
}

FONTES = [str(comum.MODELOS / "Anton-Regular.ttf"), "/System/Library/Fonts/Supplemental/Impact.ttf",
          "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def fonte(tamanho):
    for f in FONTES:
        if Path(f).exists():
            return ImageFont.truetype(f, tamanho)
    return ImageFont.load_default()


def cor(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def para_cv(p):
    """The path as OpenCV can open it. On Windows OpenCV does not open a path with accents (C:\\Users\\João\\...),
    so it gets the same file counted from the current folder, which has none."""
    p = str(p)
    if comum.WINDOWS and not p.isascii():
        try:
            curto = os.path.relpath(p)
            if curto.isascii():
                return curto
        except ValueError:
            pass
    return p


def gravar_jpg(caminho, imagem, qualidade):
    """cv2.imwrite fails without a word on a Windows path with accents: encode here, write with Python."""
    ok, dado = cv2.imencode(".jpg", imagem, [cv2.IMWRITE_JPEG_QUALITY, qualidade])
    if ok:
        Path(caminho).write_bytes(dado.tobytes())


def nome_de_arquivo(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:50] or "corte"


# ---------- the piece of the stream ----------

def baixar_trecho(info, pasta, n, ini, fim, cookies):
    destino = pasta / ("%02d.mp4" % n)
    if destino.exists() and destino.stat().st_size > 100000:
        return destino
    a, b = max(0.0, ini - MARGEM), fim + MARGEM
    r = comum.ytdlp("-f", "bv*[height<=1080][fps<=30]+ba/bv*[height<=1080]+ba/b[height<=1080]/b",
                    "--download-sections", "*%s-%s" % (comum.relogio(a), comum.relogio(b + 1)),
                    "--force-keyframes-at-cuts", "--merge-output-format", "mp4",
                    "-o", str(pasta / ("%02d.%%(ext)s" % n)), info["link"], cookies=cookies)
    if r.returncode or not destino.exists():
        sys.exit("Não consegui baixar o trecho %d:\n%s" % (n, (r.stderr or "")[-1200:]))
    return destino


def envelope(x):
    x = np.abs(x.astype(np.float32))
    n = len(x) // 160 * 160
    e = x[:n].reshape(-1, 160).mean(axis=1)  # 100 values per second
    return (e - e.mean()) / (e.std() + 1e-9)


def alinhar(trecho, audio_da_live, pedido):
    """Where in the stream (seconds) the downloaded piece really starts, found by matching its sound to the stream's sound."""
    som = comum.audio(trecho)
    if len(som) < comum.TAXA * 5:
        return pedido, som, 0.0
    folga = 25.0
    base = max(0.0, pedido - folga)
    regiao = comum.audio(audio_da_live, inicio=base, duracao=len(som) / comum.TAXA + 2 * folga)
    x, y = envelope(som), envelope(regiao)
    if len(y) <= len(x):
        return pedido, som, 0.0
    c = np.correlate(y, x, mode="valid") / len(x)
    k = int(np.argmax(c))
    certeza = float((c[k] - c.mean()) / (c.std() + 1e-9))
    if certeza < 6:
        return pedido, som, certeza
    return base + k / 100.0, som, certeza


# ---------- the streamer's camera ----------

class Rostos:
    def __init__(self):
        modelo = comum.MODELOS / "face_detection_yunet_2023mar.onnx"
        self.yunet = self.haar = None
        if modelo.exists() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self.yunet = cv2.FaceDetectorYN.create(str(modelo), "", (320, 320), 0.7, 0.3, 50)
            except Exception:
                self.yunet = None
            if self.yunet is None:  # a path OpenCV cannot open (accents, on Windows): hand it the file's bytes
                try:
                    dado = np.frombuffer(modelo.read_bytes(), np.uint8)
                    self.yunet = cv2.FaceDetectorYN.create("onnx", dado, np.zeros(0, np.uint8), (320, 320), 0.7, 0.3, 50)
                except Exception:
                    self.yunet = None
        if self.yunet is None:
            try:
                haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                self.haar = None if haar.empty() else haar
            except Exception:
                self.haar = None

    def em(self, quadro):
        h, w = quadro.shape[:2]
        if self.yunet is not None:
            self.yunet.setInputSize((w, h))
            _, achados = self.yunet.detect(quadro)
            return [tuple(float(v) for v in f[:4]) for f in (achados if achados is not None else [])]
        if self.haar is None:
            return []  # no face finder on this computer: the cut goes out with the video in the middle
        cinza = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
        return [tuple(float(v) for v in f) for f in self.haar.detectMultiScale(cinza, 1.1, 5, minSize=(40, 40))]


def amostrar(trecho, t0, dur, rostos, cada=0.5):
    """Looks at the cut twice a second. Returns the faces seen at each look and the pictures themselves (all of them, at half size
    when there are many, so a long cut does not fill the memory; faces are searched on the full picture)."""
    cap = cv2.VideoCapture(para_cv(trecho))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    alvos = [int(round((t0 + i * cada) * fps)) for i in range(int(dur / cada) + 1)]
    quadros, achados, i = [], [], 0
    while alvos:
        ok = cap.grab()
        if not ok:
            break
        if i == alvos[0]:
            ok, q = cap.retrieve()
            if ok:
                achados.append(rostos.em(q))
                quadros.append(q)
            alvos.pop(0)
        i += 1
    cap.release()
    return quadros, achados


def rosto_parado(quadros, achados):
    """The streamer's camera: a face that stays in the same place in most pictures and is alive.
    A face painted on the game's artwork or on an overlay also stays in place, but its pixels never change. Returns (x, y, w, h) or None."""
    if not quadros:
        return None
    W = quadros[0].shape[1]
    grupos = []
    for qi in range(len(quadros)):
        vistos = set()
        for (x, y, w, h) in achados[qi]:
            cx, cy = x + w / 2, y + h / 2
            for gi, g in enumerate(grupos):
                if abs(cx - g["cx"]) < 0.06 * W and abs(cy - g["cy"]) < 0.06 * W and 0.5 < w / g["w"] < 2.0:
                    if gi not in vistos:
                        g["caixas"].append((x, y, w, h))
                        g["onde"].append(qi)
                        g["cx"], g["cy"], g["w"] = np.median([[b[0] + b[2] / 2, b[1] + b[3] / 2, b[2]] for b in g["caixas"]], axis=0)
                        vistos.add(gi)
                    break
            else:
                grupos.append({"cx": cx, "cy": cy, "w": w, "caixas": [(x, y, w, h)], "onde": [qi]})
    grupos = [g for g in grupos if len(g["caixas"]) >= max(3, 0.35 * len(quadros))]
    if not grupos:
        return None
    H = quadros[0].shape[0]
    for g in grupos:
        x, y, w, h = [int(v) for v in np.median(np.array(g["caixas"]), axis=0)]
        x, y = max(0, x), max(0, y)
        w, h = max(8, min(w, W - x)), max(8, min(h, H - y))
        minis = [cv2.resize(cv2.cvtColor(quadros[i][y:y + h, x:x + w], cv2.COLOR_BGR2GRAY), (48, 48), interpolation=cv2.INTER_AREA).astype(np.float32)
                 for i in range(len(quadros))]
        # how much the picture inside the box changes from one second to the next (grey levels)
        g["vida"] = float(np.median([np.abs(minis[i + 1] - minis[i]).mean() for i in range(len(minis) - 1)])) if len(minis) > 1 else 0.0
    vivos = [g for g in grupos if g["vida"] >= 1.5]
    melhor = max(vivos or grupos, key=lambda g: (len(g["caixas"]), g["w"]))
    return tuple(float(v) for v in np.median(np.array(melhor["caixas"]), axis=0))


def linhas_paradas(quadros):
    """Edges that are in the same place in every frame: the borders of what the streamer put over the game."""
    soma_v = soma_h = None
    for q in quadros:
        c = cv2.cvtColor(q, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gv, gh = np.abs(cv2.Sobel(c, cv2.CV_32F, 1, 0, ksize=3)), np.abs(cv2.Sobel(c, cv2.CV_32F, 0, 1, ksize=3))
        soma_v = gv if soma_v is None else np.minimum(soma_v, gv)  # the minimum over time keeps only what never moves
        soma_h = gh if soma_h is None else np.minimum(soma_h, gh)
    return soma_v, soma_h


def caixa_da_camera(quadros, rosto):
    """From the face to the whole camera box: first a guess from the size of the face, then snapped to borders that never move."""
    H, W = quadros[0].shape[:2]
    fx, fy, fw, fh = rosto
    cx, cy = fx + fw / 2, fy + fh / 2
    # the guess
    esq, dir_ = cx - 1.7 * fw, cx + 1.7 * fw
    topo, base = cy - 1.0 * fh, cy + 1.5 * fh
    achou = {}
    if len(quadros) >= 4:
        bv, bh = linhas_paradas(quadros)
        y0, y1 = int(max(0, cy - 0.8 * fh)), int(min(H, cy + 0.8 * fh))
        x0, x1 = int(max(0, cx - 0.8 * fw)), int(min(W, cx + 0.8 * fw))
        col = bv[y0:y1].mean(axis=0)   # one number per column: how much of a standing line it holds
        lin = bh[:, x0:x1].mean(axis=1)

        def procura(serie, de, ate, piso):
            de, ate = int(max(0, min(de, ate))), int(min(len(serie), max(de, ate)))
            if ate - de < 4:
                return None
            k = de + int(np.argmax(serie[de:ate]))
            return k if serie[k] >= piso else None

        piso_c, piso_l = max(12.0, 6 * float(np.median(col))), max(12.0, 6 * float(np.median(lin)))
        achou["esq"] = procura(col, cx - 4.0 * fw, cx - 0.8 * fw, piso_c)
        achou["dir"] = procura(col, cx + 0.8 * fw, cx + 4.0 * fw, piso_c)
        achou["topo"] = procura(lin, cy - 3.0 * fh, cy - 0.7 * fh, piso_l)
        achou["base"] = procura(lin, cy + 0.9 * fh, cy + 4.5 * fh, piso_l)
        # a camera that touches the edge of the screen has no line there: the edge is the border
        if achou["esq"] is None and cx - 2.4 * fw <= 0:
            achou["esq"] = 0
        if achou["dir"] is None and cx + 2.4 * fw >= W:
            achou["dir"] = W
        if achou["topo"] is None and cy - 1.6 * fh <= 0:
            achou["topo"] = 0
        if achou["base"] is None and cy + 2.6 * fh >= H:
            achou["base"] = H
        if achou["esq"] is not None and achou["dir"] is not None and 2.0 * fw <= achou["dir"] - achou["esq"] <= 8 * fw:
            esq, dir_ = achou["esq"] + 2, achou["dir"] - 2
        if achou["topo"] is not None and achou["base"] is not None and 1.6 * fh <= achou["base"] - achou["topo"] <= 7 * fh:
            topo, base = achou["topo"] + 2, achou["base"] - 2
    esq, dir_, topo, base = max(0.0, esq), min(float(W), dir_), max(0.0, topo), min(float(H), base)
    return [int(esq), int(topo), int(dir_ - esq), int(base - topo)]


GRANDE = 0.16  # a face this wide (share of the screen's width) means the camera is the whole screen


def planos(quadros, achados, forcado_modo, forcada_camera, cada=0.5):
    """How the cut is framed, stretch by stretch, because streamers change the screen in the middle of a moment.
    Each stretch is 'facecam' (camera on top, game below), 'cheia' (the camera is the whole screen) or 'sem' (no face).
    Returns [{"de": seconds, "entre": seconds of the look before, "pl": {...}}], the first one starting at 0."""
    H, W = quadros[0].shape[:2]
    if forcada_camera:
        return [{"de": 0.0, "entre": 0.0, "pl": {"modo": "facecam", "camera": forcada_camera, "rosto": None}}]
    if forcado_modo == "sem":
        return [{"de": 0.0, "entre": 0.0, "pl": {"modo": "sem", "camera": None, "rosto": None}}]
    n = len(quadros)
    grandes = []
    for fs in achados:
        g = [f for f in fs if f[2] >= GRANDE * W]
        grandes.append(max(g, key=lambda f: f[2]) if g else None)
    marca = ["cheia" if g is not None else "cam" for g in grandes]
    if forcado_modo == "cheia":
        marca = ["cheia"] * n
    if forcado_modo == "facecam":
        marca = ["cam"] * n
    # a single look that disagrees with both neighbours is a wrong detection, not a change of screen
    for _ in range(2):
        for i in range(n):
            antes, depois = marca[i - 1] if i else None, marca[i + 1] if i + 1 < n else None
            if marca[i] != antes and marca[i] != depois and (antes or depois):
                marca[i] = antes or depois
    # the small camera, measured only on the looks where the screen is the game
    idx = [i for i in range(n) if marca[i] == "cam"]
    pl_cam = {"modo": "sem", "camera": None, "rosto": None}
    if idx:
        qs = [quadros[i] for i in idx]
        pequenos = [[f for f in achados[i] if f[2] < GRANDE * W] for i in idx]
        rosto = rosto_parado(qs, pequenos)
        if rosto is not None:
            caixa = caixa_da_camera(qs[::2] if len(qs) > 8 else qs, rosto)
            if rosto[2] >= 0.085 * W or caixa[2] >= 0.45 * W:
                # a stream that is only the streamer talking: the camera is the screen, there is no game to put below
                pl_cam = {"modo": "cheia", "camera": None, "rosto": [int(v) for v in rosto]}
            else:
                pl_cam = {"modo": "facecam", "camera": caixa, "rosto": [int(v) for v in rosto]}
    trechos, i = [], 0
    while i < n:
        j = i
        while j + 1 < n and marca[j + 1] == marca[i]:
            j += 1
        if marca[i] == "cheia":
            caixas = [grandes[k] for k in range(i, j + 1) if grandes[k] is not None]
            rosto = [int(v) for v in np.median(np.array(caixas), axis=0)] if caixas else [W // 2 - 100, H // 3, 200, 240]
            pl = {"modo": "cheia", "camera": None, "rosto": rosto}
        else:
            pl = pl_cam
        trechos.append({"de": i * cada if i else 0.0, "entre": max(0.0, (i - 1) * cada), "pl": pl})
        i = j + 1
    return trechos


def recortes(pl, W, H):
    """The source rectangles and where each goes on the 1080x1920 canvas."""
    if pl["modo"] == "facecam":
        x, y, w, h = pl["camera"]
        prop = min(1.9, max(1.3, w / float(h)))
        # trim the camera box to that shape, around the face when we know it
        if w / float(h) > prop:
            nw = int(h * prop)
            centro = (pl["rosto"][0] + pl["rosto"][2] / 2) if pl["rosto"] else x + w / 2
            x = int(min(max(x, centro - nw / 2), x + w - nw))
            w = nw
        else:
            nh = int(w / prop)
            centro = (pl["rosto"][1] + pl["rosto"][3] * 0.55) if pl["rosto"] else y + h / 2
            y = int(min(max(y, centro - nh * 0.45), y + h - nh))
            h = nh
        alt_topo = int(round(L / prop / 2) * 2)
        alt_jogo = A - alt_topo
        jw = int(H * L / float(alt_jogo))
        jx = (W - jw) // 2
        cam_cx = x + w / 2
        if x < jx + jw and x + w > jx:  # the camera sits inside the middle of the game: slide the game crop away from it
            jx = min(W - jw, x + w) if cam_cx < W / 2 else max(0, x - jw)
        return {"topo": (x, y, w, h, 0, 0, L, alt_topo), "jogo": (jx, 0, jw, H, 0, alt_topo, L, alt_jogo), "emenda": alt_topo}
    if pl["modo"] == "cheia":
        cw = int(H * L / float(A))
        cx = pl["rosto"][0] + pl["rosto"][2] / 2
        x = int(min(max(0, cx - cw / 2), W - cw))
        return {"jogo": (x, 0, cw, H, 0, 0, L, A), "emenda": int(A * 0.16)}
    alt = int(L * H / float(W) / 2) * 2
    return {"fundo": True, "jogo": (0, 0, W, H, 0, (A - alt) // 2, L, alt), "emenda": (A - alt) // 2 - 70}


# ---------- the words on screen ----------

def limpar(p):
    return re.sub(r"[\"“”]", "", p).strip()


def grupos_de_legenda(palavras, estilo):
    grupos, atual = [], []
    for p in palavras:
        w = limpar(p["w"])
        if not w:
            continue
        txt = w.upper() if estilo["maiusculas"] else w
        item = {"w": txt.rstrip(",.;:"), "s": p["s"], "e": p["e"]}
        if not item["w"]:
            continue
        letras = sum(len(x["w"]) for x in atual) + len(item["w"])
        if atual and (len(atual) >= estilo["palavras_por_legenda"] or letras > estilo["letras_por_legenda"]
                      or p["s"] - atual[-1]["e"] > 0.5 or atual[-1].get("fim_de_frase")):
            grupos.append(atual)
            atual = []
        item["fim_de_frase"] = bool(re.search(r"[.!?]$", w))
        atual.append(item)
    if atual:
        grupos.append(atual)
    for i, g in enumerate(grupos):
        proximo = grupos[i + 1][0]["s"] if i + 1 < len(grupos) else g[-1]["e"] + 0.6
        g[-1]["mostra_ate"] = min(proximo, g[-1]["e"] + 0.6)
    return grupos


def imagem_da_legenda(grupo, ativo, estilo):
    tam = estilo["tamanho_legenda"]
    while True:
        f = fonte(tam)
        espaco = f.getlength(" ")
        larguras = [f.getlength(x["w"]) for x in grupo]
        total = sum(larguras) + espaco * (len(grupo) - 1)
        if total <= L - 120 or tam <= 40:
            break
        tam -= 6
    borda = max(6, tam // 10)
    img = Image.new("RGBA", (int(total) + 4 * borda, int(tam * 1.5) + 4 * borda), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 2 * borda
    for i, pal in enumerate(grupo):
        d.text((x, 2 * borda), pal["w"], font=f, fill=cor(estilo["cor_destaque"] if i == ativo else estilo["cor_legenda"]) + (255,),
               stroke_width=borda, stroke_fill=cor(estilo["cor_contorno"]) + (255,))
        x += larguras[i] + espaco
    return np.array(img)


def imagem_do_titulo(texto, estilo):
    texto = texto.upper() if estilo["maiusculas"] else texto
    tam = estilo["tamanho_titulo"]
    while True:
        f = fonte(tam)
        linhas, atual = [], ""
        for p in texto.split():
            tenta = (atual + " " + p).strip()
            if f.getlength(tenta) <= L - 200 or not atual:
                atual = tenta
            else:
                linhas.append(atual)
                atual = p
        linhas.append(atual)
        if len(linhas) <= 2 or tam <= 40:
            break
        tam -= 4
    alt_linha = int(tam * 1.28)
    larg = int(max(f.getlength(x) for x in linhas)) + 72
    alt = alt_linha * len(linhas) + 40
    img = Image.new("RGBA", (larg + 16, alt + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 12, larg + 12, alt + 12), radius=22, fill=(0, 0, 0, 110))        # a soft shadow
    d.rounded_rectangle((4, 4, larg + 4, alt + 4), radius=22, fill=cor(estilo["cor_destaque"]) + (255,))
    for i, linha in enumerate(linhas):
        d.text((4 + (larg - f.getlength(linha)) / 2, 4 + 14 + i * alt_linha), linha, font=f, fill=cor(estilo["cor_titulo_texto"]) + (255,))
    return np.array(img)


def colar(tela, rgba, cx, cy):
    """Paste an RGBA picture centred on (cx, cy) of the BGR canvas."""
    h, w = rgba.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    x1, y1 = max(0, x0), max(0, y0)
    x2, y2 = min(tela.shape[1], x0 + w), min(tela.shape[0], y0 + h)
    if x2 <= x1 or y2 <= y1:
        return
    pedaco = rgba[y1 - y0:y2 - y0, x1 - x0:x2 - x0]
    alfa = pedaco[:, :, 3:4].astype(np.float32) / 255.0
    tela[y1:y2, x1:x2] = (tela[y1:y2, x1:x2] * (1 - alfa) + pedaco[:, :, 2::-1] * alfa).astype(np.uint8)


# ---------- the clip ----------

def codificador():
    r = subprocess.run([comum.ffmpeg(), "-hide_banner", "-encoders"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    if "libx264" in r:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19"]
    if "h264_videotoolbox" in r:
        return ["-c:v", "h264_videotoolbox", "-b:v", "9M"]
    return ["-c:v", "mpeg4", "-q:v", "3"]


def montar(trecho, t0, dur, pls, grupos, titulo, estilo, saida, folha, coment=None):
    """coment: {"abre": {"arquivo", "dur", "grupos"}, "fecha": {...}}: the person's own voice before and after the cut,
    over the first and the last picture of the cut, held still and darkened."""
    coment = coment or {}
    cap = cv2.VideoCapture(para_cv(trecho))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    rcs = [recortes(s["pl"], W, H) for s in pls]  # one framing per stretch of the cut
    n_corte = int(dur * FPS)
    n_abre = int(coment["abre"]["dur"] * FPS) if "abre" in coment else 0
    n_fecha = int(coment["fecha"]["dur"] * FPS) if "fecha" in coment else 0
    total = n_abre + n_corte + n_fecha
    # the sound: [the opening comment] + the cut + [the closing comment], each brought to the same loudness, then joined
    entradas, filtros, juntar = [], [], []
    nivel = "loudnorm=I=%d:TP=-1.5:LRA=11,aresample=48000,aformat=channel_layouts=stereo" % estilo["volume"]

    def entra(args, extra=""):
        entradas.extend(args)
        i = len(juntar) + 1
        filtros.append("[%d:a]%s%s[a%d]" % (i, extra, nivel, i))
        juntar.append("[a%d]" % i)

    if n_abre:
        entra(["-t", "%.3f" % (n_abre / float(FPS)), "-i", str(coment["abre"]["arquivo"])])
    entra(["-ss", "%.3f" % t0, "-t", "%.3f" % (n_corte / float(FPS)), "-i", str(trecho)],
          "afade=t=in:d=0.04,afade=t=out:st=%.3f:d=0.1," % max(0.0, n_corte / float(FPS) - 0.1))
    if n_fecha:
        entra(["-t", "%.3f" % (n_fecha / float(FPS)), "-i", str(coment["fecha"]["arquivo"])])
    filtro = ";".join(filtros) + ";" + "".join(juntar) + "concat=n=%d:v=0:a=1,loudnorm=I=%d:TP=-1.5:LRA=11[som]" % (len(juntar), estilo["volume"])
    cmd = [comum.ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (L, A), "-r", str(FPS), "-i", "-"] + entradas + [
           "-filter_complex", filtro, "-map", "0:v", "-map", "[som]"] + codificador() + [
           "-pix_fmt", "yuv420p", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(saida)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    img_titulo = imagem_do_titulo(titulo, estilo) if (estilo["titulo"] and titulo) else None
    cache = {}
    cor_barra = cor(estilo["cor_destaque"])[::-1]
    estilo_meu = dict(estilo, cor_destaque=estilo["cor_comentario"])  # the person's own words in another colour
    guardar = {int(total * (i + 0.5) / 6): None for i in range(6)}

    def compor(quadro, rc):
        tela = np.zeros((A, L, 3), np.uint8)
        if rc.get("fundo"):
            cw = int(H * L / float(A))
            f = cv2.resize(quadro[:, (W - cw) // 2:(W - cw) // 2 + cw], (L // 16, A // 16), interpolation=cv2.INTER_AREA)
            tela[:] = (cv2.resize(cv2.GaussianBlur(f, (0, 0), 3), (L, A), interpolation=cv2.INTER_LINEAR) * 0.45).astype(np.uint8)
        for chave in ("jogo", "topo"):
            if chave in rc:
                sx, sy, sw, sh, dx, dy, dw, dh = rc[chave]
                tela[dy:dy + dh, dx:dx + dw] = cv2.resize(quadro[sy:sy + sh, sx:sx + sw], (dw, dh),
                                                          interpolation=cv2.INTER_AREA if dw < sw else cv2.INTER_CUBIC)
        return tela

    def legenda(tela, lista, t, est, marca):
        for gi, g in enumerate(lista):
            if g[0]["s"] - 0.03 <= t < g[-1]["mostra_ate"]:
                ativo = max([i for i, p in enumerate(g) if p["s"] - 0.03 <= t] or [0])
                if (marca, gi, ativo) not in cache:
                    cache[(marca, gi, ativo)] = imagem_da_legenda(g, ativo, est)
                colar(tela, cache[(marca, gi, ativo)], L / 2, A * estilo["altura_legenda"])
                return

    lido, quadro, parado = -1, None, None
    atual, mini_antes = 0, None  # which stretch we are in; the last picture, small, to see a hard change of screen
    for k in range(total):
        kc = min(max(k - n_abre, 0), n_corte - 1)  # which picture of the cut this frame shows
        alvo = int(round(t0 * fps + kc * fps / FPS))
        while lido < alvo:
            ok, q = cap.read()
            if not ok:
                break
            quadro, lido = q, lido + 1
        if quadro is None:
            break
        if atual + 1 < len(pls) and n_abre <= k < n_abre + n_corte:
            seg, prox = kc / float(FPS), pls[atual + 1]
            mini = cv2.resize(cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY), (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32)
            virou = mini_antes is not None and seg > prox["entre"] and float(np.abs(mini - mini_antes).mean()) > 22
            mini_antes = mini
            if virou or seg >= prox["de"]:  # the screen changed here (or, with a soft change, at the look that saw it)
                atual += 1
        rc = rcs[atual]
        if n_abre <= k < n_abre + n_corte:
            tela = compor(quadro, rc)
            legenda(tela, grupos, kc / float(FPS), estilo, "c")
            parado = None
        else:
            if parado is None:
                parado = (compor(quadro, rc) * 0.4).astype(np.uint8)  # held still and darkened while the person speaks
            tela = parado.copy()
            if k < n_abre:
                legenda(tela, coment["abre"]["grupos"], k / float(FPS), estilo_meu, "a")
            else:
                legenda(tela, coment["fecha"]["grupos"], (k - n_abre - n_corte) / float(FPS), estilo_meu, "f")
        if img_titulo is not None:
            colar(tela, img_titulo, L / 2, rc["emenda"])
        if estilo["barra"]:
            tela[A - 12:A, :int(L * (k + 1) / float(total))] = cor_barra
        if k in guardar:
            guardar[k] = cv2.resize(tela, (360, 640), interpolation=cv2.INTER_AREA)
        enc.stdin.write(tela.tobytes())
    cap.release()
    enc.stdin.close()
    enc.wait()
    minis = [m for m in guardar.values() if m is not None]
    if minis:
        gravar_jpg(folha, np.hstack(minis), 88)
    return enc.returncode == 0


def juntar_numeros(palavras):
    out = []
    for w in palavras:
        if out and re.match(r"^[.,]\d", w["w"]):  # "209" + ".8": one number
            out[-1] = {"w": out[-1]["w"] + w["w"], "s": out[-1]["s"], "e": w["e"]}
        else:
            out.append(w)
    return out


def comentarios(pasta, n, lingua, estilo):
    """The person's own recordings for cut n: comentarios/NN-abre.* plays before the cut, comentarios/NN-fecha.* after it."""
    achados = {}
    for lado in ("abre", "fecha"):
        arqs = [p for p in sorted((pasta / "comentarios").glob("%02d-%s.*" % (n, lado))) if p.suffix.lower() in
                (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac", ".aiff", ".aif", ".mp4", ".mov", ".webm")]
        if not arqs:
            continue
        som = comum.audio(arqs[0])
        if len(som) < comum.TAXA * 0.5:
            continue
        segs, _ = comum.transcrever(som, lingua=lingua, palavras=True)
        palavras = juntar_numeros([w for s in segs for w in s.get("p", [])])
        achados[lado] = {"arquivo": arqs[0], "dur": len(som) / float(comum.TAXA) + 0.25, "grupos": grupos_de_legenda(palavras, estilo),
                         "texto": " ".join(w["w"] for w in palavras)}
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--so", type=int, default=0, help="só o momento com este número")
    ap.add_argument("--cookies", default="")
    ap.add_argument("--camera", default="", help="a caixa da câmera na tela da live: x,y,largura,altura")
    ap.add_argument("--modo", default="", choices=["", "facecam", "cheia", "sem"])
    a = ap.parse_args()
    pasta = Path(a.pasta)
    info = comum.ler_json(pasta / "info.json")
    dado = comum.ler_json(pasta / "momentos-conferidos.json")
    if not info or not dado:
        sys.exit("Rode antes o ouvir.py e o conferir.py nessa pasta.")
    estilo = dict(ESTILO)
    estilo.update(comum.ler_json(pasta / "estilo.json", {}))
    audio_da_live = [p for p in pasta.glob("audio.*") if p.suffix not in (".part", ".ytdl")][0]
    lingua = comum.ler_json(pasta / "transcricao.json").get("lingua")
    trechos, cortes = pasta / "trechos", pasta / "cortes"
    trechos.mkdir(exist_ok=True)
    cortes.mkdir(exist_ok=True)
    tempos = comum.Tempos(pasta)
    escolhidos = [m for m in dado["momentos"] if (m["n"] == a.so if a.so else m.get("manter"))]
    if not escolhidos:
        sys.exit("Nenhum momento marcado para o corte.")
    forcada = [int(v) for v in a.camera.split(",")] if a.camera else None
    rostos = Rostos()
    tempos.comeca("cortar")
    feitos = comum.ler_json(cortes / "cortes.json", [])

    # first pass: download, align and look for the camera in every clip, so clips of one stream can agree on it
    prontos = []
    for m in escolhidos:
        n = m["n"]
        print("momento %d: %s a %s (%s)" % (n, m["inicio"], m["fim"], m.get("titulo", "")), flush=True)
        trecho = baixar_trecho(info, trechos, n, m["inicio_s"], m["fim_s"], a.cookies)
        pedido = max(0.0, m["inicio_s"] - MARGEM)
        comeco, som, certeza = alinhar(trecho, audio_da_live, pedido)
        t0 = m["inicio_s"] - comeco
        dur = m["fim_s"] - m["inicio_s"]
        if t0 < 0 or t0 + dur > len(som) / comum.TAXA + 0.5:
            t0, certeza = min(MARGEM, m["inicio_s"]), 0.0
        print("    trecho baixado; começa em %s da live (%s)" % (comum.relogio(comeco, True), "som conferido" if certeza >= 6 else "sem conferir pelo som"))
        cada = 0.5 if dur <= 75 else 1.0
        quadros, achados = amostrar(trecho, t0, dur, rostos, cada)
        if not quadros:
            sys.exit("Não consegui ler o vídeo do trecho %d." % n)
        gravar_jpg(trechos / ("%02d-quadro.jpg" % n), quadros[len(quadros) // 2], 90)
        pls = planos(quadros, achados, a.modo, forcada, cada)
        del quadros
        prontos.append({"m": m, "trecho": trecho, "t0": t0, "dur": dur, "som": som, "pls": pls})
    com_camera = [s["pl"]["camera"] for p in prontos for s in p["pls"] if s["pl"]["modo"] == "facecam"]
    if com_camera and not forcada and not a.modo:
        comum_ = [int(v) for v in np.median(np.array(com_camera), axis=0)]
        for p in prontos:
            for s in p["pls"]:
                if s["pl"]["modo"] == "sem":  # no face found here, but the stream has a camera: use its place
                    s["pl"] = {"modo": "facecam", "camera": comum_, "rosto": None}
    comum.escrever_json(pasta / "camera.json", {str(p["m"]["n"]): [dict(s["pl"], de=s["de"]) for s in p["pls"]] for p in prontos})
    # second pass: the words and the clip
    for p in prontos:
        m, n = p["m"], p["m"]["n"]
        a0 = int(p["t0"] * comum.TAXA)
        segs, _ = comum.transcrever(p["som"][a0:a0 + int(p["dur"] * comum.TAXA)], lingua=lingua, palavras=True)
        palavras = juntar_numeros([w for s in segs for w in s.get("p", [])])
        grupos = grupos_de_legenda(palavras, estilo)
        coment = comentarios(pasta, n, lingua, estilo)
        base = "%02d-%s" % (n, nome_de_arquivo(m.get("titulo", "")))
        saida = cortes / (base + ".mp4")
        if coment:
            base += "-comentado"
            saida = cortes / (base + ".mp4")
        modos = " + ".join(dict.fromkeys(s["pl"]["modo"] for s in p["pls"]))
        ok = montar(p["trecho"], p["t0"], p["dur"], p["pls"], grupos, m.get("titulo", ""), estilo, saida, cortes / (base + "-conferir.jpg"), coment)
        if not ok:
            sys.exit("O ffmpeg não fechou o corte %d." % n)
        link = info["link"] + ("&" if "?" in info["link"] else "?") + "t=%ds" % int(m["inicio_s"])
        meu = "".join("\n\nO SEU COMENTÁRIO (%s)\n%s" % ("antes" if lado == "abre" else "depois", coment[lado]["texto"]) for lado in ("abre", "fecha") if lado in coment)
        (cortes / (base + ".txt")).write_text(
            "TÍTULO\n%s\n\nLEGENDA DO POST\n%s\n\nHASHTAGS\n%s\n\nDE ONDE VEIO\n%s, %s a %s\n%s\n\nO QUE É DITO\n%s%s\n" % (
                m.get("titulo", ""), m.get("legenda", ""), " ".join(m.get("hashtags", [])), info["canal"], m["inicio"], m["fim"], link,
                " ".join(w["w"] for w in palavras), meu), encoding="utf-8")
        total_s = p["dur"] + sum(c["dur"] for c in coment.values())
        feitos = [f for f in feitos if f["arquivo"] != saida.name]
        feitos.append({"n": n, "arquivo": saida.name, "comentario": sorted(coment), "titulo": m.get("titulo", ""), "inicio": m["inicio"], "fim": m["fim"],
                       "duracao": round(total_s, 1), "modo": modos, "nota": m.get("nota"), "link": link})
        print("    corte pronto: %s (%.0f s, %s, %d palavras%s)" % (saida.name, total_s, modos, len(palavras),
              ", com o seu comentário " + " e ".join("antes" if x == "abre" else "depois" for x in sorted(coment)) if coment else ""), flush=True)
    comum.escrever_json(cortes / "cortes.json", sorted(feitos, key=lambda f: f["n"]))
    levou = tempos.termina()
    print("\n%d cortes em %s: %s" % (len(prontos), comum.duracao_falada(levou), cortes))
    print("Abra cada NN-...-conferir.jpg e veja: a câmera inteira em cima, o jogo embaixo, o título e a legenda legíveis.")


if __name__ == "__main__":
    main()
