#!/usr/bin/env python3
"""Lê os feeds RSS das fontes abaixo e gera o arquivo news.json usado pelo Pauta.

Só usa a biblioteca padrão do Python (nada para instalar).
Uso: python fetch_news.py
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

BRT = timezone(timedelta(hours=-3))
UA = {"User-Agent": "Mozilla/5.0 (compatible; PautaBot/1.0)"}
MAX_AGE_DAYS = 7      # descarta matérias mais antigas que isso
MAX_PER_SOURCE = 10   # evita que uma fonte domine a lista
TOTAL_MAX = 260


def gnews(site):
    """Feed do Google Notícias restrito a um site (para quem não tem RSS próprio)."""
    q = urllib.parse.quote(f"site:{site} when:2d")
    return f"https://news.google.com/rss/search?hl=pt-BR&gl=BR&ceid=BR:pt-419&q={q}"


# feeds: lista de (url, editoria fixa ou None para classificar pelo texto)
# fallback=True: usa o primeiro feed que funcionar; False: junta todos.
SOURCES = {
    "bbc": {
        "name": "BBC News Brasil", "color": "#9f1239", "default": "Brasil", "fallback": False,
        "feeds": [("https://feeds.bbci.co.uk/portuguese/rss.xml", None)],
    },
    "g1": {
        "name": "g1", "color": "#dc2626", "default": "Brasil", "fallback": False,
        "feeds": [
            ("https://g1.globo.com/rss/g1/", None),
            ("https://g1.globo.com/rss/g1/politica/", "Brasil"),
            ("https://g1.globo.com/rss/g1/economia/", "Economia"),
            ("https://g1.globo.com/rss/g1/mundo/", "Mundo"),
            ("https://g1.globo.com/rss/g1/tecnologia/", "Tecnologia"),
            ("https://g1.globo.com/rss/g1/ciencia-e-saude/", "Ciência"),
            ("https://g1.globo.com/rss/g1/pop-arte/", "Cultura"),
        ],
    },
    "rt": {  # a Reuters não oferece RSS público oficial
        "name": "Reuters", "color": "#d97706", "default": "Mundo", "fallback": True,
        "feeds": [(gnews("reuters.com"), None)],
    },
    "icl": {
        "name": "ICL Notícias", "color": "#0369a1", "default": "Brasil", "fallback": True,
        "feeds": [("https://iclnoticias.com.br/feed/", None), (gnews("iclnoticias.com.br"), None)],
    },
    "b247": {
        "name": "Brasil 247", "color": "#15803d", "default": "Brasil", "fallback": True,
        "feeds": [("https://www.brasil247.com/rss", None), (gnews("brasil247.com"), None)],
    },
    "carta": {
        "name": "CartaCapital", "color": "#b91c1c", "default": "Brasil", "fallback": True,
        "feeds": [("https://www.cartacapital.com.br/feed/", None), (gnews("cartacapital.com.br"), None)],
    },
    "bdf": {
        "name": "Brasil de Fato", "color": "#be123c", "default": "Brasil", "fallback": True,
        "feeds": [("https://www.brasildefato.com.br/rss2.xml", None), ("https://www.brasildefato.com.br/rss", None), (gnews("brasildefato.com.br"), None)],
    },
    "intercept": {
        "name": "Intercept Brasil", "color": "#1f2937", "default": "Brasil", "fallback": True,
        "feeds": [("https://www.intercept.com.br/feed/", None), (gnews("intercept.com.br"), None)],
    },
    "op": {
        "name": "Outras Palavras", "color": "#7c3aed", "default": "Brasil", "fallback": True,
        "feeds": [("https://outraspalavras.net/feed/", None), (gnews("outraspalavras.net"), None)],
    },
    "eo": {
        "name": "Esquerda Online", "color": "#dc2626", "default": "Brasil", "fallback": True,
        "feeds": [("https://esquerdaonline.com.br/feed/", None), (gnews("esquerdaonline.com.br"), None)],
    },
    "uol": {
        "name": "UOL Notícias", "color": "#d97706", "default": "Brasil", "fallback": True,
        "feeds": [("https://rss.uol.com.br/feed/noticias.xml", None), (gnews("noticias.uol.com.br"), None)],
    },
    "uole": {
        "name": "UOL Esporte", "color": "#ea580c", "default": "Esportes", "fallback": True,
        "feeds": [("https://rss.uol.com.br/feed/esporte.xml", "Esportes"), (gnews("esporte.uol.com.br"), "Esportes")],
    },
    "terra": {
        "name": "Terra Notícias", "color": "#059669", "default": "Brasil", "fallback": True,
        "feeds": [(gnews("terra.com.br/noticias"), None)],
    },
    "gefla": {
        "name": "ge Flamengo", "color": "#b91c1c", "default": "Esportes", "fallback": True,
        "feeds": [("https://ge.globo.com/rss/ge/futebol/times/flamengo/", "Esportes"), (gnews("ge.globo.com/futebol/times/flamengo"), "Esportes")],
    },
    "crf": {  # site oficial do clube: não tem RSS, então usa o Google Notícias
        "name": "Flamengo (site oficial)", "color": "#111827", "default": "Esportes", "fallback": True,
        "feeds": [(gnews("flamengo.com.br/noticias/futebol"), "Esportes")],
    },
    "espn": {  # matérias da ESPN Brasil que citam o Flamengo (a página do time não tem RSS)
        "name": "ESPN Flamengo", "color": "#c2410c", "default": "Esportes", "fallback": True,
        "feeds": [(gnews("espn.com.br Flamengo"), "Esportes")],
    },
    "espnb": {
        "name": "ESPN Brasil", "color": "#dc2626", "default": "Esportes", "fallback": True,
        "feeds": [(gnews("espn.com.br"), "Esportes")],
    },
    "uoleco": {
        "name": "UOL Economia", "color": "#ca8a04", "default": "Economia", "fallback": True,
        "feeds": [("https://rss.uol.com.br/feed/economia.xml", "Economia"), (gnews("economia.uol.com.br"), "Economia")],
    },
    "terrafut": {
        "name": "Terra Futebol", "color": "#047857", "default": "Esportes", "fallback": True,
        "feeds": [(gnews("terra.com.br/esportes/futebol"), "Esportes")],
    },
    "planeta": {
        "name": "Terra Planeta", "color": "#0d9488", "default": "Ciência", "fallback": True,
        "feeds": [(gnews("terra.com.br/planeta"), "Ciência")],
    },
    "super": {
        "name": "Super Interessante", "color": "#e11d48", "default": "Ciência", "fallback": True,
        "feeds": [("https://super.abril.com.br/feed/", "Ciência"), (gnews("super.abril.com.br"), "Ciência")],
    },
    "galileu": {
        "name": "Galileu", "color": "#0284c7", "default": "Ciência", "fallback": True,
        "feeds": [("https://revistagalileu.globo.com/rss/revistagalileu/", "Ciência"), (gnews("revistagalileu.globo.com"), "Ciência")],
    },
    "usp": {
        "name": "Jornal da USP", "color": "#b45309", "default": "Ciência", "fallback": True,
        "feeds": [("https://jornal.usp.br/feed/", "Ciência"), (gnews("jornal.usp.br"), "Ciência")],
    },
    "olhar": {
        "name": "Olhar Digital", "color": "#6b46c1", "default": "Tecnologia", "fallback": True,
        "feeds": [("https://olhardigital.com.br/feed/", None), (gnews("olhardigital.com.br"), None)],
    },
    "mongabay": {
        "name": "Mongabay Brasil", "color": "#15803d", "default": "Ciência", "fallback": True,
        "feeds": [("https://brasil.mongabay.com/feed/", "Ciência"), (gnews("brasil.mongabay.com"), "Ciência")],
    },
    "oeco": {
        "name": "((o))eco", "color": "#16a34a", "default": "Ciência", "fallback": True,
        "feeds": [("https://oeco.org.br/feed/", "Ciência"), (gnews("oeco.org.br"), "Ciência")],
    },
}

# Ordem importa: a primeira editoria que casar vence.
KEYWORDS = [
    ("Esportes", r"futebol|brasileir[ãa]o|libertadores|copa d|campeonato|flamengo|corinthians|palmeiras|v[ôo]lei|f[óo]rmula 1|\bnba\b|olimp|atleta|\bgol\b|t[ée]cnico"),
    ("Economia", r"economia|infla[çc][ãa]o|juros|selic|d[óo]lar|ibovespa|\bpib\b|banco central|petr[óo]leo|imposto|desemprego|tarifa|mercado financeiro"),
    ("Tecnologia", r"intelig[êe]ncia artificial|chatgpt|openai|iphone|apple|google|microsoft|nvidia|meta ai|tecnologia|aplicativo|celular|hacker|ciberataque|big tech"),
    ("Ciência", r"cientistas|\bnasa\b|telesc[óo]pio|pesquisadores|descoberta|planeta|espacial|vacina|f[óo]ssil|arque[óo]log"),
    ("Cultura", r"filme|cinema|s[ée]rie|m[úu]sica|\bshow\b|festival|exposi[çc][ãa]o|livro|teatro|cantor|cantora|atriz|\bator\b|oscar|novela"),
    ("Mundo", r"\beua\b|estados unidos|trump|israel|gaza|ucr[âa]nia|r[úu]ssia|china|\bir[ãa]\b|uni[ãa]o europeia|\bonu\b|putin|europa|fran[çc]a|argentina"),
]


def classify(text, default):
    t = text.lower()
    for cat, pattern in KEYWORDS:
        if re.search(pattern, t):
            return cat
    return default


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def child(node, name):
    for c in node:
        if c.tag.split("}")[-1] == name:
            return c
    return None


def first(node, *names):
    """Primeiro filho existente (não use `or`: elemento sem filhos conta como falso)."""
    for name in names:
        c = child(node, name)
        if c is not None:
            return c
    return None


def parse_date(text):
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def clean(text, limit=230):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return text


IMG_RE = re.compile(r"<img[^>]+?src=[\"']([^\"']+)[\"']", re.I)
BAD_IMG = re.compile(r"(pixel|spacer|blank|1x1|logo|avatar|gravatar|emoji|/ads?/|googleusercontent\.com/.{0,5}$)", re.I)


def good_img(u):
    u = html.unescape((u or "").strip())
    if u.startswith("//"):
        u = "https:" + u
    if not u.lower().startswith(("http://", "https://")) or BAD_IMG.search(u):
        return ""
    if u.lower().startswith("http://"):
        u = "https://" + u[7:]
    return u[:500]


def find_image(node):
    """Procura a foto da matéria: media:content/thumbnail, enclosure ou <img> no corpo."""
    html_bits = []
    for el in node.iter():
        tag = el.tag.split("}")[-1]
        u = el.get("url") or ""
        kind = (el.get("type") or el.get("medium") or "").lower()
        if tag in ("content", "thumbnail", "enclosure", "image") and u:
            if tag == "thumbnail" or kind.startswith("image") or (tag == "content" and not kind and re.search(r"\.(jpe?g|png|webp)", u, re.I)):
                g = good_img(u)
                if g:
                    return g
        if tag in ("description", "encoded", "summary", "content") and el.text:
            html_bits.append(el.text)
    for bit in html_bits:
        m = IMG_RE.search(bit)
        if m:
            g = good_img(m.group(1))
            if g:
                return g
    return ""


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    for node in root.iter():
        if node.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = child(node, "title")
        link = child(node, "link")
        if title is None or link is None:
            continue
        url = (link.text or link.get("href") or "").strip()
        desc = first(node, "description", "summary", "content")
        date = first(node, "pubDate", "published", "updated")
        yield {
            "title": clean(title.text, 300),
            "url": url,
            "desc": clean(desc.text if desc is not None else ""),
            "dt": parse_date(date.text if date is not None else None),
            "img": find_image(node),
        }


def norm(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())[:45]


REPORT = {}  # resumo por fonte, gravado em news.json para a página status.html


def collect():
    now = datetime.now(timezone.utc)
    oldest = now - timedelta(days=MAX_AGE_DAYS)
    items, seen = [], set()
    for key, src in SOURCES.items():
        found = []
        rep = {"nome": src["name"], "feeds": [], "recebidas": 0, "recentes": 0, "mantidas": 0}
        REPORT[key] = rep
        for url, fixed_cat in src["feeds"]:
            try:
                entries = list(parse_feed(fetch(url)))
            except Exception as exc:  # um feed fora do ar não derruba o resto
                print(f"[erro] {key}: {url} -> {exc}", file=sys.stderr)
                rep["feeds"].append({"url": url, "ok": False, "n": 0, "erro": str(exc)[:120]})
                continue
            print(f"[ok] {key}: {len(entries)} itens em {url}")
            rep["feeds"].append({"url": url, "ok": True, "n": len(entries), "erro": ""})
            rep["recebidas"] += len(entries)
            for e in entries:
                e["fixed"] = fixed_cat
            found.extend(entries)
            if src["fallback"] and entries:
                break
        found = [e for e in found if e["url"] and e["title"] and e["dt"] and e["dt"] >= oldest]
        found.sort(key=lambda e: e["dt"], reverse=True)
        rep["recentes"] = len(found)
        kept = 0
        for e in found:
            title = e["title"]
            if " - " in title and "news.google.com" in e["url"]:
                title = title.rsplit(" - ", 1)[0]  # tira o " - Veículo" do Google Notícias
            sig = norm(title)
            if sig in seen:
                continue
            seen.add(sig)
            summary = e["desc"]
            if not summary or len(summary) < 40 or summary.lower().startswith(title.lower()[:30]):
                summary = f"Veja a matéria completa em {src['name']}."
            items.append({
                "s": key,
                "c": e["fixed"] or classify(f"{title} {summary}", src["default"]),
                "d": e["dt"].astimezone(BRT).strftime("%Y-%m-%d"),
                "r": 5 if kept < 3 else 4 if kept < 8 else 3,
                "t": title,
                "x": summary,
                "u": e["url"],
                "i": e.get("img", ""),
                "_ts": e["dt"].timestamp(),
            })
            kept += 1
            rep["mantidas"] = kept
            if kept >= MAX_PER_SOURCE:
                break
    items.sort(key=lambda i: i["_ts"], reverse=True)
    for i in items:
        del i["_ts"]
    return items[:TOTAL_MAX]


def main():
    items = collect()
    if not items:
        print("Nenhuma notícia coletada; news.json não foi alterado.", file=sys.stderr)
        sys.exit(1)
    data = {
        "updated": datetime.now(BRT).isoformat(timespec="seconds"),
        "sources": {k: [v["name"], v["color"]] for k, v in SOURCES.items()},
        "report": REPORT,
        "items": items,
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"news.json gerado com {len(items)} matérias.")


if __name__ == "__main__":
    main()
