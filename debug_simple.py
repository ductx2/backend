"""
Simple Debug Script: Check what content is available
"""

import requests
from bs4 import BeautifulSoup

def debug_content():
    url = "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/30-08-2025"
    
    print("ANALYZING HTML CONTENT")
    print(f"URL: {url}")
    
    # Fetch content
    response = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    print(f"Status: {response.status_code}")
    print(f"Content Length: {len(response.text)} characters")
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check title
    title = soup.find('title')
    print(f"Page Title: {title.text if title else 'None'}")
    
    # Check for expected content
    expected_titles = [
        "Civil Society Organizations",
        "Samudrayaan Project", 
        "USD 125.8 billion"
    ]
    
    content_text = soup.get_text()
    print("\nSEARCHING FOR EXPECTED CONTENT:")
    for title in expected_titles:
        if title.lower() in content_text.lower():
            print(f"FOUND: {title}")
        else:
            print(f"NOT FOUND: {title}")
    
    # Show content preview
    print("\nCONTENT PREVIEW (first 1000 chars):")
    print("-" * 50)
    clean_text = soup.get_text(separator=' ', strip=True)
    print(clean_text[:1000])
    print("-" * 50)

if __name__ == "__main__":
    debug_content()