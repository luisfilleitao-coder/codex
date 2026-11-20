# Motion 3D — como funciona uma máquina de espresso (15 s)

- `index.html` — animação em three.js (formato 16:9 por padrão).
- `index.html?format=short` — mesma animação em 9:16, para Shorts/Reels.
- `espresso-15s.mp4` — render 16:9 (1920×1080).
- `espresso-15s-short.mp4` — render 9:16 (1080×1920).

Cada versão de vídeo é entregue em **dois MP4**: um 16:9 e um 9:16 (short).

## Como renderizar

Os quadros são capturados com Playwright (`?t=<segundos>` posiciona a animação
exatamente no instante desejado) e montados com ffmpeg a 30 fps.

```bash
# 16:9 → espresso-15s.mp4 (viewport 1920×1080, frames em frames/)
# 9:16 → espresso-15s-short.mp4 (viewport 1080×1920, ?format=short, frames em frames_short/)
ffmpeg -framerate 30 -i frames_short/f_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 \
  -movflags +faststart espresso-15s-short.mp4
```
