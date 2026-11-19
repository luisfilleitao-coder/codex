---
name: clips-shorts-youtube
description: "Transforma uma live inteira em cortes verticais prontos para postar: baixa só o áudio, transcreve no computador da pessoa, marca onde o streamer gritou e onde o chat disparou, escolhe os melhores momentos, e monta cada corte com a câmera do streamer em cima, o jogo embaixo, o título e a legenda palavra por palavra. Use quando pedirem \"corta essa live\", \"faz cortes dessa stream\", \"acha as maiores lives de GTA 6 e corta\", \"prepara o cortes de live\" ou cortes de podcast e de vídeo longo.\n"
---

# Cortes de live

## 1. Preparar (uma vez)
- `python3 $SKILL/ferramentas/preparar.py` instala tudo numa pasta só do skill.

## 2. Ouvir a live
- Só o áudio é baixado. A live é transcrita no computador.
- Saem as janelas de texto com as marcas de volume e de chat.

## 3. Escolher
- Você lê as janelas e dá nota para cada momento.
- O `conferir.py` acerta o começo e o fim e mostra a fala exata.

## 4. Cortar
- Só os trechos escolhidos são baixados.
- Sai o corte vertical, o texto do post e uma folha para conferir.

---

## Começar: o que perguntar

Se a pessoa já mandou o link, não pergunte nada: comece. Se não mandou, pergunte numa mensagem só:

1. O link da live (YouTube, Twitch ou Kick), ou o assunto para procurar as maiores lives.
2. Quantos cortes por live. Sem resposta, três.

## As regras

1. **A fala é a fonte.** O título e a legenda saem do que é dito no trecho. Nada inventado.
2. **Seja duro na nota.** Siga `referencias/como-escolher.md`. Zero candidatos numa janela é uma resposta normal.
3. **Abra as imagens você mesmo.** Cada `-conferir.jpg` é para você olhar antes de dizer que o corte está pronto.
4. **Diga os números.** Quantas horas entraram, quantos momentos apareceram, quantos ficaram, quanto tempo levou (`tempos.json`).
5. **Você entrega arquivos.** Não poste nada em nenhuma rede.
6. **O canal é de outra pessoa.** Na primeira live de um streamer, diga à pessoa para ver se o canal aceita cortes. Muitos têm regra ou programa de cortes.
7. **Cada versão com um nome novo.** Não escreva por cima de um corte que a pessoa já viu: mude o título ou a pasta.

## O passo a passo

Nos comandos, `$SKILL` é a pasta deste skill e a pasta atual é a pasta onde os cortes vão ficar.

Funciona no Mac e no Windows. No Windows:

- O comando é `python` no lugar de `python3`. Se `python` não existir, use `py`.
- Sem Python no computador: `winget install -e --id Python.Python.3.12`, abra um terminal novo e siga.
- Caminhos sempre entre aspas: `python "$SKILL/ferramentas/preparar.py"`.

### 1. Preparar

`python3 $SKILL/ferramentas/preparar.py`

Cria a pasta `.cortes-de-live` na pasta de usuário da pessoa, com um Python só do skill, o yt-dlp, o Whisper, o modelo de rostos e a fonte. Leva alguns minutos na primeira vez. Quando terminar com `PRONTO`, diga à pessoa. Se der erro, leia a mensagem: ela diz o que instalar.

Para saber se já está preparado: `python3 $SKILL/ferramentas/preparar.py --conferir`.

### 2. Achar as lives (se a pessoa não mandou o link)

`python3 $SKILL/ferramentas/achar.py "gta 6" --quando hoje`

Mostra as maiores lives do assunto que já terminaram, com o link. `--quando semana` ou `mes` quando hoje vier vazio. Mostre a lista e siga com as primeiras, ou com as que a pessoa escolher.

### 3. Ouvir

`python3 $SKILL/ferramentas/ouvir.py "<link>"`

O link vai sempre entre aspas.

Cria `lives/<id>/` com `resumo.md`, `janelas/`, `transcricao.json`, `sinais.json` e `tempos.json`. Uma live de quatro horas leva alguns minutos num Mac com chip Apple. No Windows e no Mac com chip Intel o Whisper roda no processador e leva mais: diga isso à pessoa antes de começar uma live longa, e mostre o andamento (`ouvido até ...`).

