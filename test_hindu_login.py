"""
Focused end-to-end test: Hindu login → cookie save → article scrape.
Run from backend/ directory: python test_hindu_login.py
"""

import asyncio
import sys
import os

# Load .env
from dotenv import load_dotenv

load_dotenv()
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.services.playwright_session import PlaywrightSessionManager
from app.services.hindu_playwright_scraper import HinduPlaywrightScraper


async def main():
    print("=" * 60)
    print("Hindu End-to-End Test")
    print("=" * 60)

    email = settings.HINDU_EMAIL
    password = settings.HINDU_PASSWORD

    if not email or not password:
        print("ERROR: HINDU_EMAIL or HINDU_PASSWORD not set in .env")
        return

    print(f"\nCredentials loaded: {email}")

    mgr = PlaywrightSessionManager()

    try:
        print("\n[1/3] Checking for existing cookies...")
        existing_state = await mgr._load_cookies_from_supabase("hindu")
        if existing_state:
            print("      OK: Found existing cookies in Supabase, skipping login")
        else:
            print("      No cookies found, logging in...")
            await mgr.login_hindu(email=email, password=password)
            print("      OK: Login successful + cookies saved to Supabase")

        print("\n[2/3] Scraping articles...")
        scraper = HinduPlaywrightScraper(mgr)
        articles = await scraper.scrape_editorials()

        print(f"\n{'=' * 60}")
        print(f"RESULT: {len(articles)} articles fetched")
        print("=" * 60)

        if articles:
            from collections import Counter
            by_section = Counter(a.get('section') for a in articles)
            print('\nPer-section breakdown:')
            for sec, count in sorted(by_section.items()):
                print(f'  {sec:15s}: {count} articles')
            print('\nSample (first 2 per section):')
            shown: Counter = Counter()
            for a in articles:
                sec = a.get('section', '?')
                if shown[sec] >= 2:
                    continue
                shown[sec] += 1
                title = a.get('title', 'no title')[:65]
                title_safe = title.encode('ascii', 'replace').decode('ascii')
                content_len = len(a.get('content', ''))
                print(f'  [{sec}] {title_safe}')
                print(f'    content: {content_len} chars')
        else:
            print('  No articles returned -- check logs above')

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await mgr.close()
        print("\n[Done] Browser closed.")


if __name__ == "__main__":
    asyncio.run(main())
