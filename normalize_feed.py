#!/usr/bin/env python3
"""Miroir normalise du flux RSS de blog.projectnightcrawler.dev.

Le flux amont est valide, mais servi en `text/xml` sans parametre charset.
La RFC 3023 impose alors de le decoder en us-ascii, ce qui fait echouer les
parseurs stricts (start.me entre autres) des le premier octet non-ASCII --
en pratique le `(c)` de la balise <copyright>, situe avant le premier <item>,
d'ou un flux vu comme vide.

On re-emet donc un RSS 2.0 strictement ASCII : tout caractere non-ASCII est
echappe en reference numerique. Le resultat est correct quel que soit le
charset suppose par le consommateur, sans dependre de l'en-tete HTTP.
"""

import html
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path

SOURCE = "https://blog.projectnightcrawler.dev/posts/index.xml"
OUTPUT = Path(__file__).parent / "docs" / "pnc.rss"
TIMEOUT = 30

SELF_LINK = "https://kotk1n.github.io/pnc-feed/pnc.rss"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pnc-feed-mirror/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    # On decode nous-memes en UTF-8 : c'est ce que le prologue XML declare, et
    # l'en-tete HTTP amont est justement celui en qui on ne peut pas avoir
    # confiance.
    return raw.decode("utf-8")


def text_of(item, tag):
    node = item.find(tag)
    return (node.text or "").strip() if node is not None else ""


def parse_items(xml_text):
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("flux amont inattendu : pas de <channel>")

    items = []
    for node in channel.findall("item"):
        link = text_of(node, "link")
        if not link:
            continue

        raw_date = text_of(node, "pubDate")
        try:
            when = parsedate_to_datetime(raw_date)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            # Un item sans date exploitable est ce qui a casse l'ordre de tri
            # cote Diffbot. On refuse de le laisser passer sans date : le lien
            # sert d'identite stable, et on le date au plus ancien pour qu'il
            # ne remonte jamais artificiellement en tete.
            when = datetime(1970, 1, 1, tzinfo=timezone.utc)

        items.append(
            {
                "title": text_of(node, "title") or link,
                "link": link,
                "guid": text_of(node, "guid") or link,
                "description": text_of(node, "description"),
                "date": when,
            }
        )

    items.sort(key=lambda i: i["date"], reverse=True)
    return items


def esc(text):
    """Echappe le XML, puis tout caractere non-ASCII en reference numerique."""
    text = html.escape(text, quote=True)
    return text.encode("ascii", "xmlcharrefreplace").decode("ascii")


def build_rss(items):
    now = format_datetime(datetime.now(timezone.utc))
    latest = format_datetime(items[0]["date"]) if items else now

    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        "<title>Posts on PNC Blog</title>",
        "<link>https://blog.projectnightcrawler.dev/posts/</link>",
        "<description>Miroir normalise du flux Posts on PNC Blog</description>",
        "<language>en</language>",
        f"<lastBuildDate>{latest}</lastBuildDate>",
        f"<generator>pnc-feed-mirror (source: {esc(SOURCE)})</generator>",
        f'<atom:link href="{esc(SELF_LINK)}" rel="self" type="application/rss+xml"/>',
    ]

    for item in items:
        out += [
            "<item>",
            f"<title>{esc(item['title'])}</title>",
            f"<link>{esc(item['link'])}</link>",
            f'<guid isPermaLink="true">{esc(item["guid"])}</guid>',
            f"<pubDate>{format_datetime(item['date'])}</pubDate>",
            f"<description>{esc(item['description'])}</description>",
            "</item>",
        ]

    out += ["</channel>", "</rss>", ""]
    return "\n".join(out)


def main():
    items = parse_items(fetch(SOURCE))
    if not items:
        raise SystemExit("aucun item recupere : on refuse d'ecraser le miroir")

    rss = build_rss(items)

    # Garde-fou : ce qu'on publie doit etre du pur ASCII et du XML valide.
    rss.encode("ascii")
    ET.fromstring(rss)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    previous = OUTPUT.read_text() if OUTPUT.exists() else None

    # lastBuildDate bouge a chaque execution : on l'ignore pour ne pas produire
    # un commit par heure sans changement reel. Tout le reste compte, en-tete
    # comprise, sinon une modification de la configuration passerait inapercue.
    def comparable(text):
        return "\n".join(
            line for line in text.splitlines() if "<lastBuildDate>" not in line
        )

    if previous is not None and comparable(previous) == comparable(rss):
        print(f"inchange : {len(items)} items, rien a commiter")
        return 0

    OUTPUT.write_text(rss)
    print(f"ecrit {OUTPUT} : {len(items)} items, plus recent = {items[0]['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