- Se o site pedir login ou a live tiver restrição de idade: `--cookies chrome` (ou `edge`, `firefox`, `safari`).
- A língua vem da live. Para forçar: `--lingua pt`.
- Se a live não tiver replay do chat, o passo segue só com a transcrição e o volume.

### 4. Escolher

1. Leia `lives/<id>/resumo.md`.
2. Leia `referencias/como-escolher.md` uma vez.
3. Leia cada arquivo de `lives/<id>/janelas/`, na ordem. Anote os candidatos de cada janela antes de abrir a próxima.
4. Escreva `lives/<id>/momentos.json` com todos os candidatos de nota 60 ou mais.
5. `python3 $SKILL/ferramentas/conferir.py lives/<id> --manter 3`
6. Leia a fala exata de cada momento mantido. Se um aviso aparecer, ou se a fala não se sustenta sozinha, arrume `momentos.json` e rode de novo.

### 5. Cortar

`python3 $SKILL/ferramentas/cortar.py lives/<id>`

Para cada momento mantido sai, em `lives/<id>/cortes/`:

- `NN-titulo.mp4`: o corte, 1080 por 1920.
- `NN-titulo.txt`: o título, a legenda do post, as hashtags e o link da live no segundo certo.
- `NN-titulo-conferir.jpg`: seis quadros do corte.

Abra cada `-conferir.jpg` e veja quatro coisas: a câmera do streamer inteira em cima, o jogo embaixo, o título legível, a legenda na palavra certa.

- **A câmera saiu errada:** abra `lives/<id>/trechos/NN-quadro.jpg`, meça a caixa da câmera na tela e rode `cortar.py lives/<id> --so NN --camera x,y,largura,altura`.
- **A live não tem câmera:** o corte sai com o vídeo no meio e o fundo desfocado. Para forçar: `--modo sem`.
- **O streamer está em tela cheia:** o corte segue o rosto. Para forçar: `--modo cheia`.
- **Ele troca a tela no meio do momento:** o corte troca junto, sozinho (câmera em tela cheia, depois câmera em cima e jogo embaixo).

### 6. Entregar

Diga à pessoa, numa mensagem:

- Os números: a duração da live, quantos momentos apareceram, quantos ficaram, quanto tempo levou.
- Cada corte: o título, a duração, a nota e o motivo.
- Os outros momentos bons que ficaram de fora, para ela pedir se quiser.
- Onde estão os arquivos.

## O modo comentário

A pessoa põe a própria voz no corte: uma fala antes, uma fala depois, ou as duas.

1. Depois de mostrar os cortes, pergunte se ela quer comentar algum.
2. Ela grava a fala no gravador do celular ou do computador e salva em `lives/<id>/comentarios/`:
   - `NN-abre.m4a`: toca antes do corte.
   - `NN-fecha.m4a`: toca depois do corte.
   `NN` é o número do momento (`01`, `02`...). Serve m4a, mp3, wav ou o vídeo gravado no celular.
3. `python3 $SKILL/ferramentas/cortar.py lives/<id> --so NN`

Sai `NN-titulo-comentado.mp4`: a voz dela por cima da primeira e da última imagem do corte, paradas e escurecidas, com a fala dela legendada em verde. O corte sem comentário continua na pasta.

Se ela pedir ajuda com o que falar, sugira duas ou três frases curtas a partir do que acontece no trecho: uma que arma a cena antes, uma opinião ou uma pergunta depois. Quem fala é ela.

## Várias lives

Rode o `ouvir.py` de uma live por vez (o Whisper usa o computador inteiro). Enquanto a próxima é ouvida, escolha os momentos da anterior. O `cortar.py` de lives diferentes pode rodar junto.

## O visual

Crie `lives/<id>/estilo.json` só com o que mudar:

```json
{"cor_destaque": "#FFD60A", "tamanho_legenda": 92, "palavras_por_legenda": 3,
 "altura_legenda": 0.68, "titulo": true, "barra": true, "maiusculas": true}
```

Depois rode o `cortar.py` de novo. O trecho já baixado é reaproveitado.

## Podcast e vídeo longo

Funciona igual. Sem chat, as marcas são só as de volume. Num podcast com as pessoas em tela cheia, o corte segue o rosto que mais aparece.
