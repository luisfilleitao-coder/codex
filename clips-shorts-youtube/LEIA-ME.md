# Cortes de live: a live inteira vira cortes prontos, feitos pelo Claude

Você manda o link de uma live e o Claude te devolve os melhores momentos já cortados na vertical, com a câmera do streamer em cima, o jogo embaixo, o título e a legenda palavra por palavra:

1. **Baixa só o áudio.** Uma live de quatro horas vira umas centenas de MB.
2. **Ouve a live inteira no seu computador:** transcreve tudo, marca onde o streamer ficou bem mais alto que o normal e onde o chat disparou.
3. **Escolhe os momentos:** o Claude lê a transcrição em janelas de 12 minutos, dá nota para cada momento e joga fora o que precisa de contexto.
4. **Corta:** baixa só os trechos escolhidos, acha a câmera do streamer sozinho e monta o corte, com o texto do post e as hashtags.

## O que você precisa

- **O Claude com acesso às pastas do seu computador:** o Claude Code, ou a aba Code do app do Claude.
- **Um Mac ou um PC com Windows.**
- **Espaço:** cerca de 3 GB para as ferramentas e o modelo que transcreve.

O skill instala o resto sozinho, numa pasta só dele (`.cortes-de-live`, na sua pasta de usuário).

## Como instalar

**No Claude Code:** copie a pasta `cortes-de-live` para a pasta `.claude/skills` da sua pasta de usuário (no Windows, `C:\Users\<seu nome>\.claude\skills`). Abra uma sessão numa pasta vazia, só para os cortes, e peça:

> Prepara o cortes de live.

**No app do Claude:** em Configurações, Capacidades, envie o arquivo `.zip`. Use a aba Code, com a pasta dos cortes aberta.

## Como usar

Com o link:

> Corta esta live: <link>

Sem o link:

> Acha as maiores lives de GTA 6 de hoje e corta as três primeiras.

Funciona com lives do YouTube, da Twitch e do Kick, e com podcast e vídeo longo.

## Pôr a sua voz no corte

Grave a sua fala no celular e peça:

> Põe esse áudio abrindo o corte 1.

O corte sai com a sua voz antes (ou depois) e a sua fala legendada em outra cor.

## O que sai

Para cada corte, na pasta `lives/<id da live>/cortes/`:

- `01-titulo.mp4`: o corte, 1080 por 1920.
- `01-titulo.txt`: o título, a legenda do post, as hashtags e o link da live no segundo certo.
- `01-titulo-conferir.jpg`: seis quadros do corte.

## O que vem na pasta

- `SKILL.md`: o passo a passo que o Claude segue.
- `ferramentas/`: `preparar.py` (instala tudo), `achar.py` (acha as maiores lives de um assunto), `ouvir.py` (o áudio, a transcrição, o volume e o chat), `conferir.py` (acerta e confere os momentos), `cortar.py` (monta os cortes).
- `referencias/como-escolher.md`: como o Claude dá nota para um momento.

## Mudar o visual

Peça ao Claude: "muda a cor do destaque para verde e a legenda para duas palavras por vez". Ele escreve um `estilo.json` na pasta da live e monta de novo.
