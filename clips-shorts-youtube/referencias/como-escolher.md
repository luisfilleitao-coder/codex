# Como escolher os momentos

O `ouvir.py` entrega a live inteira em texto, em janelas de 12 minutos, com duas marcas nas frases:

- `ALTO+9dB`: o streamer ficou 9 dB acima do volume normal daqueles minutos. Grito, risada, susto.
- `CHAT x3.1`: o chat andou 3,1 vezes mais rápido que o normal. Alguma coisa aconteceu uns segundos antes.

As marcas mostram onde olhar. Quem decide é a leitura: um grito sem contexto não vira corte, e uma opinião forte dita em voz baixa vira.

## A ordem

1. Leia `resumo.md`: o tamanho da live e os maiores picos.
2. Leia as janelas uma por uma, na ordem (`janelas/janela-01.md`, `janela-02.md`...). Em cada uma, anote de zero a três candidatos. Zero é uma resposta normal.
3. Escreva `momentos.json` com todos os candidatos de nota 60 ou mais.
4. Rode o `conferir.py`, leia a fala exata de cada um e arrume o que ele avisar.

## O que vira corte

- **Primeira reação:** a primeira vez que ele vê uma coisa. O espanto é de verdade.
- **Descoberta:** achou um detalhe, um segredo, um bug, um jeito de fazer.
- **Surto:** perdeu a linha de raiva, de medo ou de rir.
- **Falha engraçada:** deu errado na frente de todo mundo.
- **Opinião forte:** uma frase que metade vai concordar e metade vai brigar nos comentários.
- **História curta:** começo, meio e final em menos de um minuto.
- **Com o chat:** uma doação, uma pergunta ou uma provocação que rende resposta boa.

## As quatro perguntas

Um momento só entra se as quatro respostas forem sim.

1. **Quem nunca viu a live entende em três segundos?** Se precisa de "como eu falei antes", fica fora.
2. **Começa na frase que arma a cena?** Não em "então", "aí", "tipo", nem no meio de um raciocínio. Volte até a frase que apresenta o assunto.
3. **Termina no ponto alto?** A risada, o grito, a frase de efeito. O corte acaba ali, sem a explicação que vem depois.
4. **É uma ideia só?** Dois assuntos são dois cortes, ou nenhum.

## O tamanho

Entre 20 e 45 segundos é o melhor. Menos de 15 não dá tempo de entender. Mais de 60 só quando é uma história que não dá para cortar.

## A nota, de 0 a 100

| Vale | O quê |
|---|---|
| 30 | Os três primeiros segundos prendem |
| 25 | Se sustenta sozinho |
| 25 | Tem um ponto alto claro |
| 10 | Tem marca de volume ou de chat |
| 10 | Dá vontade de comentar ou mandar para alguém |

Seja duro. Numa live de quatro horas, a maioria das janelas não tem nada acima de 70. Nota alta para tudo estraga a escolha.

## O título, a legenda e as hashtags

- **Título:** o que aparece no corte. Até 45 letras. Diz quem e o que acontece, sem entregar o final. Só com o que é dito no trecho: nada inventado.
- **Legenda:** uma ou duas frases para o post, no jeito que a pessoa fala, com uma pergunta no final quando couber.
- **Hashtags:** de quatro a seis: o jogo, o streamer, o assunto do momento.
- **Os nomes:** o nome do streamer e o do jogo vêm do `info.json` e do `resumo.md`, escritos como estão lá. A transcrição erra nomes.

## O arquivo

`momentos.json`, na pasta da live:

```json
{"momentos": [
  {"inicio": "1:23:45", "fim": "1:24:20", "nota": 87, "tipo": "primeira reação",
   "titulo": "Fulano vê o mapa pela primeira vez",
   "motivo": "espanto de verdade, fecha numa frase que todo mundo vai repetir",
   "legenda": "A cara dele quando o mapa abriu. Você também ficou assim?",
   "hashtags": ["#jogo", "#fulano", "#cortes", "#live"]}
]}
```

`inicio` e `fim` são os tempos que aparecem entre colchetes nas janelas. O `conferir.py` acerta os dois nas frases.
