import re
import json
import unicodedata
import urllib.parse
from pathlib import Path

import pandas as pd
import scrapy
from scrapy import Request

from dotenv import load_dotenv
import os

load_dotenv()

DESKTOP_BASE = "https://www.booking.com"  # desktop domain

# ---- Config ----
SCORE_COL = "nice_score"
DEST_COL = "site"
DEFAULT_N_SITES = 5
DEFAULT_N_HOTELS = 22  # hotels per destination (top by score on page)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_CSV = str(PROJECT_ROOT /"02-Get weather"/"sites_weather_summary.csv")

# Output file (lesson-style: delete if exists before crawling)
FILENAME = str(Path(__file__).resolve().parents[2] / "hotels.csv")


# ---------------- small utils ----------------
def canonical_url(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))
    except Exception:
        return url.split("?", 1)[0]


def abs_url(base: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base + href
    return base + "/" + href


def to_6(x):
    try:
        return round(float(str(x).replace(",", ".")), 6)
    except Exception:
        return None


def extract_hotel_id_from_url(url: str) -> str | None:
    # https://www.booking.com/hotel/fr/mercure-amiens-cathdrale.en-gb.html -> mercure-amiens-cathdrale
    try:
        path = urllib.parse.urlsplit(url).path
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "hotel":
            slug = parts[2]
            if "." in slug:
                slug = slug.split(".", 1)[0]
            return slug
    except Exception:
        pass
    return None


def short(text: str, n: int = 100) -> str:
    if not text:
        return ""
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _norm_key(s: str) -> str:
    """lowercase, remove accents, drop non-alnum for stable joins ('mont-saint-michel' == 'Mont Saint Michel')."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


class hotel_simple(scrapy.Spider):
    name = "booking_hotels"

    # Per-spider settings; gentle and overwrite CSV
    custom_settings = {
        # politeness
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 4.5,  # a bit slower to reduce bot flags
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.5,
        "AUTOTHROTTLE_MAX_DELAY": 20.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 0.3,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "COOKIES_ENABLED": True,

        # desktop UA (stable, realistic)
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept-Language": "en-GB,en;q=0.9,fr;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },

        # output
        "FEEDS": {  # overwrite each run
            FILENAME: {"format": "csv", "overwrite": True, "encoding": "utf-8-sig"},
        },
        "FEED_EXPORT_ENCODING": "utf-8-sig",  # Excel-friendly
        "LOG_LEVEL": "INFO",

        # Keep field order stable (site_id first)
        "FEED_EXPORT_FIELDS": [
            "site_id",
            "destination",
            "name",
            "lat",
            "lon",
            "url",
            "hotel_id",
            "review_score",
            "description",
            "address",
        ],
    }

    # ---------------- lifecycle ----------------
    def start_requests(self):
        # Delete existing CSV (lesson requirement)
        out = Path(FILENAME)
        if out.exists():
            out.unlink()

        # Load destinations and map {normalized site -> site_id}
        df = pd.read_csv(DEFAULT_INPUT_CSV)

        # Detect id column: prefer 'site_id', else 'id'
        id_col = None
        for c in df.columns:
            if c.lower() == "site_id":
                id_col = c
                break
        if id_col is None:
            for c in df.columns:
                if c.lower() == "id":
                    id_col = c
                    break

        if not id_col:
            self.logger.warning("No 'site_id' or 'id' column found; site_id will be blank.")
            self.site_id_map = {}
        else:
            if DEST_COL not in df.columns:
                raise ValueError(f"Expected column '{DEST_COL}' in {DEFAULT_INPUT_CSV}")
            self.site_id_map = {_norm_key(site): sid for site, sid in zip(df[DEST_COL].astype(str), df[id_col])}

        cities_arg = getattr(self, "cities", None)
        if cities_arg:
            destinations = [c.strip() for c in cities_arg.split(",") if c.strip()]
        else:
            top = df.sort_values(SCORE_COL, ascending=False).head(DEFAULT_N_SITES)
            destinations = top[DEST_COL].dropna().astype(str).tolist()

        self.logger.info(f"Destinations: {destinations}")
        self.seen_global = set()  # dedupe across all cities

        for dest in destinations:
            site_key = _norm_key(dest)
            site_id = self.site_id_map.get(site_key)
            if site_id is None:
                self.logger.info(f"[{dest}] site_id not found in CSV (key='{site_key}').")

            # We keep the hotel-only filter (ht_id=204) in ALL variants.
            urls = [
                self._build_search_url("en-gb", dest, variant="strict"),
                self._build_search_url("en-gb", dest, variant="simple"),
            ]
            # Start with the first variant; if 0 cards, we'll try the next.
            yield Request(
                urls[0],
                callback=self.parse_search,
                meta={
                    "destination": dest,
                    "site_id": site_id,
                    "variant_index": 0,
                    "variants": urls,
                    "yielded": 0,
                    "page_no": 1,
                },
                dont_filter=True,
            )

    # ---------------- URL building ----------------
    def _build_search_url(self, lang: str, ss: str, variant: str = "strict") -> str:
        """
        Always keep 'Hotels only' via ht_id=204. Use two query shapes to dodge guarded templates.
        """
        if variant == "strict":
            q = f"{ss} region, France"
            params = {
                "lang": lang,
                "group_adults": "2",
                "no_rooms": "1",
                "sb": "1",
                "ss": q,
                "ssne": q,
                "ssne_untouched": q,
                "nflt": "ht_id=204",  # hotels only
                "rows": "50",
            }
        else:  # "simple" but still hotel-only
            q = ss  # do not force ", France" in the visible query, but keep the filter
            params = {
                "lang": lang,
                "group_adults": "2",
                "no_rooms": "1",
                "sb": "1",
                "ss": q,
                "nflt": "ht_id=204",
                "rows": "50",
            }
        return f"{DESKTOP_BASE}/searchresults.html?{urllib.parse.urlencode(params)}"

    # ---------------- parsing: search (with pagination + variant retry) ----------------
    def parse_search(self, response):
        dest = response.meta["destination"]
        site_id = response.meta.get("site_id")
        variants = response.meta.get("variants") or []
        variant_index = int(response.meta.get("variant_index", 0))
        yielded = int(response.meta.get("yielded", 0))
        page_no = int(response.meta.get("page_no", 1))

        # quick guarded-page check
        txt_low = response.text.lower()
        if ("verify you are a human" in txt_low) or ("javascript is disabled" in txt_low):
            self.logger.warning(f"[{dest}] Guarded page detected on variant {variant_index}; switching variant.")
            if variant_index + 1 < len(variants):
                yield Request(
                    variants[variant_index + 1],
                    callback=self.parse_search,
                    meta={"destination": dest, "site_id": site_id, "variant_index": variant_index + 1,
                          "variants": variants, "yielded": yielded, "page_no": 1},
                    dont_filter=True,
                )
                return

        cards = response.css('[data-testid="property-card"], .sr_item')
        self.logger.info(f"[{dest}] Variant {variant_index}, page {page_no}: found {len(cards)} cards.")

        candidates = []
        for card in cards:
            href = (
                card.css('a[data-testid="title-link"]::attr(href)').get()
                or card.css('a[href*="/hotel/"]::attr(href)').get()
                or card.css('a::attr(href)').get()
                or ""
            )
            url = abs_url(DESKTOP_BASE, href)
            # not relying on /hotel/ path to decide type; final check happens on hotel page.
            canon = canonical_url(url)
            if not canon or canon in self.seen_global:
                continue
            self.seen_global.add(canon)

            # Name and rough score from the card
            card_name = (
                card.css('[data-testid="title"]::text').get()
                or card.css('a[data-testid="title-link"]::text').get()
                or card.css(".sr-hotel__name::text").get()
                or card.css("h3::text, h2::text").get()
                or ""
            )
            card_name = " ".join(card_name.split())

            txt = " ".join([b.strip() for b in card.css("::text").getall() if b.strip()])
            m = re.search(r"(?<!\d)(10(?:\.0)?|[0-9](?:[.,]\d)?)(?!\d)", txt)
            score = None
            if m:
                try:
                    score = float(m.group(1).replace(",", "."))
                except Exception:
                    score = None

            candidates.append(
                {"canon": canon, "name": card_name, "score": score, "lat": None, "lon": None}
            )

        # Sort by score desc then name, pick next batch up to what we still need
        candidates.sort(key=lambda d: (-1.0 if d["score"] is None else -d["score"], d["name"]))
        to_fetch = max(0, DEFAULT_N_HOTELS - yielded)
        for c in candidates[:to_fetch]:
            yield Request(
                c["canon"],
                callback=self.parse_hotel,
                meta={
                    "site_id": site_id,
                    "destination": dest,
                    "card_name": c["name"],
                    "canon_url": c["canon"],
                    "card_score": c["score"],
                },
                dont_filter=True,
            )
            yielded += 1

        # If we still need more hotels for this destination, paginate (still hotel-only)
        if yielded < DEFAULT_N_HOTELS:
            next_href = (
                response.css('a[aria-label="Next page"]::attr(href)').get()
                or response.css('a[rel="next"]::attr(href)').get()
                or response.css('a[aria-label*="Next"]::attr(href)').get()
                or response.css('a[data-testid="pagination-next"]::attr(href)').get()
            )
            if next_href:
                next_url = abs_url(DESKTOP_BASE, next_href)
                self.logger.info(f"[{dest}] Following next page → {next_url}")
                yield Request(
                    next_url,
                    callback=self.parse_search,
                    meta={
                        "destination": dest,
                        "site_id": site_id,
                        "variant_index": variant_index,
                        "variants": variants,
                        "yielded": yielded,
                        "page_no": page_no + 1,
                    },
                    dont_filter=True,
                )
                return

            # No next page: try the alternate query variant once (still hotel-only)
            if variant_index + 1 < len(variants):
                self.logger.info(f"[{dest}] Not enough candidates; switching to variant {variant_index + 1}.")
                yield Request(
                    variants[variant_index + 1],
                    callback=self.parse_search,
                    meta={"destination": dest, "site_id": site_id, "variant_index": variant_index + 1,
                          "variants": variants, "yielded": yielded, "page_no": 1},
                    dont_filter=True,
                )
                return

            # Ultimately, we stop if nothing else to try
            if yielded == 0:
                self.logger.warning(f"[{dest}] 0 hotel pages queued after pagination + variants (hotel-only filter was on).")

    # ---------------- parsing: hotel ----------------
    def parse_hotel(self, response):
        site_id = response.meta.get("site_id")
        dest = response.meta["destination"]
        card_name = response.meta.get("card_name") or ""
        canon_url = response.meta["canon_url"]
        card_score = response.meta.get("card_score")

        # Anti-bot / JS-disabled fallback → skip (we keep hotel-only guarantee at search level)
        txt_low = response.text.lower()
        if ("please verify you are a human" in txt_low) or ("javascript is disabled" in txt_low):
            self.logger.warning(f"[{dest}] Guarded hotel page: {canon_url}")
            return

        # Canonical may change
        can_tag = response.css('link[rel="canonical"]::attr(href)').get()
        if can_tag:
            canon_url = canonical_url(can_tag)

        # Validate hotel type + country France from page data
        if not self._is_hotel(response):
            self.logger.info(f"[{dest}] Skipping non-hotel property: {canon_url}")
            return
        if not self._is_france(response, canon_url):
            self.logger.info(f"[{dest}] Skipping non-France property: {canon_url}")
            return

        name = self._extract_name(response) or card_name

        # Coords
        lat, lon = self._extract_coords(response)

        # Score: JSON-LD if present; else card score
        page_score = self._extract_review_score(response)
        review_score = page_score if page_score is not None else card_score

        # Description (prefer hotel page)
        desc = self._extract_description(response) or ""

        # Address (JSON-LD first; else visible on page)
        address = self._extract_address(response)

        # If coords missing, try geocoding
        if (lat is None or lon is None) and address:
            lat, lon = self._geocode_with_nominatim(address, dest)
        if (lat is None or lon is None) and name:
            lat, lon = self._geocode_with_nominatim(f"{name}, {dest}", dest)

        yield {
            "site_id": "" if site_id is None else str(site_id),
            "destination": dest,
            "name": name,
            "lat": to_6(lat),
            "lon": to_6(lon),
            "url": canon_url,
            "hotel_id": extract_hotel_id_from_url(canon_url),
            "review_score": review_score,
            "description": short(desc, 100),
            "address": address,
        }

    # ---------------- helpers ----------------
    def _is_hotel(self, response) -> bool:
        """
        Decide if the property is a real Hotel (exclude B&B, aparthotel, apartment, guest house).
        Use multiple signals and accept if any strongly indicates "Hotel".
        """
        # 1) JSON-LD @type
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if isinstance(obj, dict):
                    typ = obj.get("@type")
                    if isinstance(typ, str) and typ.lower() == "hotel":
                        return True
                    if isinstance(typ, list) and any(str(t).lower() == "hotel" for t in typ):
                        return True

        html = response.text

        # 2) Booking internal JSON hints (propertyType)
        # e.g., "propertyType":"HOTEL" or "accType":"HOTEL"
        if re.search(r'"propertyType"\s*:\s*"HOTEL"', html):
            return True
        if re.search(r'"accType"\s*:\s*"HOTEL"', html):
            return True

        # 3) Breadcrumb / labels indicating "Hotel"
        breadcrumb_text = " ".join([t.strip() for t in response.css('nav, .breadcrumbs, [data-testid="breadcrumb"] ::text').getall() if t.strip()])
        if re.search(r"\bhotel(s)?\b", breadcrumb_text, flags=re.I):
            # Be careful: "Aparthotel" contains "hotel"; reject known non-hotel words.
            if re.search(r"\b(aparthotel|apartment|guest\s*house|b&b|bed\s*&\s*breakfast|residence)\b", breadcrumb_text, flags=re.I):
                pass
            else:
                return True

        # 4) Negative keywords → likely not a hotel
        negative_hits = re.search(r"\b(aparthotel|apartment|appart|résidence|residence|guest\s*house|b&b|bed\s*&\s*breakfast|maison\s*d[h’']ôtes?)\b", html, flags=re.I)
        if negative_hits:
            return False

        # Conservative default: if we don't have a positive signal, do not keep it.
        return False

    def _is_france(self, response, canon_url: str) -> bool:
        """
        Confirm the property is in France (country=FR / France).
        """
        # JSON-LD address
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if not isinstance(obj, dict):
                    continue
                addr = obj.get("address")
                if isinstance(addr, dict):
                    ctry = (addr.get("addressCountry") or "").strip()
                    if ctry:
                        ctry_low = ctry.lower()
                        if ctry_low in ("fr", "fra", "france"):
                            return True
                        else:
                            return False  # explicit non-FR
        # Fallbacks
        if "/hotel/fr/" in canon_url:
            return True
        visible_addr = " ".join([b.strip() for b in response.css('[data-testid="address"] ::text, address ::text').getall() if b.strip()])
        if "france" in visible_addr.lower():
            return True
        return False

    def _extract_name(self, response) -> str:
        # JSON-LD
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if isinstance(obj, dict) and obj.get("name"):
                    n = " ".join(str(obj["name"]).split())
                    if n:
                        return n
        # og:title
        og = response.css('meta[property="og:title"]::attr(content)').get()
        if og:
            return " ".join(og.split())
        # Fallback headers
        h = (
            response.css("h1#hp_hotel_name::text").get()
            or response.css("h1::text").get()
            or response.css("h2::text").get()
            or ""
        )
        return " ".join(h.split())

    def _extract_coords(self, response):
        import urllib.parse as _up

        # JSON-LD geo / hasMap
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if not isinstance(obj, dict):
                    continue
                geo = obj.get("geo")
                if isinstance(geo, dict) and "latitude" in geo and "longitude" in geo:
                    return geo.get("latitude"), geo.get("longitude")
                has_map = obj.get("hasMap")
                if isinstance(has_map, str):
                    try:
                        q = _up.urlsplit(has_map).query
                        params = _up.parse_qs(q)
                        for k in ("ll", "q"):
                            if k in params and params[k]:
                                latlon = params[k][0].split(",")
                                if len(latlon) == 2:
                                    return latlon[0], latlon[1]
                    except Exception:
                        pass

        html = response.text
        m = re.search(
            r'hotelCoordinates"\s*:\s*{[^}]*"latitude"\s*:\s*([-]?\d+\.\d+)[^}]*"longitude"\s*:\s*([-]?\d+\.\d+)',
            html, re.DOTALL,
        )
        if m:
            return m.group(1), m.group(2)

        mlat = re.search(r'"latitude"\s*:\s*([-]?\d+\.\d+)', html)
        mlon = re.search(r'"longitude"\s*:\s*([-]?\d+\.\d+)', html)
        if mlat and mlon:
            return mlat.group(1), mlon.group(1)

        mlat = re.search(r'"lat"\s*:\s*([-]?\d+\.\d+)', html)
        mlon = re.search(r'"lng"\s*:\s*([-]?\d+\.\d+)', html)
        if mlat and mlon:
            return mlat.group(1), mlon.group(1)

        mlat = re.search(r'data-lat="?([-]?\d+\.\d+)"?', html)
        mlon = re.search(r'data-lng="?([-]?\d+\.\d+)"?', html)
        if mlat and mlon:
            return mlat.group(1), mlon.group(1)

        og_lat = response.css('meta[property="og:latitude"]::attr(content)').get()
        og_lon = response.css('meta[property="og:longitude"]::attr(content)').get()
        if og_lat and og_lon:
            return og_lat, og_lon

        return None, None

    def _extract_review_score(self, response):
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if isinstance(obj, dict):
                    agg = obj.get("aggregateRating")
                    if isinstance(agg, dict) and agg.get("ratingValue"):
                        try:
                            return float(str(agg["ratingValue"]).replace(",", "."))
                        except Exception:
                            pass
        return None

    def _extract_description(self, response) -> str:
        # JSON-LD description
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if isinstance(obj, dict) and obj.get("description"):
                    d = " ".join(str(obj["description"]).split())
                    if d:
                        return d
        # meta description
        md = response.css('meta[name="description"]::attr(content)').get()
        if md:
            return md
        # simplest on-page fallback
        p = response.css("p::text").get()
        return p or ""

    def _extract_address(self, response) -> str:
        """
        Prefer JSON-LD postal address; else try visible address blocks on the page.
        Returns a compact single-line address string.
        """
        # 1) JSON-LD
        for block in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(block.strip())
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if not isinstance(obj, dict):
                    continue
                addr = obj.get("address")
                if isinstance(addr, dict):
                    parts = []
                    for k in ("streetAddress", "postalCode", "addressLocality", "addressRegion", "addressCountry"):
                        v = addr.get(k)
                        if v:
                            parts.append(str(v).strip())
                    if parts:
                        return " ".join(" ".join(parts).split())

        # 2) Common visible address containers
        sel = response.css('[data-node_tt_id="location_score_tooltip"] ::text, \
                            [data-testid="address"] ::text, \
                            #showMap2 ::text, \
                            .hp_address_subtitle ::text, \
                            address ::text')
        bits = [b.strip() for b in sel.getall() if b.strip()]
        if bits:
            return " ".join(" ".join(bits).split())

        # 3) Fallback: a single meta if present
        meta_addr = response.css('meta[itemprop="address"]::attr(content)').get()
        if meta_addr:
            return " ".join(meta_addr.split())

        return ""

    def _geocode_with_nominatim(self, query: str, city_hint: str = ""):
        """
        Nominatim lookup using a detailed address or name + city.
        Returns (lat, lon) as strings if found, else (None, None).
        """
        try:
            import requests

            # Load your email from environment
            email = os.getenv("NOMINATIM_EMAIL", "")
            ua = f"hotel_simple_scraper/1.0 (+{email})"

            q = query if query else city_hint
            if city_hint and city_hint.lower() not in q.lower():
                q = f"{q}, {city_hint}"

            r = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": ua},
                timeout=15,
            )

            data = r.json()
            if isinstance(data, list) and data:
                lat = data[0].get("lat")
                lon = data[0].get("lon")
                return lat, lon

        except Exception:
            pass

        return None, None
