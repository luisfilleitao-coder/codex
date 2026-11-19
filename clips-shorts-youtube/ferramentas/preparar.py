#!/usr/bin/env python3
"""Prepara o computador uma vez: um ambiente Python só do skill, com tudo que as outras ferramentas usam.

Uso (no Windows o comando é python no lugar de python3):
  python3 preparar.py            instala o que falta e testa
  python3 preparar.py --conferir só diz o que está instalado

Funciona no Mac e no Windows. Instala dentro de ~/.cortes-de-live, na sua pasta de usuário (nada fora dessa
pasta): yt-dlp (baixa a live), OpenCV, NumPy e Pillow (acham a câmera e montam o corte), um ffmpeg se o
computador não tiver, e o Whisper, que ouve a live no seu computador: mlx-whisper no Mac com chip Apple,
faster-whisper no Windows e no Mac com chip Intel. Baixa também o modelo que acha rostos e a fonte das
legendas. Na primeira vez o Whisper baixa o modelo dele (cerca de 1,6 GB no Mac com chip Apple, cerca de
500 MB nos outros).
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

ROSTO = ("face_detection_yunet_2023mar.onnx", [
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
])
FONTE = ("Anton-Regular.ttf", [
    "https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf",
])


TEXTO = dict(text=True, encoding="utf-8", errors="replace")  # how the answer of every program started here is read
INSTALE = ("\nInstale o Python 3.12 e rode de novo. No Windows: winget install -e --id Python.Python.3.12 (ou python.org). "
           "No Mac: brew install python@3.12 (ou python.org).")


def baixar(nome, links, minimo):
    destino = comum.MODELOS / nome
    if destino.exists() and destino.stat().st_size >= minimo:
        return True
    for link in links:
        try:
            req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
            dado = urllib.request.urlopen(req, timeout=60).read()
            if len(dado) >= minimo:
                destino.write_bytes(dado)
                return True
        except Exception:
            continue
    return False


def versao(py):
    r = subprocess.run([str(py), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], capture_output=True, **TEXTO)
    try:
        a, b = r.stdout.strip().split(".")
        return int(a), int(b)
    except Exception:
        return (0, 0)


def serve(v):
    return (3, 10) <= v <= (3, 13)


def criar_ambiente():
    """The environment needs Python 3.10 to 3.13 (the current yt-dlp and the Whisper packages ask for it).
    Use this Python if it fits, else another one already on the computer, else fetch one into the skill's own folder."""
    if serve(sys.version_info[:2]):
        venv.create(str(comum.AMBIENTE), with_pip=True)
        return "o Python %d.%d deste computador" % sys.version_info[:2]
    for nome in ("python3.12", "python3.13", "python3.11", "python3.10"):
        achados = [shutil.which(nome)] + [str(Path(d) / nome) for d in ("/opt/homebrew/bin", "/usr/local/bin")]
        for exe in achados:
            if exe and Path(exe).exists() and serve(versao(exe)):
                subprocess.run([exe, "-m", "venv", str(comum.AMBIENTE)], check=True)
                return exe
    if comum.WINDOWS and shutil.which("py"):  # the Windows launcher knows every Python installed from python.org
        for v in ("3.12", "3.13", "3.11", "3.10"):
            r = subprocess.run(["py", "-" + v, "-c", "import sys; print(sys.executable)"], capture_output=True, **TEXTO)
            exe = r.stdout.strip()
            if r.returncode == 0 and exe and Path(exe).exists() and serve(versao(exe)):
                subprocess.run([exe, "-m", "venv", str(comum.AMBIENTE)], check=True)
                return exe
    partida = comum.CASA / "partida"
    if not partida.exists():
        venv.create(str(partida), with_pip=True)
    pasta_bin = partida / ("Scripts" if os.name == "nt" else "bin")
    py = pasta_bin / ("python.exe" if os.name == "nt" else "python3")
    r = subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip", "uv"], capture_output=True, **TEXTO)
    if r.returncode:
        sys.exit("Não consegui instalar o uv, que busca um Python novo:\n" + r.stderr[-1200:] + INSTALE)
    amb = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(comum.CASA / "python"))
    r = subprocess.run([str(pasta_bin / ("uv.exe" if os.name == "nt" else "uv")), "venv", "--seed", "--python", "3.12", str(comum.AMBIENTE)],
                       capture_output=True, env=amb, **TEXTO)
    if r.returncode:
        sys.exit("Não consegui buscar o Python 3.12:\n" + r.stderr[-1200:] + INSTALE)
    return "um Python 3.12 só do skill (este computador tem o %d.%d)" % sys.version_info[:2]


