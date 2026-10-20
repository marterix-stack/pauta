# Pauta — agregador com atualização diária

Arquivos:
- `index.html` — o site (lê `news.json`; se não existir, mostra um retrato de 19/10/2026)
- `fetch_news.py` — lê os feeds de BBC News Brasil, g1, Reuters, ICL Notícias e Brasil 247 e gera `news.json`
- `.github/workflows/atualizar.yml` — roda o script todo dia às 06h (Brasília)

Como publicar de graça no GitHub:
1. Crie um repositório e envie estes arquivos (mantendo a pasta `.github/workflows`).
2. Em Settings → Pages, escolha "Deploy from a branch", branch `main`, pasta `/ (root)`.
3. Em Actions, abra "Atualizar notícias" e clique em "Run workflow" para gerar o primeiro `news.json`.
4. Abra o endereço do Pages. Dali em diante o site se atualiza sozinho todo dia.

Notas:
- Os feeds não foram testados no ambiente onde o código foi escrito (sem internet). Veja o log do primeiro run: linhas `[erro]` mostram feeds que precisam de ajuste em `SOURCES`.
- A Reuters não tem RSS público; o script usa o Google Notícias, e os títulos podem vir em inglês.
- ICL e Brasil 247 tentam o feed do site e, se falhar, o Google Notícias.
- Para mudar o horário, edite o `cron` (está em UTC, 3 horas à frente de Brasília).
