# core/utils/nhgscraper/scraper.py

import copy
import os
import re
import time
import random
from collections import deque
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from fake_useragent import UserAgent
from curl_cffi import requests
from tabulate import tabulate


class NHGScraper:
    BASE_URL = "https://richtlijnen.nhg.org"
    SITEMAP_URL = "https://richtlijnen.nhg.org/sitemap.xml"
    # Fallback: homepage tab panels (only present in full SSR response)
    DISCOVERY_URL = "https://richtlijnen.nhg.org/"

    CATEGORY_TAB = {
        "standaard": "tab--nhgstandaarden",
        "behandelrichtlijn": "tab--nhgbehandelrichtlijnen",
    }
    CATEGORY_PATH_PREFIX = {
        "standaard": "/standaarden/",
        "behandelrichtlijn": "/behandelrichtlijnen/",
    }

    def __init__(
        self,
        debug_limit: Optional[int] = None,
        verbose: Optional[bool] = None,
    ):
        self.debug_limit = debug_limit

        if verbose is None:
            verbose = os.getenv("NHG_VERBOSE", "0").strip() in ("1", "true", "True", "yes")
        self.verbose = verbose

        self.ua = UserAgent()
        self.session = requests.Session(impersonate="chrome120")

        self.discovery_sleep_min = float(os.getenv("NHG_DISCOVERY_SLEEP_MIN", "0.5"))
        self.discovery_sleep_max = float(os.getenv("NHG_DISCOVERY_SLEEP_MAX", "1.5"))

        self._html_cache: deque = deque(maxlen=5)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            "Referer": self.BASE_URL,
        }

    def _polite_sleep(self, where: str = "") -> None:
        lo = 0.15 if self.debug_limit else self.discovery_sleep_min
        hi = 0.35 if self.debug_limit else self.discovery_sleep_max
        s = random.uniform(lo, hi)
        self._log(f"Sleep ({where}): {s:.2f}s")
        time.sleep(s)

    def _exp_backoff(self, attempt: int, base: float = 3.0, cap: float = 90.0) -> float:
        return min(cap, base * (2 ** attempt)) * random.uniform(0.8, 1.2)

    def fetch_url(self, url: str) -> Optional[str]:
        for cached_url, content in self._html_cache:
            if cached_url == url:
                return content

        max_retries = int(os.getenv("NHG_HTTP_MAX_RETRIES", "3"))
        timeout_s = float(os.getenv("NHG_HTTP_TIMEOUT", "20"))

        last_err = None
        for attempt in range(max_retries + 1):
            self._polite_sleep(where="fetch_url")
            try:
                res = self.session.get(url, headers=self._headers(), timeout=timeout_s)
                status = res.status_code

                if status == 429:
                    wait = self._exp_backoff(attempt, base=30.0, cap=300.0)
                    self._log(f"HTTP 429 {url} -> wait {wait:.1f}s")
                    time.sleep(wait)
                    continue

                if status in (500, 502, 503, 504):
                    wait = self._exp_backoff(attempt)
                    self._log(f"HTTP {status} {url} -> wait {wait:.1f}s")
                    time.sleep(wait)
                    continue

                if status in (400, 401, 403, 404):
                    return None

                res.raise_for_status()
                html = res.text
                self._html_cache.append((url, html))
                return html

            except Exception as e:
                last_err = e
                time.sleep(self._exp_backoff(attempt))

        self._log(f"Fetch failed {url}: {last_err}")
        return None

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _abs_url(self, href: str) -> Optional[str]:
        if not href:
            return None
        href = href.strip()
        if href.startswith("#") or href.startswith("javascript"):
            return None
        if href.startswith("/"):
            return f"{self.BASE_URL}{href}"
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return f"{self.BASE_URL}/{href.lstrip('/')}"

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _category_for_url(self, url: str) -> Optional[str]:
        for cat, prefix in self.CATEGORY_PATH_PREFIX.items():
            if prefix in url:
                return cat
        return None

    def _discover_from_sitemap(self, categories: List[str]) -> List[Dict]:
        """
        Primary discovery: parse sitemap.xml.
        Drupal sitemaps list every published node — no JS required.
        """
        xml = self.fetch_url(self.SITEMAP_URL)
        if not xml:
            self._log("Sitemap fetch failed")
            return []

        soup = BeautifulSoup(xml, "xml")
        items: List[Dict] = []
        seen: set = set()

        for loc in soup.find_all("loc"):
            url = loc.get_text(strip=True)
            cat = self._category_for_url(url)
            if not cat or cat not in categories:
                continue
            # Exclude sub-pages like /standaarden/hartfalen/wijzigingen
            path = url.replace(self.BASE_URL, "").strip("/")
            if path.count("/") != 1:
                continue
            if url in seen:
                continue
            seen.add(url)
            items.append({
                "url": url,
                "category": cat,
                "name": None,
                "revision_status": None,
            })

        self._log(f"Sitemap discovery: {len(items)} items total")
        return items

    def _discover_from_tabs(self, categories: List[str]) -> List[Dict]:
        """
        Fallback discovery: parse homepage tab panels.
        Only works when the server returns the full SSR response.
        """
        html = self.fetch_url(self.DISCOVERY_URL)
        if not html:
            self._log("Homepage fetch failed")
            return []

        soup = BeautifulSoup(html, "html.parser")
        result: List[Dict] = []

        for cat in categories:
            tab_id = self.CATEGORY_TAB.get(cat)
            if not tab_id:
                continue

            tab = soup.find("div", id=tab_id)
            if not tab:
                self._log(f"Tab #{tab_id} not found — server may not have returned full SSR")
                continue

            seen: set = set()
            for a in tab.find_all("a", class_="outer-link"):
                href = (a.get("href") or "").strip()
                if not href or href in seen:
                    continue
                seen.add(href)

                name_dd = a.find("dd", class_=lambda c: not c or "revision-status" not in " ".join(c))
                name = name_dd.get_text(strip=True) if name_dd else None

                revision_dd = a.find("dd", class_="revision-status")
                revision = revision_dd.get("title", "").strip() if revision_dd else None

                url = self._abs_url(href)
                if not url:
                    continue

                result.append({
                    "url": url,
                    "category": cat,
                    "name": name,
                    "revision_status": revision,
                })

            cat_count = sum(1 for r in result if r["category"] == cat)
            self._log(f"Tab discovery [{cat}]: {cat_count} items")

        return result

    def discovery_phase(self, categories: Optional[List[str]] = None) -> List[Dict]:
        """
        Returns a flat list of {"url", "category", "name", "revision_status"} dicts.
        categories: subset of ["standaard", "behandelrichtlijn"], or None for all.

        Tries sitemap.xml first (reliable, no JS). Falls back to homepage tab parsing.
        """
        selected = categories or list(self.CATEGORY_TAB.keys())

        items = self._discover_from_sitemap(selected)

        if not items:
            self._log("Sitemap returned nothing, falling back to tab parsing")
            items = self._discover_from_tabs(selected)

        if self.debug_limit:
            items = items[: self.debug_limit]

        return items

    # ------------------------------------------------------------------
    # Extraction: HTML -> Markdown
    # ------------------------------------------------------------------

    def _normalize(self, text: str) -> str:
        return " ".join((text or "").replace("\xa0", " ").split()).strip()

    def _heading_text(self, tag: Tag) -> str:
        # Remove the 'Kopieer ankerlink' button injected into every heading.
        clone = copy.copy(tag)
        for btn in clone.find_all("button", class_="btn-copy-anchor-link"):
            btn.decompose()
        return self._normalize(clone.get_text(" ", strip=True))

    def _replace_links_with_md(self, node: Tag) -> None:
        for a in node.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            text = self._normalize(a.get_text(" ", strip=True)) or "link"
            if href.startswith("/"):
                href = f"{self.BASE_URL}{href}"
            if href and not href.startswith("#"):
                a.replace_with(NavigableString(f"[{text}]({href})"))
            else:
                a.replace_with(NavigableString(text))

    def _table_to_markdown(self, table: Tag) -> str:
        def cell_text(td: Tag) -> str:
            return self._normalize(td.get_text(" ", strip=True))

        header: Optional[List[str]] = None
        body_rows: List[List[str]] = []

        thead = table.find("thead")
        if thead:
            tr = thead.find("tr")
            if tr:
                cells = tr.find_all(["th", "td"])
                if cells:
                    header = [cell_text(c) for c in cells]

        for tr in table.find_all("tr"):
            if thead and tr.find_parent("thead"):
                continue
            cells = tr.find_all(["th", "td"])
            row = [cell_text(c) for c in cells]
            if any(row):
                body_rows.append(row)

        if header is None and body_rows:
            first_tr = table.find("tr")
            if first_tr and first_tr.find("th"):
                header = body_rows[0]
                body_rows = body_rows[1:]

        if not header and not body_rows:
            return ""

        col_n = max([len(header) if header else 0] + [len(r) for r in body_rows]) or 1
        if header is None:
            header = [f"Kolom {i+1}" for i in range(col_n)]
        header = (header + [""] * (col_n - len(header)))[:col_n]
        body_rows = [(r + [""] * (col_n - len(r)))[:col_n] for r in body_rows]

        return tabulate(body_rows, headers=header, tablefmt="github") + "\n\n"

    def _list_to_markdown(self, list_tag: Tag, indent: int = 0) -> str:
        if list_tag.name not in ("ul", "ol"):
            return ""
        ordered = list_tag.name == "ol"
        lines: List[str] = []
        idx = 1
        for li in list_tag.find_all("li", recursive=False):
            li_clone = copy.deepcopy(li)
            self._replace_links_with_md(li_clone)
            nested = li_clone.find_all(["ul", "ol"], recursive=False)
            for nl in nested:
                nl.extract()
            text = self._normalize(li_clone.get_text(" ", strip=True))
            prefix = "  " * indent + (f"{idx}. " if ordered else "- ")
            lines.append(prefix + text if text else prefix.rstrip())
            for nl in li.find_all(["ul", "ol"], recursive=False):
                nested_md = self._list_to_markdown(nl, indent=indent + 1)
                if nested_md:
                    lines.append(nested_md.rstrip())
            if ordered:
                idx += 1
        return ("\n".join(lines) + "\n\n") if lines else ""

    def _text_formatted_to_markdown(self, div: Tag) -> str:
        parts: List[str] = []
        for child in div.children:
            if not isinstance(child, Tag):
                continue
            if child.name in ("ul", "ol"):
                parts.append(self._list_to_markdown(child))
            elif child.name == "table":
                parts.append(self._table_to_markdown(child))
            elif child.name == "div" and "table-wrapper" in (child.get("class") or []):
                table = child.find("table")
                if table:
                    parts.append(self._table_to_markdown(table))
            elif child.name == "div" and "embedded-entity" in (child.get("class") or []):
                fig = child.find("figure")
                if fig:
                    a = fig.find("a", href=True)
                    caption_div = fig.find("div", class_="field--name-field-caption")
                    caption = self._normalize(caption_div.get_text(" ", strip=True)) if caption_div else ""
                    img_url = (a.get("href") or "") if a else ""
                    if img_url.startswith("/"):
                        img_url = f"{self.BASE_URL}{img_url}"
                    if caption:
                        line = f"[{caption}]({img_url})\n\n" if img_url else f"*{caption}*\n\n"
                        parts.append(line)
            elif child.name == "p":
                child_clone = copy.deepcopy(child)
                self._replace_links_with_md(child_clone)
                txt = self._normalize(child_clone.get_text(" ", strip=True))
                if txt:
                    parts.append(txt + "\n\n")
            else:
                child_clone = copy.deepcopy(child)
                self._replace_links_with_md(child_clone)
                txt = self._normalize(child_clone.get_text(" ", strip=True))
                if txt:
                    parts.append(txt + "\n\n")
        return "".join(parts)

    def _render_section_node(self, node: Tag) -> str:
        parts: List[str] = []
        is_aanbeveling = "node--aanbeveling" in (node.get("class") or [])

        for child in node.children:
            if not isinstance(child, Tag):
                continue

            # Skip empty spacer divs
            if child.name == "div" and not child.get("class") and not child.get("id"):
                if not child.get_text(strip=True):
                    continue

            # Section heading (h3/h4/h5)
            if child.name in ("h3", "h4", "h5", "h6") and "section-heading" in (child.get("class") or []):
                text = self._heading_text(child)
                if text:
                    prefix = "#" * int(child.name[1])
                    label = f" **[Aanbeveling]**" if is_aanbeveling else ""
                    parts.append(f"\n{prefix}{label} {text}\n\n")
                continue

            # Cross-link back to samenvatting — navigation noise, skip
            if child.name == "a" and "summary-main-text-crosslink" in (child.get("class") or []):
                continue

            if child.name == "div" and "text-formatted" in (child.get("class") or []):
                parts.append(self._text_formatted_to_markdown(child))
                continue

            # 'Details / Waarom deze aanbeveling?' collapsible
            if child.name == "div" and "more-info-wrapper" in (child.get("class") or []):
                explanation_div = child.find("div", class_="text-formatted")
                if explanation_div:
                    txt = self._text_formatted_to_markdown(explanation_div)
                    if txt.strip():
                        parts.append(f"> **Toelichting:** {txt.strip()}\n\n")
                continue

        return "".join(parts)

    def _render_collapsible_section(self, wrapper: Tag) -> str:
        parts: List[str] = []

        h2 = wrapper.find("h2", class_="section-heading")
        if h2:
            text = self._heading_text(h2)
            if text:
                parts.append(f"\n## {text}\n\n")

        collapsible = wrapper.find("div", class_="collapsible")
        if not collapsible:
            return "".join(parts)

        for section_node in collapsible.find_all("div", class_="node--type--section", recursive=False):
            parts.append(self._render_section_node(section_node))

        return "".join(parts)

    def _render_field(self, field_div: Tag) -> str:
        parts: List[str] = []

        wrappers = field_div.find_all("div", class_="collapsible-section-wrapper", recursive=False)
        if wrappers:
            for wrapper in wrappers:
                parts.append(self._render_collapsible_section(wrapper))
            return "".join(parts)

        # Literature field: h2 + collapsible directly (no collapsible-section-wrapper)
        h2 = field_div.find("h2")
        if h2:
            parts.append(f"\n## {self._heading_text(h2)}\n\n")
        collapsible = field_div.find("div", class_="collapsible")
        if collapsible:
            ol = collapsible.find("ol")
            if ol:
                parts.append(self._list_to_markdown(ol))

        return "".join(parts)

    def _extract_metadata(self, article: Tag) -> Dict[str, Optional[str]]:
        top = article.find("div", class_="top")
        meta: Dict[str, Optional[str]] = {
            "type_label": None,
            "knr": None,
            "published": None,
            "last_updated": None,
        }
        if not top:
            return meta

        label_span = top.find("span", class_="label")
        meta["type_label"] = self._normalize(label_span.get_text()) if label_span else None

        dl = top.find("dl", class_="meta-data")
        if dl:
            for dt in dl.find_all("dt"):
                key = self._normalize(dt.get_text()).lower()
                dd = dt.find_next_sibling("dd")
                if not dd:
                    continue
                val = self._normalize(dd.get_text())
                # Strip repeated label prefix e.g. "Gepubliceerd: Gepubliceerd: mei 2021"
                val = re.sub(r"^[^:]+:\s*", "", val).strip()
                if "knr" in key:
                    meta["knr"] = val
                elif "gepubliceerd" in key:
                    meta["published"] = val
                elif "aanpassing" in key:
                    meta["last_updated"] = val

        return meta

    def scrape_to_markdown(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        html = self.fetch_url(url)
        if not html:
            return None, None

        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article", class_="node--type-guideline")
        if not article:
            self._log(f"No guideline article found at {url}")
            return None, None

        meta = self._extract_metadata(article)

        h1 = article.find("h1", class_="page-title")
        title = self._normalize(h1.get_text()) if h1 else None
        if not title:
            return None, None

        parts: List[str] = [f"# {title}\n\n"]

        meta_lines = []
        if meta["type_label"]:
            meta_lines.append(f"**Type:** {meta['type_label']}")
        if meta["knr"]:
            meta_lines.append(f"**KNR:** {meta['knr']}")
        if meta["published"]:
            meta_lines.append(f"**Gepubliceerd:** {meta['published']}")
        if meta["last_updated"]:
            meta_lines.append(f"**Laatste aanpassing:** {meta['last_updated']}")
        # Voor standaarden linken we direct naar de volledige tekst tab
        bron_url = f"{url}#volledige-tekst" if "/standaarden/" in url else url
        meta_lines.append(f"**Bron:** {bron_url}")
        parts.append("  \n".join(meta_lines) + "\n\n")

        author_dl = article.find("dl", class_="author-list")
        if author_dl:
            authors = self._normalize(author_dl.get_text(" ", strip=True))
            authors = re.sub(r"^NHG-werkgroep\s*", "", authors)
            if authors:
                parts.append(f"**NHG-werkgroep:** {authors}\n\n")

        # col-text is the content column; col-util is the utility bar
        col_main = article.find("div", class_="col-text")
        if not col_main:
            return title, "".join(parts)

        main_text_field = col_main.find("div", class_="field--name-guideline-main-text")
        if main_text_field:
            parts.append("---\n\n")
            parts.append(self._render_field(main_text_field))

        lit_field = col_main.find("div", class_="field--name-literature")
        if lit_field:
            parts.append("---\n\n")
            parts.append(self._render_field(lit_field))

        return title, "".join(parts)