def pip(*pacotes):
    r = subprocess.run([str(comum.python_do_ambiente()), "-m", "pip", "install", "-q", "--upgrade"] + list(pacotes),
                       capture_output=True, **TEXTO)
    if r.returncode:
        sys.exit("Não consegui instalar %s:\n%s" % (" ".join(pacotes), r.stderr[-1500:]))


def tem(modulo):
    return subprocess.run([str(comum.python_do_ambiente()), "-c", "import " + modulo], capture_output=True).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conferir", action="store_true")
    a = ap.parse_args()
    if sys.version_info < (3, 8):
        sys.exit("Precisa do Python 3.8 ou mais novo para começar. Este é o %d.%d." % sys.version_info[:2])
    whisper = "mlx_whisper" if comum.motor() == "mlx" else "faster_whisper"
    if a.conferir:
        ok = comum.python_do_ambiente().exists()
        print("ambiente:", "ok" if ok else "falta")
        for m in ("yt_dlp", "cv2", "numpy", "PIL", whisper):
            print("  %-15s %s" % (m, "ok" if ok and tem(m) else "falta"))
        return
    t0 = time.time()
    comum.CASA.mkdir(parents=True, exist_ok=True)
    comum.MODELOS.mkdir(parents=True, exist_ok=True)
    if comum.python_do_ambiente().exists() and not serve(versao(comum.python_do_ambiente())):
        shutil.rmtree(str(comum.AMBIENTE))  # an environment made with a Python that is too old or too new
    if not comum.python_do_ambiente().exists():
        print("1/5 criando o ambiente em", comum.AMBIENTE)
        print("    com", criar_ambiente())
    else:
        print("1/5 ambiente já existe")
    print("2/5 instalando yt-dlp, OpenCV, NumPy e Pillow")
    pip("pip")
    pip("yt-dlp[default,curl-cffi]", "deno", "opencv-python-headless", "numpy", "pillow")  # curl-cffi: Kick only answers a browser
    if not shutil.which("ffmpeg"):
        print("    ffmpeg não está no computador: instalando um só para o skill")
        pip("imageio-ffmpeg")
    print("3/5 instalando o Whisper (%s)" % whisper.replace("_", "-"))
    pip(whisper.replace("_", "-"))
    print("4/5 baixando o modelo de rostos e a fonte das legendas")
    if not baixar(ROSTO[0], ROSTO[1], 100000):
        print("    não baixei o modelo de rostos: o corte usa o detector simples do OpenCV")
    if not baixar(FONTE[0], FONTE[1], 20000):
        print("    não baixei a fonte: as legendas usam uma fonte do sistema")
    print("5/5 testando o Whisper (na primeira vez ele baixa o modelo)")
    teste = ("import sys; sys.path.insert(0, %r); import comum, numpy as np; "
             "segs, l = comum.transcrever(np.zeros(comum.TAXA * 2, dtype=np.int16), lingua='pt'); print('whisper ok')"
             % str(Path(__file__).resolve().parent))
    r = subprocess.run([str(comum.python_do_ambiente()), "-c", teste], capture_output=True, **TEXTO)
    if "whisper ok" not in r.stdout:
        sys.exit("O Whisper não rodou:\n" + r.stderr[-1500:] + (
            "\nNo Windows, instale o Microsoft Visual C++ Redistributable (https://aka.ms/vs/17/release/vc_redist.x64.exe) e rode de novo."
            if comum.WINDOWS else ""))
    print("PRONTO em %s. Modelo: %s." % (comum.duracao_falada(time.time() - t0), comum.modelo_padrao()))


if __name__ == "__main__":
    main()
