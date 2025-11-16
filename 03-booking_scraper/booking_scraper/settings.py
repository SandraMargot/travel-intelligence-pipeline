BOT_NAME = "booking_scraper"

SPIDER_MODULES = ["booking_scraper.spiders"]
NEWSPIDER_MODULE = "booking_scraper.spiders"

# -------- Crawl politeness / stability --------
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 2.0  # gentle pacing for Booking
DOWNLOAD_TIMEOUT = 30

# Keep requests simple/stateless; avoid cookie-based challenges
COOKIES_ENABLED = False

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408, 403]

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 10

# -------- Output --------
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"

# Make sure exported CSVs (from -O/-o or FEEDS) follow the spider’s field order
FEED_EXPORT_FIELDS = [
    "destination", "name", "lat", "lon", "url", "hotel_id", "review_score", "description"
]

# Optionally allow logging/saving anti-bot pages for troubleshooting in the spider
HTTPERROR_ALLOW_ALL = False
# If you want to capture and inspect challenge pages, flip to True or add:
# HTTPERROR_ALLOWED_CODES = [403, 429, 503]

# -------- User-Agent & headers (mobile HTML from m.booking.com) --------
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    # spider appends lang param in URLs; this helps server-side locale too
    "Accept-Language": "en-GB,en;q=0.8",
    # A neutral referer often lowers the chance of a bot challenge on detail pages
    "Referer": "https://www.booking.com/",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
    "Cookie": 'bkng_privacy={"consent":{"necessary":true,"preferences":true,"statistics":true,"marketing":false}}',
}

# -------- Force plain Scrapy (Playwright OFF) --------
DOWNLOAD_HANDLERS = {
    "http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
    "https": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
}

# Use default Twisted reactor (no asyncio reactor)
TWISTED_REACTOR = None

# -------- Middleware / Pipelines (defaults) --------
# DOWNLOADER_MIDDLEWARES = { }
# SPIDER_MIDDLEWARES = { }
# ITEM_PIPELINES = { }

# -------- Scrapy 2.7+ compatibility --------
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"