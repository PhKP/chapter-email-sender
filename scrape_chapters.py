#!/usr/bin/env python3
r"""
Scrapes all 97 chapters from:
  https://yoshi389111.github.io/kinokobooks/soft_en/

Produces chapters.json with title, author, and content fields. `content` is a
"\n\n"-delimited string of blocks, each optionally prefixed with a marker that
sender.py turns back into markup — see ChapterParser.BLOCKS.

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

    # Block-level tags whose text ends up in the body, mapped to the marker that
    # survives sender.py's "\n\n"-delimited rendering. <dt> is a subheading in
    # the one chapter (26) that uses a definition list.
    BLOCKS = {
        "p": "",
        "li": "• ",
        "dd": "",
        "h2": "## ",
        "dt": "## ",
        "blockquote": "> ",
    }

    # Placeholder for a break that separates paragraphs *within* one block. The
    # source hard-wraps prose across lines, so a bare "\n" can't mean this.
    SPLIT = "\x00"

    def __init__(self):
        super().__init__()
        self.title = ""
        self.author = ""
        self.paragraphs = []
        self._in_article = False
        self._in_header = False
        self._in_footer = False
        self._in_blockquote = False
        self._block = None
        self._p_class = None
        self._buf = []

    @staticmethod
    def _clean(text):
        # Collapse runs of whitespace (incl. source newlines) to single spaces.
        return " ".join(unescape(text).split())

    def _flush(self):
        """Close the open block and emit its paragraphs."""
        block, buf, p_class = self._block, self._buf, self._p_class
        self._block, self._buf, self._p_class = None, [], None
        if block is None:
            return

        raw = "".join(buf)
        if block == "h1":
            self.title = self._clean(raw)
            return
        if p_class == "author":
            text = self._clean(raw)
            if text:
                # Source authors are inconsistent ("By X" / "by X" / "X").
                self.author = text[3:].strip() if text[:3].lower() == "by " else text
            return
        if self._in_footer:
            return

        if block == "dd":
            # Inside <dd> the source puts each paragraph on its own line
            # (no wrapping), so newlines there are paragraph breaks.
            raw = raw.replace("\n", self.SPLIT)
        # A <p> nested in a <blockquote> is still quoted text.
        prefix = "> " if self._in_blockquote else self.BLOCKS[block]
        for part in raw.split(self.SPLIT):
            text = self._clean(part)
            if text:
                self.paragraphs.append(prefix + text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self._in_article = True
        elif not self._in_article:
            return
        elif tag == "header":
            self._in_header = True
        elif tag == "footer":
            self._flush()
            self._in_footer = True
        elif tag == "br" and self._block:
            self._buf.append(self.SPLIT)
        elif tag == "h1" and self._in_header:
            self._flush()
            self._block = "h1"
        elif tag in self.BLOCKS:
            # Some source pages open a new <p> without closing the previous
            # one, so a new block flushes what came before instead of
            # discarding it.
            self._flush()
            if tag == "blockquote":
                self._in_blockquote = True
            self._block = tag
            self._p_class = attrs.get("class")

    def handle_endtag(self, tag):
        if tag == "article":
            self._flush()
            self._in_article = False
        elif tag == "header":
            self._in_header = False
        elif tag == "footer":
            self._in_footer = False
        elif tag == "blockquote":
            self._flush()
            self._in_blockquote = False
        elif self._block == tag:
            self._flush()

    def handle_data(self, data):
        if self._block:
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
