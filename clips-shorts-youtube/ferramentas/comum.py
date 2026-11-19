"""O que as ferramentas dividem: o ambiente, o ffmpeg, o yt-dlp, o Whisper e os tempos."""
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

CASA = Path(os.environ.get("CORTES_CASA", str(Path.home() / ".cortes-de-live")))
AMBIENTE = CASA / "ambiente"
MODELOS = CASA / "modelos"
SKILL = Path(__file__).resolve().parent.parent
TAXA = 16000  # samples per second of everything we analyse
WINDOWS = os.name == "nt"
PYTHON = "python" if WINDOWS else "python3"  # the command a person types to start a tool

# Windows: the console and the files default to an old code page. Everything here reads and writes UTF-8,
# and every program started from here (the environment's Python, yt-dlp) does the same.
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
for _saida in (sys.stdout, sys.stderr):
    try:
        _saida.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def python_do_ambiente():
    return AMBIENTE / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")


def no_ambiente():
    """Run this same command inside the skill's own Python environment."""
    py = python_do_ambiente()
    if not py.exists():
        sys.exit("Falta preparar o computador. Rode: %s \"%s\"" % (PYTHON, SKILL / "ferramentas" / "preparar.py"))
    fora = Path(sys.prefix).resolve() != AMBIENTE.resolve()
    if fora or (WINDOWS and not sys.flags.utf8_mode):  # on Windows also start again in UTF-8 mode
        sys.exit(subprocess.call([str(py)] + sys.argv))


def chip_apple():
    return sys.platform == "darwin" and platform.machine() == "arm64"


def motor():
    """Which Whisper this computer uses: mlx-whisper on a Mac with an Apple chip, faster-whisper everywhere else
    (Windows, a Mac with an Intel chip, Linux). CORTES_MOTOR=faster or mlx forces one."""
    pedido = os.environ.get("CORTES_MOTOR", "")
    if pedido in ("mlx", "faster"):
        return pedido
    return "mlx" if chip_apple() else "faster"


def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ffmpeg não encontrado. Rode de novo o preparar.py.")


def ytdlp(*args, cookies="", captura=True, tempo=None):
    """Call yt-dlp from this environment. Returns the finished process."""
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--ffmpeg-location", ffmpeg()]
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    cmd += list(args)
    # YouTube needs a JavaScript runtime: the environment brings its own deno, in the folder of its Python
    amb = dict(os.environ, PATH=str(python_do_ambiente().parent) + os.pathsep + os.environ.get("PATH", ""))
    try:
        return subprocess.run(cmd, capture_output=captura, text=True, encoding="utf-8", errors="replace", timeout=tempo, env=amb)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, e.stdout or "", "tempo esgotado")


def segundos(t):
    """'1:02:03', '62:03' or 3723 -> seconds."""
    if isinstance(t, (int, float)):
        return float(t)
    partes = [float(p) for p in str(t).strip().split(":")]
    s = 0.0
    for p in partes:
        s = s * 60 + p
    return s


def relogio(s, decimos=False):
    s = max(0.0, float(s))
    h, r = divmod(int(s), 3600)
    m, seg = divmod(r, 60)
    base = "%d:%02d:%02d" % (h, m, seg)
    return base + (".%d" % int((s % 1) * 10)) if decimos else base


def duracao_falada(s):
    s = int(round(s))
    h, r = divmod(s, 3600)
    m, seg = divmod(r, 60)
    if h:
        return "%d h %02d min" % (h, m)
    if m:
        return "%d min %02d s" % (m, seg)
    return "%d s" % seg


def ler_json(p, padrao=None):
    p = Path(p)
    if not p.exists():
        return padrao
    return json.loads(p.read_text(encoding="utf-8"))


def escrever_json(p, dado):
    Path(p).write_text(json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")


class Tempos:
    """How long each step took, kept in tempos.json next to the stream."""

    def __init__(self, pasta):
        self.arquivo = Path(pasta) / "tempos.json"
        self.dado = ler_json(self.arquivo, {})
        self._t = None
        self._nome = None

    def comeca(self, nome):
        self._nome, self._t = nome, time.time()

    def termina(self):
        self.dado[self._nome] = round(time.time() - self._t, 1)
        escrever_json(self.arquivo, self.dado)
        return self.dado[self._nome]


def audio_em_blocos(arquivo, inicio=None, duracao=None, bloco=TAXA * 30):
    """Decode any audio or video file to 16 kHz mono and yield it in pieces (numpy int16)."""
    import numpy as np
    cmd = [ffmpeg(), "-v", "error", "-nostdin"]
    if inicio is not None:
        cmd += ["-ss", "%.3f" % max(0.0, inicio)]
    cmd += ["-i", str(arquivo)]
    if duracao is not None:
        cmd += ["-t", "%.3f" % duracao]
    cmd += ["-vn", "-ac", "1", "-ar", str(TAXA), "-f", "s16le", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            dado = p.stdout.read(bloco * 2)
            if not dado:
                break
            yield np.frombuffer(dado[: len(dado) // 2 * 2], dtype=np.int16)
    finally:
        p.stdout.close()
        p.wait()


def audio(arquivo, inicio=None, duracao=None):
    import numpy as np
    partes = list(audio_em_blocos(arquivo, inicio, duracao))
    return np.concatenate(partes) if partes else np.zeros(0, dtype=np.int16)


_MOTOR = {}


def modelo_padrao():
    return "large-v3-turbo" if motor() == "mlx" else "small"


def transcrever(amostras, lingua=None, palavras=False, modelo=None):
    """Whisper on this computer. amostras: numpy int16 at 16 kHz.
    Returns (segments, language); a segment is {"s", "e", "t"} plus "p": [{"w", "s", "e"}] when palavras is on."""
    import numpy as np
    som = amostras.astype(np.float32) / 32768.0
    modelo = modelo or modelo_padrao()
    try:
        if motor() != "mlx":
            raise ImportError("this computer uses faster-whisper")
        import mlx_whisper
        repo = modelo if "/" in modelo else "mlx-community/whisper-" + modelo
        r = mlx_whisper.transcribe(som, path_or_hf_repo=repo, language=lingua, word_timestamps=palavras,
                                   condition_on_previous_text=False, verbose=None)
        segs = []
        for s in r["segments"]:
            item = {"s": float(s["start"]), "e": float(s["end"]), "t": s["text"].strip()}
            if palavras:
                item["p"] = [{"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])} for w in s.get("words", [])]
            segs.append(item)
        return segs, r.get("language") or lingua
    except ImportError:
        pass
    from faster_whisper import WhisperModel
    if modelo not in _MOTOR:
        # on the processor, always: a video card only works here with extra libraries that most computers do not have
        _MOTOR[modelo] = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=max(4, (os.cpu_count() or 8) // 2))
    achados, info = _MOTOR[modelo].transcribe(som, language=lingua, word_timestamps=palavras,
                                              condition_on_previous_text=False, vad_filter=True)
    segs = []
    for s in achados:
        item = {"s": float(s.start), "e": float(s.end), "t": s.text.strip()}
        if palavras:
            item["p"] = [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)} for w in (s.words or [])]
        segs.append(item)
    return segs, info.language
