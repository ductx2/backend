#!/usr/bin/env python3
"""
Debug script to test Drishti IAS content extraction directly
"""
import asyncio
import requests
import os
import sys
sys.path.append('.')

from app.services.drishti_scraper import DrishtiScraper

async def test_extraction():
    """Test the extraction process step by step"""
    
    # Test URL for today
    test_url = "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/30-08-2025"
    
    print(f"[DEBUG] Testing extraction from: {test_url}")
    
    # Step 1: Test HTTP request
    print("\n[STEP 1] Testing HTTP request...")
    try:
        response = requests.get(test_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }, timeout=30)
        print(f"[SUCCESS] HTTP Status: {response.status_code}")
        print(f"[SUCCESS] Content length: {len(response.text)} characters")
        
        # Check if content contains expected elements
        if '.article-list' in response.text:
            print("[SUCCESS] Found .article-list in HTML")
        else:
            print("[ERROR] No .article-list found in HTML")
            
        if '<article' in response.text:
            print("[SUCCESS] Found <article> tags in HTML")
        else:
            print("[ERROR] No <article> tags found in HTML")
            
    except Exception as e:
        print(f"[ERROR] HTTP request failed: {e}")
        return
    
    # Step 2: Test HTML cleaning
    print("\n[STEP 2] Testing HTML cleaning...")
    scraper = DrishtiScraper()
    try:
        cleaned_html = scraper._clean_html_for_gemini(response.text)
        print(f"[SUCCESS] Cleaned HTML length: {len(cleaned_html)} characters")
        
        # Save cleaned HTML for inspection
        with open('debug_cleaned_html.txt', 'w', encoding='utf-8') as f:
            f.write(cleaned_html[:5000])  # First 5000 chars
        print("[SUCCESS] Saved cleaned HTML sample to debug_cleaned_html.txt")
        
    except Exception as e:
        print(f"[ERROR] HTML cleaning failed: {e}")
        return
    
    # Step 3: Test Gemini extraction
    print("\n[STEP 3] Testing Gemini extraction...")
    try:
        articles = await scraper._extract_with_gemini(cleaned_html, test_url)
        print(f"[SUCCESS] Gemini returned {len(articles)} articles")
        
        for i, article in enumerate(articles, 1):
            print(f"  [ARTICLE {i}]: {article.get('title', 'No title')[:50]}...")
            
    except Exception as e:
        print(f"[ERROR] Gemini extraction failed: {e}")
        return
    
    # Step 4: Test BeautifulSoup fallback directly
    print("\n[STEP 4] Testing BeautifulSoup fallback...")
    try:
        bs_articles = await scraper._extract_with_beautifulsoup(cleaned_html, test_url)
        print(f"[SUCCESS] BeautifulSoup returned {len(bs_articles)} articles")
        
        for i, article in enumerate(bs_articles, 1):
            print(f"  [ARTICLE {i}]: {article.get('title', 'No title')[:50]}...")
            print(f"    Category: {article.get('category', 'Unknown')}")
            print(f"    Content length: {len(article.get('content', ''))} chars")
            
    except Exception as e:
        print(f"[ERROR] BeautifulSoup extraction failed: {e}")
    
    # Step 5: Test full extraction method (with fallback)
    print("\n[STEP 5] Testing full extraction method with fallback...")
    try:
        drishti_articles = await scraper.extract_articles_from_page_content(test_url)
        print(f"[SUCCESS] Full extraction returned {len(drishti_articles)} DrishtiArticle objects")
        
        for i, article in enumerate(drishti_articles, 1):
            print(f"  [ARTICLE {i}]: {article.title[:50]}...")
            print(f"    Category: {article.category}")
            print(f"    Content length: {len(article.content)} chars")
            
    except Exception as e:
        print(f"[ERROR] Full extraction failed: {e}")
        return

if __name__ == "__main__":
    asyncio.run(test_extraction())