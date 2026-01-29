"""
Debug Script: Analyze what content is actually available in the HTML
This will help us understand why all approaches are failing
"""

import requests
from bs4 import BeautifulSoup

def analyze_html_content():
    url = "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/30-08-2025"
    
    print("🔍 ANALYZING HTML CONTENT STRUCTURE")
    print(f"📍 URL: {url}")
    
    # Fetch content
    response = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    print(f"✅ HTTP {response.status_code}")
    print(f"📊 Content Length: {len(response.text)} characters")
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check for various content patterns
    print("\n🔍 CONTENT ANALYSIS:")
    
    # Check title
    title = soup.find('title')
    print(f"📰 Page Title: {title.text if title else 'None'}")
    
    # Look for main content indicators
    selectors_to_check = [
        'article', '.article', '.article-detail',
        '.news-item', '.content', '.post',
        'h1', 'h2', 'h3', 
        '.main-content', 'main',
        '[class*="current"]', '[class*="affairs"]',
        'p'
    ]
    
    for selector in selectors_to_check:
        elements = soup.select(selector)
        print(f"🔍 {selector}: {len(elements)} elements found")
        
        if elements and len(elements) <= 10:  # Show details for small counts
            for i, elem in enumerate(elements[:3]):  # Show first 3
                text = elem.get_text(strip=True)[:100]
                print(f"   {i+1}. {text}...")
    
    # Check for specific text patterns that might indicate articles
    content_text = soup.get_text()
    
    # Look for expected article titles in the content
    expected_titles = [
        "Civil Society Organizations",
        "SC Calls for Regulating Social Media",
        "Samudrayaan Project", 
        "CDS Released 3 Joint Doctrines",
        "USD 125.8 billion"
    ]
    
    print("\n🎯 SEARCHING FOR EXPECTED CONTENT:")
    for title in expected_titles:
        if title.lower() in content_text.lower():
            print(f"✅ FOUND: '{title}' in page content")
        else:
            print(f"❌ NOT FOUND: '{title}'")
    
    # Show first 2000 characters of cleaned content
    print("\n📄 CONTENT PREVIEW (first 2000 chars):")
    print("="*80)
    clean_text = soup.get_text(separator=' ', strip=True)
    print(clean_text[:2000])
    print("="*80)
    
    # Check for redirects or error pages
    if "404" in response.text or "not found" in response.text.lower():
        print("⚠️ POTENTIAL 404 ERROR PAGE")
    
    if "redirect" in response.text.lower():
        print("⚠️ POTENTIAL REDIRECT PAGE")

if __name__ == "__main__":
    analyze_html_content()