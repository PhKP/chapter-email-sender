#!/usr/bin/env python3
"""
Scrapes all 97 chapters from:
  https://yoshi389111.github.io/kinokobooks/soft_en/

Produces chapters.json with title, author, and content fields.
Run this to regenerate chapters.json from the web source.
"""

import json
import time
import urllib.request
from html.parser import HTMLParser
from html import unescape

BASE_URL = "https://yoshi389111.github.io/kinokobooks/soft_en/"
INDEX_URL = BASE_URL + "index.html"


class IndexParser(HTMLParser):
    """Extracts chapter hrefs from the index page."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._in_nav = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            href = attrs["href"]
            if href.endswith(".htm") and href != "index.htm":
                self.links.append(href)


class ChapterParser(HTMLParser):
    """Extracts title, body paragraphs, and author from a chapter page."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.author = ""
        self.paragraphs = []
        self._in_article = False
        self._in_header = False
        self._in_footer = False
        self._in_h1 = False
        self._in_p = False
        self._p_class = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self._in_article = True
        elif tag == "header" and self._in_article:
            self._in_header = True
        elif tag == "footer" and self._in_article:
            # Flush any unclosed <p> before the footer
            if self._in_p and self._buf:
                text = unescape("".join(self._buf)).strip()
                if text:
                    self.paragraphs.append(text)
                self._in_p = False
                self._buf = []
            self._in_footer = True
        elif tag == "h1" and self._in_header:
            self._in_h1 = True
            self._buf = []
        elif tag == "p" and self._in_article:
            self._in_p = True
            self._p_class = attrs.get("class")
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "article":
            self._in_article = False
        elif tag == "header":
            self._in_header = False
        elif tag == "footer":
            self._in_footer = False
        elif tag == "h1" and self._in_h1:
            self._in_h1 = False
            self.title = unescape("".join(self._buf)).strip()
            self._buf = []
        elif tag == "p" and self._in_p:
            self._in_p = False
            text = unescape("".join(self._buf)).strip()
            if text:
                if self._p_class == "author":
                    self.author = text.removeprefix("By ").strip()
                elif not self._in_footer:
                    self.paragraphs.append(text)
            self._buf = []

    def handle_data(self, data):
        if self._in_h1 or self._in_p:
            self._buf.append(data)

    def handle_entityref(self, name):
        self.handle_data(unescape(f"&{name};"))


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "chapter-scraper/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def main():
    print("Fetching index...")
    index_html = fetch(INDEX_URL)
    parser = IndexParser()
    parser.feed(index_html)
    links = parser.links
    print(f"Found {len(links)} chapters.")

    chapters = []
    for i, href in enumerate(links, start=1):
        url = BASE_URL + href
        print(f"  [{i:2d}/97] {href}")
        html = fetch(url)
        cp = ChapterParser()
        cp.feed(html)
        chapters.append({
            "chapter": i,
            "title": cp.title,
            "author": cp.author,
            "content": "\n\n".join(cp.paragraphs),
        })
        time.sleep(0.2)  # polite crawl rate

    with open("chapters.json", "w", encoding="utf-8") as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(chapters)} chapters to chapters.json.")

    # Spot-check
    missing = [c for c in chapters if not c["content"]]
    no_author = [c for c in chapters if not c["author"]]
    if missing:
        print(f"WARNING: Empty content in chapters: {[c['chapter'] for c in missing]}")
    if no_author:
        print(f"WARNING: Missing author in chapters: {[c['chapter'] for c in no_author]}")
    if not missing and not no_author:
        print("All chapters have content and author. ✓")


if __name__ == "__main__":
    main()
