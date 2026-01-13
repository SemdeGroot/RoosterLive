# core/utils/kompasscraper/scraper.py

import hashlib
import time
import random
import os
import tempfile
import re
from typing import Optional, List, Dict, Set, Tuple
import gc
import copy
from collections import deque

from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString
from fake_useragent import UserAgent
from google import genai
from curl_cffi import requests
from tabulate import tabulate

from core.models import ScrapedPage

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

class KompasScraper:
    def __init__(
        self,
        debug_limit: Optional[int] = None,
        verbose: Optional[bool] = None,
        tmp_dump_count: Optional[int] = None,
        tmp_dump_dir: Optional[str] = None,
    ):
        self.base_url = "https://www.farmacotherapeutischkompas.nl"
        self.debug_limit = debug_limit

        # logs: standaard stil (geen debug spam)
        if verbose is None:
            verbose = os.getenv("FK_VERBOSE", "0").strip() in ("1", "true", "True", "yes", "YES")
        self.verbose = verbose

        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.store_id = os.getenv("GEMINI_STORE_ID")

        self.ua = UserAgent()
        self.session = requests.Session(impersonate="chrome120")

        # ---- Rate limiting / politeness defaults ----
        self.max_preparaat_groups_per_run = int(os.getenv("FK_PREPARAAT_GROUPS_PER_RUN", "9999"))
        self.discovery_sleep_min = float(os.getenv("FK_DISCOVERY_SLEEP_MIN", "0.5"))
        self.discovery_sleep_max = float(os.getenv("FK_DISCOVERY_SLEEP_MAX", "1.5"))

        # Infinite scroll autoload
        self.max_groep_autoload_pages = int(os.getenv("FK_GROEP_AUTOLOAD_PAGES_MAX", "999"))

        # Extractie: max aantal inject fetches per pagina
        self.max_inject_fetches_per_page = int(os.getenv("FK_EXTRACT_INJECT_MAX", "100"))

        # md dumps in MEDIA/tmp/kompasgpt (via default_storage)
        if tmp_dump_count is None:
            tmp_dump_count = int(os.getenv("FK_TMP_DUMP_COUNT", "3"))
        self.tmp_dump_count = max(0, tmp_dump_count)

        # map binnen MEDIA_ROOT (storage path)
        if tmp_dump_dir is None:
            tmp_dump_dir = os.getenv("FK_TMP_DUMP_DIR", "")
        # default: tmp/kompasgpt
        self.tmp_dump_dir = (tmp_dump_dir.strip() or "tmp/kompasgpt").strip("/")

        self._tmp_dump_written = 0

        # simpele cache om dubbele fetches te vermijden binnen één run
        self._html_cache = deque(maxlen=5)

    # ----------------------------
    # LOG
    # ----------------------------
    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    # ----------------------------
    # HTTP
    # ----------------------------
    def get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            "Referer": self.base_url,
        }

    def _polite_sleep(self, where: str = "") -> None:
        if self.debug_limit:
            lo, hi = 0.15, 0.35
        else:
            lo, hi = self.discovery_sleep_min, self.discovery_sleep_max

        s = random.uniform(lo, hi)
        self._log(f"Polite sleep ({where}): {s:.2f}s" if where else f"Polite sleep: {s:.2f}s")
        time.sleep(s)

    def _parse_retry_after_seconds(self, value: str) -> Optional[int]:
        if not value:
            return None
        v = value.strip()
        return int(v) if v.isdigit() else None

    def _exp_backoff_seconds(self, attempt: int, base: float, cap: float) -> float:
        # exponential backoff: base * 2^attempt, met jitter
        raw = min(cap, base * (2 ** attempt))
        jitter = random.uniform(0.8, 1.2)
        return max(0.0, raw * jitter)
    
    def _is_transient_gemini_error(self, e: Exception) -> bool:
        msg = str(e).lower()

        # voorkom dat eigen poll timeout eindeloos retried
        if "poll timeout" in msg or "operation poll timeout" in msg:
            return False

        # status codes die vrijwel altijd transient zijn
        transient_codes = ("429", "500", "502", "503", "504")
        if any(code in msg for code in transient_codes):
            return True

        # alleen hele specifieke signalen (niet te brede woorden)
        transient_markers = (
            "too many requests",
            "rate limit",
            "quota exceeded",
            "resource_exhausted",
            "unavailable",
            "overloaded",
            "internal error",
            "deadline exceeded",
        )
        return any(m in msg for m in transient_markers)
    
    _ATC_RE = re.compile(r"\b[A-Z]\d{2}[A-Z]{2}\d{2}\b")

    def _extract_atc_from_markdown(self, md: str) -> Optional[str]:
        """
        Verwacht header zoals:
        *Geneesmiddel | 11-beta-hydroxylaseremmers | V04CD01*
        """
        if not md:
            return None

        head = "\n".join(md.splitlines()[:80])  # header zit vrijwel altijd bovenin
        if "Geneesmiddel" not in head:
            return None

        m = self._ATC_RE.search(head)
        return m.group(0) if m else None

    def fetch_url(self, url: str) -> Optional[str]:
        # Check mini-cache (deque)
        for cached_url, content in self._html_cache:
            if cached_url == url:
                return content

        # Config via env (veilige defaults)
        max_retries = int(os.getenv("FK_HTTP_MAX_RETRIES", "3"))
        timeout_s = float(os.getenv("FK_HTTP_TIMEOUT", "20"))
        backoff_5xx_base = float(os.getenv("FK_BACKOFF_5XX_BASE", "3"))
        backoff_5xx_cap  = float(os.getenv("FK_BACKOFF_5XX_CAP", "90"))
        backoff_429_base = float(os.getenv("FK_BACKOFF_429_BASE", "30"))
        backoff_429_cap  = float(os.getenv("FK_BACKOFF_429_CAP", "300"))

        last_err = None

        for attempt in range(max_retries + 1):
            self._polite_sleep(where="fetch_url")

            try:
                res = self.session.get(url, headers=self.get_headers(), timeout=timeout_s)
                status = res.status_code

                if status == 429:
                    ra = self._parse_retry_after_seconds(res.headers.get("Retry-After", ""))
                    wait = float(ra) if ra is not None else self._exp_backoff_seconds(attempt, backoff_429_base, backoff_429_cap)
                    self._log(f"HTTP 429 voor {url}. Backoff: {wait:.1f}s")
                    time.sleep(wait)
                    continue

                if status in (500, 502, 503, 504):
                    wait = self._exp_backoff_seconds(attempt, backoff_5xx_base, backoff_5xx_cap)
                    self._log(f"HTTP {status} voor {url}. Backoff: {wait:.1f}s")
                    time.sleep(wait)
                    continue

                if status in (400, 401, 403, 404):
                    return None

                res.raise_for_status()
                html_text = res.text
                
                # Opslaan in mini-cache
                self._html_cache.append((url, html_text))
                return html_text

            except Exception as e:
                last_err = e
                wait = self._exp_backoff_seconds(attempt, backoff_5xx_base, backoff_5xx_cap)
                time.sleep(wait)

        self._log(f"Fetch failed voor {url}: {last_err}")
        return None

    # ----------------------------
    # URL helpers
    # ----------------------------
    def _abs_url(self, href: str) -> Optional[str]:
        if not href:
            return None
        href = href.strip()
        if href.startswith("#"):
            return None
        if href.startswith("/"):
            return f"{self.base_url}{href}"
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return f"{self.base_url}/{href.lstrip('/')}"

    def _clean_fk_url(self, href: str) -> Optional[str]:
        """
        FK heeft soms trailing ';' achter URLs (bv ...#medicine-listing;).
        """
        if not href:
            return None
        href = href.strip()
        while href.endswith(";"):
            href = href[:-1].strip()
        return self._abs_url(href)

    def _dedupe_keep_order(self, items: List[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for it in items:
            u = it.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(it)
        return out

    # ----------------------------
    # DOM helpers
    # ----------------------------
    def _get_main_container(self, soup: BeautifulSoup) -> Tag:
        return (
            soup.select_one("#main")
            or soup.select_one("main")
            or soup.select_one("article")
            or soup.select_one("body")
            or soup
        )

    def _normalize_text(self, txt: str) -> str:
        txt = (txt or "").replace("\xa0", " ")
        return " ".join(txt.split()).strip()

    def _heading_prefix(self, tag_name: str) -> str:
        """
        h1 -> '#', h2 -> '##', ... h6 -> '######'
        """
        if not tag_name or not re.fullmatch(r"h[1-6]", tag_name):
            return ""
        level = int(tag_name[1])
        return "#" * level

    def _get_h2_anchor(self, h2: Tag) -> Optional[str]:
        if h2.get("id"):
            return h2["id"].strip()
        a = h2.find("a", id=True)
        if a and a.get("id"):
            return a["id"].strip()
        a = h2.find("a", attrs={"name": True})
        if a and a.get("name"):
            return a["name"].strip()
        return None

    def _replace_links_with_md(self, node: Tag) -> None:
        """
        Zet <a> om naar markdown links in-place (zodat get_text() MD behoudt).
        """
        for a in node.find_all("a", href=True):
            text = self._normalize_text(a.get_text(" ", strip=True)) or "link"
            href = self._clean_fk_url(a.get("href", ""))
            if href:
                a.replace_with(NavigableString(f"[{text}]({href})"))
            else:
                a.replace_with(NavigableString(text))

    # ============================
    # DISCOVERY (LOGICA ONGEWIJZIGD)
    # ============================

    def _discover_preparaat_links(self, soup: BeautifulSoup) -> List[str]:
        main = self._get_main_container(soup)
        results = main.select_one("#results-list") or main
        directory = results.select_one("#directory") or results

        sections = directory.select("section")
        self._log(f"Preparaat discovery: {len(sections)} sections gevonden in #directory")

        cap = max(1, self.debug_limit) if self.debug_limit else self.max_preparaat_groups_per_run
        if len(sections) > cap:
            self._log(f"Preparaat discovery: cap actief -> {cap}/{len(sections)} sections uitklappen deze run")
            sections = sections[:cap]

        medicine_urls: List[str] = []

        for idx, sec in enumerate(sections, start=1):
            label = (sec.get("data-label") or "").strip()
            h3 = sec.select_one("h3")
            h3_txt = h3.get_text(strip=True) if h3 else ""
            self._log(f"Preparaat section [{idx}/{len(sections)}] data-label='{label}' h3='{h3_txt}'")

            ul = sec.select_one("ul.link-list")
            if ul:
                for a in ul.select("li a[href]"):
                    href = a.get("href", "")
                    if "/bladeren/preparaatteksten/" in href and "/bladeren/preparaatteksten/groep/" not in href:
                        u = self._clean_fk_url(href)
                        if u:
                            medicine_urls.append(u)
                continue

            load_a = sec.select_one("p.collapsible-loading-message a[href]")
            if not load_a:
                continue

            load_url = self._clean_fk_url(load_a.get("href", ""))
            if not load_url:
                continue

            self._log(f"Preparaat discovery: fetch load-url: {load_url}")
            sub_html = self.fetch_url(load_url)
            if not sub_html:
                continue

            sub_soup = BeautifulSoup(sub_html, "html.parser")
            sub_main = self._get_main_container(sub_soup)

            listing = sub_main.select_one("#medicine-listing") or sub_main
            ul2 = listing.select_one("ul.link-list") or listing.select_one("ul")
            if not ul2:
                continue

            for a in ul2.select("li a[href]"):
                href = a.get("href", "")
                if "/bladeren/preparaatteksten/" in href and "/bladeren/preparaatteksten/groep/" not in href:
                    u = self._clean_fk_url(href)
                    if u:
                        medicine_urls.append(u)

            self._polite_sleep(where="preparaat load-url")

        seen = set()
        medicine_urls = [u for u in medicine_urls if not (u in seen or seen.add(u))]
        return medicine_urls

    def _find_groep_autoload_links(self, soup: BeautifulSoup) -> List[str]:
        main = self._get_main_container(soup)
        results = main.select_one("#results-list") or main
        urls = []
        for a in results.select("a.pat-inject[href]"):
            href = (a.get("href") or "").strip()
            if "/bladeren/groepsteksten/alfabet/" in href:
                u = self._clean_fk_url(href)
                if u:
                    urls.append(u)
        seen = set()
        return [u for u in urls if not (u in seen or seen.add(u))]

    def _parse_groep_links_from_directory(self, soup: BeautifulSoup) -> List[str]:
        main = self._get_main_container(soup)
        results = main.select_one("#results-list") or main

        article = (
            results.select_one("article#directory-alfabet-groepsteksten")
            or results.select_one("article")
            or results
        )
        sections = article.select("section.block") or results.select("section.block")

        urls: List[str] = []
        for sec in sections:
            ul = sec.select_one("ul.link-list") or sec.select_one("ul")
            if not ul:
                continue
            for a in ul.select("li a[href]"):
                u = self._clean_fk_url(a.get("href", ""))
                if u and "/bladeren/groepsteksten/" in u:
                    urls.append(u)
        return urls

    def _discover_groep_links(self, soup: BeautifulSoup) -> List[str]:
        urls = self._parse_groep_links_from_directory(soup)

        queue = self._find_groep_autoload_links(soup)
        visited: Set[str] = set()
        fetched = 0

        while queue and fetched < self.max_groep_autoload_pages:
            load_url = queue.pop(0)
            if load_url in visited:
                continue
            visited.add(load_url)
            fetched += 1

            html = self.fetch_url(load_url)
            if not html:
                continue

            sub_soup = BeautifulSoup(html, "html.parser")
            new_urls = self._parse_groep_links_from_directory(sub_soup)
            if new_urls:
                urls.extend(new_urls)

            new_loaders = self._find_groep_autoload_links(sub_soup)
            for u in new_loaders:
                if u not in visited and u not in queue:
                    queue.append(u)

            self._polite_sleep(where="groep autoload")

            if self.debug_limit and fetched >= max(1, self.debug_limit):
                break

        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]
        return urls

    def _discover_indicatie_links(self, soup: BeautifulSoup) -> List[str]:
        main = self._get_main_container(soup)
        results = main.select_one("#results-list") or main
        sections = results.select("article.directory section.block") or results.select("section.block")

        urls: List[str] = []
        for sec in sections:
            ul = sec.select_one("ul.link-list") or sec.select_one("ul")
            if not ul:
                continue
            for a in ul.select("li a[href]"):
                u = self._clean_fk_url(a.get("href", ""))
                if u and "/bladeren/indicatieteksten/" in u:
                    urls.append(u)

        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]
        return urls

    def discovery_phase(self, categories: Optional[List[str]] = None) -> List[Dict]:
        all_start_urls = {
            "preparaat": f"{self.base_url}/bladeren/preparaatteksten/groep",
            "groep": f"{self.base_url}/bladeren/groepsteksten/alfabet",
            "indicatie": f"{self.base_url}/bladeren/indicatieteksten/alfabet",
        }
        
        # Als categories None is, pakken we alles. Anders alleen de gevraagde.
        selected_cats = categories if categories else list(all_start_urls.keys())

        final_queue: List[Dict] = []

        for cat in selected_cats:
            start_url = all_start_urls.get(cat)
            if not start_url:
                continue
                
            html = self.fetch_url(start_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            if cat == "preparaat":
                urls = self._discover_preparaat_links(soup)
            elif cat == "groep":
                urls = self._discover_groep_links(soup)
            else:
                urls = self._discover_indicatie_links(soup)

            cat_links = [{"url": u, "category": cat} for u in urls]
            cat_links = self._dedupe_keep_order(cat_links)

            if self.debug_limit:
                final_queue.extend(cat_links[:2])
            else:
                final_queue.extend(cat_links)
            
            # Directe opruiming na elke categorie discovery
            del soup
            gc.collect()

        final_queue = self._dedupe_keep_order(final_queue)
        return final_queue

    # ============================
    # EXTRACTIE -> MARKDOWN (LOGICA GOED)
    # ============================

    def _should_skip_tag(self, tag: Tag) -> bool:
        if not isinstance(tag, Tag):
            return True

        if tag.name in ("script", "style", "noscript", "template"):
            return True
        if tag.name in ("nav", "aside", "footer"):
            return True

        cls = " ".join(tag.get("class", []))
        if any(x in cls for x in ["pat-toolbar", "bumper"]):
            return True

        if tag.name in ("ul", "ol") and "link-list" in cls and "col-4" in cls:
            return True

        return False

    def _table_to_markdown(self, table: Tag) -> str:
        def cell_text(td: Tag) -> str:
            return self._normalize_text(td.get_text(" ", strip=True))

        header: Optional[List[str]] = None
        body_rows: List[List[str]] = []

        thead = table.find("thead")
        if thead:
            tr = thead.find("tr")
            if tr:
                header_cells = tr.find_all(["th", "td"])
                if header_cells:
                    header = [cell_text(c) for c in header_cells]

        for tr in table.find_all("tr"):
            if thead and tr.find_parent("thead") is not None:
                continue
            cells = tr.find_all(["th", "td"])
            row = [cell_text(c) for c in cells]
            if any(row):
                body_rows.append(row)

        if header is None and body_rows:
            first_tr = table.find("tr")
            has_th = bool(first_tr and first_tr.find("th"))
            if has_th:
                header = body_rows[0]
                body_rows = body_rows[1:]

        if header is None and not body_rows:
            return ""

        coln = max([len(header) if header else 0] + [len(r) for r in body_rows]) or 1
        if header is None:
            header = [f"Kolom {i+1}" for i in range(coln)]
        header = (header + [""] * (coln - len(header)))[:coln]

        norm_rows = []
        for r in body_rows:
            r = (r + [""] * (coln - len(r)))[:coln]
            norm_rows.append(r)

        md = tabulate(norm_rows, headers=header, tablefmt="github")
        return md + "\n\n"

    def _list_to_markdown(self, list_tag: Tag, indent: int = 0) -> str:
        if not isinstance(list_tag, Tag) or list_tag.name not in ("ul", "ol"):
            return ""

        ordered = list_tag.name == "ol"
        lines: List[str] = []
        idx = 1

        for li in list_tag.find_all("li", recursive=False):
            li_clone = copy.deepcopy(li)
            if not isinstance(li_clone, Tag):
                continue

            self._replace_links_with_md(li_clone)

            nested_lists = li_clone.find_all(["ul", "ol"], recursive=False)
            for nl in nested_lists:
                nl.extract()

            text = self._normalize_text(li_clone.get_text(" ", strip=True))
            prefix = ("  " * indent) + (f"{idx}. " if ordered else "- ")
            lines.append(prefix + text if text else prefix.rstrip())

            for nl in li.find_all(["ul", "ol"], recursive=False):
                nested_md = self._list_to_markdown(nl, indent=indent + 1)
                if nested_md:
                    lines.append(nested_md.rstrip())

            if ordered:
                idx += 1

        return ("\n".join([ln for ln in lines if ln is not None]) + "\n\n") if lines else ""

    def _extract_injected_content(self, href: str, base_url: str, budget: Dict[str, int], depth: int) -> str:
        if depth >= 2:
            return ""

        full = self._clean_fk_url(href)
        if not full:
            return ""

        if budget["remaining"] <= 0:
            return f"[Laden…]({full})\n\n"

        budget["remaining"] -= 1

        html = self.fetch_url(full)
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")
        main_content = soup.select_one("#main-content")
        if not main_content:
            main = self._get_main_container(soup)
            main_content = main.select_one("article") or main

        anchor = None
        if "#" in full:
            anchor = full.split("#", 1)[1].strip() or None

        if anchor:
            target = main_content.select_one(f"#{anchor}")
            if target and isinstance(target, Tag) and target.name == "h2":
                title = self._normalize_text(target.get_text(" ", strip=True))
                md = f"\n### {title}\n\n"
                md += self._render_section_after_heading(
                    heading=target,
                    base_url=full,
                    budget=budget,
                    depth=depth + 1,
                )
                self._polite_sleep(where="extract inject")
                return md

        md = "\n### Ingevoegde content\n\n"
        md += self._node_to_markdown(main_content, base_url=full, budget=budget, depth=depth + 1)
        self._polite_sleep(where="extract inject")
        return md

    def _node_to_markdown(self, node: Tag, base_url: str, budget: Dict[str, int], depth: int) -> str:
        if not isinstance(node, Tag) or self._should_skip_tag(node):
            return ""

        # 1. Headers (h1 t/m h6)
        if re.fullmatch(r"h[1-6]", node.name or ""):
            prefix = self._heading_prefix(node.name)
            node_copy = copy.deepcopy(node) # Lichte kopie in plaats van nieuwe BS instantie
            self._replace_links_with_md(node_copy)
            t = self._normalize_text(node_copy.get_text(" ", strip=True))
            if t:
                return f"\n{prefix} {t}\n\n"
            return ""

        # 2. Paragrafen
        if node.name == "p":
            cls = " ".join(node.get("class", []))
            # Check voor 'Ingevoegde' content (pat-inject)
            if "collapsible-loading-message" in cls:
                a = node.select_one("a[href]")
                if a:
                    return self._extract_injected_content(
                        a.get("href", ""), base_url=base_url, budget=budget, depth=depth
                    )
                return ""

            node_copy = copy.deepcopy(node)
            self._replace_links_with_md(node_copy)
            txt = self._normalize_text(node_copy.get_text(" ", strip=True))
            if txt:
                return f"{txt}\n\n"
            return ""

        # 3. Blockquotes
        if node.name == "blockquote":
            node_copy = copy.deepcopy(node)
            self._replace_links_with_md(node_copy)
            txt = self._normalize_text(node_copy.get_text(" ", strip=True))
            if txt:
                return "\n".join([f"> {line}" for line in txt.splitlines()]) + "\n\n"
            return ""

        # 4. Code blokken
        if node.name == "pre":
            code = node.get_text("\n", strip=False).rstrip("\n").strip("\n")
            if code.strip():
                return f"```\n{code}\n```\n\n"
            return ""

        # 5. Lijsten (ul/ol) - maakt intern gebruik van helpers
        if node.name in ("ul", "ol"):
            return self._list_to_markdown(node)

        # 6. Tabellen
        if node.name == "table":
            return self._table_to_markdown(node)

        # 7. Losse links met injectie
        if node.name == "a":
            cls = " ".join(node.get("class", []))
            if "pat-inject" in cls and node.get("href"):
                return self._extract_injected_content(
                    node.get("href", ""), base_url=base_url, budget=budget, depth=depth
                )

        # 8. Breaks & Rules
        if node.name == "br":
            return "\n"
        if node.name == "hr":
            return "\n---\n\n"

        # 9. Recursie voor kinderen (Containers zoals div, section, etc.)
        out = ""
        for child in node.children:
            if isinstance(child, Tag):
                if self._should_skip_tag(child):
                    continue
                out += self._node_to_markdown(child, base_url=base_url, budget=budget, depth=depth)

        # 10. Fallback voor containers die directe tekst bevatten zonder specifieke tags
        if not out.strip() and node.name in ("div", "section", "article", "span"):
            node_copy = copy.deepcopy(node)
            self._replace_links_with_md(node_copy)
            txt = self._normalize_text(node_copy.get_text(" ", strip=True))
            if txt and len(txt) >= 3:
                return f"{txt}\n\n"

        return out

    def _render_section_after_heading(self, heading: Tag, base_url: str, budget: Dict[str, int], depth: int) -> str:
        parent = heading.parent if isinstance(heading, Tag) else None
        if not isinstance(parent, Tag):
            return ""

        parts: List[str] = []
        started = False

        for sib in parent.children:
            if not isinstance(sib, Tag):
                continue

            if sib is heading:
                started = True
                continue

            if not started:
                continue

            if sib.name == "h2":
                break

            if self._should_skip_tag(sib):
                continue

            parts.append(self._node_to_markdown(sib, base_url=base_url, budget=budget, depth=depth))

        md = "".join(parts).strip()
        return (md + "\n\n") if md else ""

    def _sections_from_main_content(self, main_content: Tag, base_url: str, budget: Dict[str, int], depth: int) -> str:
        md = ""

        page_head = main_content.select_one("#page-head")
        all_h2 = []
        for h2 in main_content.find_all("h2"):
            if page_head and h2.find_parent(id="page-head"):
                continue
            all_h2.append(h2)

        for h2 in all_h2:
            h2_text = self._normalize_text(h2.get_text(" ", strip=True))
            if not h2_text:
                continue

            # H2 titel (zonder anchor/highlight)
            md += f"\n## {h2_text}\n\n"

            # Bron direct onder elke H2 (bewust zonder anchor)
            md += f"**Bron:** {base_url}\n\n"

            section_md = self._render_section_after_heading(
                heading=h2,
                base_url=base_url,
                budget=budget,
                depth=depth,
            )

            if not section_md.strip():
                nxt = h2.find_next_sibling()
                if isinstance(nxt, Tag) and not self._should_skip_tag(nxt):
                    section_md = self._node_to_markdown(nxt, base_url=base_url, budget=budget, depth=depth)

            if section_md.strip():
                md += section_md

        return md

    def _main_content_to_markdown(self, main_content: Tag, base_url: str) -> str:
        md = ""

        page_head = main_content.select_one("#page-head")
        if page_head:
            h1 = page_head.select_one("h1")
            if h1:
                title = self._normalize_text(h1.get_text(" ", strip=True))
                if title:
                    md += f"# {title}\n\n"

            bylines = []
            for sp in page_head.select("span.byline-item, .byline-item"):
                t = self._normalize_text(sp.get_text(" ", strip=True))
                if t and t not in bylines:
                    bylines.append(t)
            if bylines:
                md += f"*{' | '.join(bylines)}*\n\n"
        else:
            h1 = main_content.select_one("h1")
            if h1:
                title = self._normalize_text(h1.get_text(" ", strip=True))
                if title:
                    md += f"# {title}\n\n"

        md += f"**Bron:** {base_url}\n\n"

        budget = {"remaining": self.max_inject_fetches_per_page}
        md += self._sections_from_main_content(main_content, base_url=base_url, budget=budget, depth=0)
        return md

    def scrape_to_markdown(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        html = self.fetch_url(url)
        if not html:
            return None, None

        soup = BeautifulSoup(html, "html.parser")

        main_content = soup.select_one("#main-content")
        if not main_content:
            main = self._get_main_container(soup)
            main_content = main.select_one("article") or main

        md = self._main_content_to_markdown(main_content=main_content, base_url=url)

        title = "Onbekend"
        for line in md.splitlines():
            if line.startswith("# "):
                title = line.replace("# ", "", 1).strip()
                break

        return title, md

    # ============================
    # TMP DUMP
    # ============================
    def _safe_filename(self, title: str, suffix: str = ".md") -> str:
        base = (title or "onbekend").strip().lower()
        base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
        if not base:
            base = "onbekend"
        return base + suffix

    def _maybe_dump_md_to_tmp(self, title: str, md_content: str, category: Optional[str] = None) -> Optional[str]:
        """
        Schrijft md weg naar MEDIA/tmp/kompasgpt/ (default_storage).
        Returnt het storage pad (bv 'tmp/kompasgpt/20260111_120102_groep_acne_vulgaris.md').
        """
        if self._tmp_dump_written >= self.tmp_dump_count:
            return None

        ts = timezone.now().strftime("%Y%m%d_%H%M%S")
        safe = self._safe_filename(title)  # eindigt op .md
        cat = (category or "page").strip().lower()
        cat = re.sub(r"[^a-z0-9]+", "_", cat).strip("_") or "page"

        rel_path = f"{self.tmp_dump_dir}/{ts}_{cat}_{safe}"

        # Sla op via storage
        saved_path = default_storage.save(rel_path, ContentFile(md_content.encode("utf-8")))

        self._tmp_dump_written += 1
        return saved_path

    # ============================
    # GEMINI / DB
    # ============================
    def upload_to_gemini(self, title: str, content: str, source_url: str, category: str | None = None) -> bool:
        max_retries = int(os.getenv("FK_GEMINI_MAX_RETRIES", "5"))  # 6 attempts
        backoff_base = float(os.getenv("FK_GEMINI_BACKOFF_BASE", "5"))
        backoff_cap  = float(os.getenv("FK_GEMINI_BACKOFF_CAP", "120"))
        poll_interval = float(os.getenv("FK_GEMINI_POLL_INTERVAL", "4"))
        poll_timeout_s = float(os.getenv("FK_GEMINI_POLL_TIMEOUT", str(30 * 60)))  # 30 min

        atc_code = self._extract_atc_from_markdown(content)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            config = {
                "display_name": title,
                "custom_metadata": [{"key": "source_url", "string_value": source_url}],
            }
            if category:
                config["custom_metadata"].append({"key": "category", "string_value": category})
            if atc_code:
                config["custom_metadata"].append({"key": "atc", "string_value": atc_code})

            for attempt in range(max_retries + 1):
                try:
                    operation = self.client.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=self.store_id,
                        file=tmp_path,
                        config=config,
                    )

                    # Polling met retry/backoff
                    start_poll = time.time()
                    while True:
                        if getattr(operation, "done", False):
                            # Sommige SDK's zetten error op operation.error
                            op_err = getattr(operation, "error", None)
                            if op_err:
                                raise RuntimeError(f"Gemini operation error: {op_err}")
                            return True

                        if (time.time() - start_poll) > poll_timeout_s:
                            raise TimeoutError("Gemini upload operation poll timeout")

                        time.sleep(poll_interval)
                        try:
                            operation = self.client.operations.get(operation)
                        except Exception as pe:
                            if self._is_transient_gemini_error(pe):
                                wait = self._exp_backoff_seconds(attempt=min(attempt, 6), base=backoff_base, cap=backoff_cap)
                                self._log(f"Gemini poll transient error: {pe} -> retry in {wait:.1f}s")
                                time.sleep(wait)
                                continue
                            raise

                except Exception as e:
                    # Niet-transient? Meteen stoppen
                    if (attempt >= max_retries) or (not self._is_transient_gemini_error(e)):
                        self._log(f"Gemini upload fout (geen retry meer): {e}")
                        return False

                    wait = self._exp_backoff_seconds(attempt=attempt, base=backoff_base, cap=backoff_cap)
                    self._log(f"Gemini upload transient error: {e} -> retry in {wait:.1f}s (attempt {attempt+1}/{max_retries+1})")
                    time.sleep(wait)

            return False

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


    def process_url(self, item: Dict, dump_md: bool = False) -> Tuple[str, Optional[str]]:
        """
        status: "uploaded" | "unchanged" | "failed"
        """

        title, md_content = self.scrape_to_markdown(item["url"])
        if not md_content or not title:
            return "failed", None

        new_hash = hashlib.sha256(md_content.encode("utf-8")).hexdigest()
        page_obj, created = ScrapedPage.objects.get_or_create(url=item["url"])

        unchanged = (not created and page_obj.content_hash == new_hash)

        dumped_path = None
        if dump_md:
            dumped_path = self._maybe_dump_md_to_tmp(
                title=title,
                md_content=md_content,
                category=item.get("category"),
            )

        if unchanged:
            return "unchanged", dumped_path

        if self.upload_to_gemini(title, md_content, source_url=item["url"], category=item.get("category")):
            page_obj.title = title
            page_obj.category = item["category"]
            page_obj.content_hash = new_hash
            page_obj.save()
            return "uploaded", dumped_path

        return "failed", dumped_path

    # ============================
    # BATCH HELPERS (10/10/10)
    # ============================
    def process_samples(
        self,
        n_preparaat: int = 10,
        n_groep: int = 10,
        n_indicatie: int = 10,
        dump_md: bool = True,
    ) -> Dict[str, object]:
        """
        - Discovery blijft hetzelfde
        - selecteert eerste N urls per category
        - verwerkt alles (upload + db)
        - dumpt max 3 md files naar tmp (standaard) voor inspectie

        Return dict met counts + dump paths.
        """
        queue = self.discovery_phase()

        picked: List[Dict] = []
        counts = {"preparaat": 0, "groep": 0, "indicatie": 0}
        limits = {"preparaat": n_preparaat, "groep": n_groep, "indicatie": n_indicatie}

        for item in queue:
            cat = item.get("category")
            if cat not in counts:
                continue
            if counts[cat] >= limits[cat]:
                continue
            picked.append(item)
            counts[cat] += 1

            if all(counts[c] >= limits[c] for c in counts):
                break

        results = {
            "selected": counts,
            "processed": {"preparaat": 0, "groep": 0, "indicatie": 0},
            "dump_dir": f"{settings.MEDIA_URL.rstrip('/')}/{self.tmp_dump_dir}",
            "dumped_files": [],
        }

        for item in picked:
            status, dumped_path = self.process_url(item, dump_md=dump_md)
            if status == "uploaded":
                results["processed"][item["category"]] += 1
            if dumped_path:
                results["dumped_files"].append(dumped_path)

            # polite delay tussen pagina's (ook voor extract inject fetches zit al delay)
            self._polite_sleep(where="process_url")

        return results