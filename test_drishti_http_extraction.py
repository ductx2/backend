"""
Test File 1: HTTP + BeautifulSoup Approach for Drishti Content Extraction
Testing Chrome-free content extraction for cloud deployment

Target: Extract 5 articles from 30-08-2025 Drishti page:
1. Civil Society Organizations in India
2. SC Calls for Regulating Social Media  
3. Samudrayaan Project
4. CDS Released 3 Joint Doctrines for Armed Forces
5. USD 125.8 billion by 2032 (Project Aarohan)

Comparison with Selenium baseline results.
"""

import requests
from bs4 import BeautifulSoup
import time
from typing import List, Dict, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DrishtiHttpExtractor:
    """HTTP-only content extractor for Drishti IAS"""
    
    def __init__(self):
        self.session = requests.Session()
        
        # Browser-like headers to mimic real browser requests
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        
        self.timeout = 30
        
    def extract_articles_from_page(self, url: str) -> List[Dict[str, str]]:
        """
        Extract articles from Drishti page using HTTP + BeautifulSoup
        
        Args:
            url: Target Drishti page URL
            
        Returns:
            List of extracted articles with title, content, etc.
        """
        logger.info(f"🔍 HTTP Extraction from: {url}")
        start_time = time.time()
        
        try:
            # Make HTTP request
            logger.info("📡 Making HTTP request...")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"✅ HTTP {response.status_code} - Content length: {len(response.text)} chars")
            
            # Parse with BeautifulSoup
            logger.info("🔧 Parsing HTML with BeautifulSoup...")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Test our validated selectors from Selenium analysis
            articles = []
            
            # PRIMARY SELECTOR: .article-detail (found 5 elements in Selenium)
            logger.info("🎯 Testing .article-detail selector...")
            article_details = soup.select('.article-detail')
            logger.info(f"📦 Found {len(article_details)} .article-detail elements")
            
            if article_details:
                articles.extend(self._extract_from_containers(article_details, "article-detail"))
            
            # BACKUP SELECTOR: [class*='article'] (found 11 elements in Selenium)  
            if not articles:
                logger.info("🎯 Testing [class*='article'] selector...")
                article_elements = soup.select('[class*="article"]')
                logger.info(f"📦 Found {len(article_elements)} [class*='article'] elements")
                articles.extend(self._extract_from_containers(article_elements[:5], "class-contains-article"))
            
            # FALLBACK: Manual content extraction
            if not articles:
                logger.info("🎯 Fallback: Manual content extraction...")
                articles = self._fallback_content_extraction(soup, url)
            
            processing_time = time.time() - start_time
            logger.info(f"⏱️ HTTP extraction completed in {processing_time:.2f}s")
            logger.info(f"📊 Total articles extracted: {len(articles)}")
            
            return articles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ HTTP request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Extraction error: {e}")
            return []
    
    def _extract_from_containers(self, containers: List, selector_name: str) -> List[Dict[str, str]]:
        """Extract content from article containers"""
        articles = []
        
        for i, container in enumerate(containers):
            try:
                logger.info(f"🔍 Extracting from container {i+1}/{len(containers)} ({selector_name})")
                
                # Extract title
                title = self._extract_title(container)
                if not title:
                    logger.warning(f"⚠️ No title found in container {i+1}")
                    continue
                    
                # Extract content
                content = self._extract_content(container)
                if not content:
                    logger.warning(f"⚠️ No content found in container {i+1}")
                    continue
                
                # Create article object
                article = {
                    'title': title,
                    'content': content,
                    'container_index': i + 1,
                    'selector_used': selector_name,
                    'content_length': len(content),
                    'extraction_method': 'http_beautifulsoup'
                }
                
                articles.append(article)
                logger.info(f"✅ Article {i+1}: '{title[:50]}...' ({len(content)} chars)")
                
            except Exception as e:
                logger.error(f"❌ Error extracting container {i+1}: {e}")
                continue
        
        return articles
    
    def _extract_title(self, container) -> Optional[str]:
        """Extract title from container using multiple strategies"""
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5',  # Heading tags
            '.title', '.article-title', '.news-title',  # Title classes
            'a[href]'  # Links that might contain titles
        ]
        
        for selector in title_selectors:
            try:
                elements = container.select(selector)
                for element in elements[:3]:  # Check first 3 matches
                    title_text = element.get_text(strip=True)
                    if title_text and 10 <= len(title_text) <= 200:  # Reasonable title length
                        return title_text
            except:
                continue
        
        # Fallback: first line of container text
        try:
            container_text = container.get_text(strip=True)
            if container_text:
                first_line = container_text.split('\n')[0].strip()
                if first_line and 10 <= len(first_line) <= 200:
                    return first_line
        except:
            pass
        
        return "Untitled Article"
    
    def _extract_content(self, container) -> Optional[str]:
        """Extract content from container"""
        try:
            # Remove script and style elements
            for element in container(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
            
            # Get clean text content
            content = container.get_text(separator='\n\n', strip=True)
            
            # Basic content validation
            if content and len(content) > 100:  # Minimum content length
                # Limit content size to prevent memory issues
                return content[:5000]  # Max 5000 characters
            
            return None
            
        except Exception as e:
            logger.error(f"Content extraction error: {e}")
            return None
    
    def _fallback_content_extraction(self, soup: BeautifulSoup, url: str) -> List[Dict[str, str]]:
        """Fallback method to extract content when selectors fail"""
        logger.info("🔄 Using fallback extraction method...")
        
        articles = []
        
        # Look for common news article patterns
        fallback_selectors = [
            'article', '.post', '.entry', '.content',
            '.news-item', '.story', '.article-content',
            'main section', '.main-content', 
            'div[class*="current"]', 'div[class*="news"]'
        ]
        
        for selector in fallback_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"📦 Fallback found {len(elements)} elements with '{selector}'")
                    
                    for i, element in enumerate(elements[:5]):  # Max 5 elements
                        content = element.get_text(separator='\n\n', strip=True)
                        if content and len(content) > 200:  # Substantial content
                            articles.append({
                                'title': f"Article {i+1} (Fallback)",
                                'content': content[:3000],  # Limit size
                                'container_index': i + 1,
                                'selector_used': f'fallback_{selector}',
                                'content_length': len(content),
                                'extraction_method': 'http_fallback'
                            })
                    
                    if articles:
                        break  # Stop after first successful selector
                        
            except Exception as e:
                logger.debug(f"Fallback selector '{selector}' failed: {e}")
                continue
        
        return articles

def test_http_extraction():
    """Test HTTP extraction against target URL"""
    
    # Target URL and expected articles
    target_url = "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/30-08-2025"
    
    expected_articles = [
        "Civil Society Organizations in India",
        "SC Calls for Regulating Social Media",  
        "Samudrayaan Project",
        "CDS Released 3 Joint Doctrines for Armed Forces",
        "USD 125.8 billion by 2032"
    ]
    
    logger.info("🧪 TESTING HTTP + BEAUTIFULSOUP APPROACH")
    logger.info(f"📍 Target URL: {target_url}")
    logger.info(f"🎯 Expected: {len(expected_articles)} articles")
    logger.info(f"📝 Expected titles: {expected_articles}")
    
    # Initialize extractor
    extractor = DrishtiHttpExtractor()
    
    # Run extraction
    start_time = time.time()
    articles = extractor.extract_articles_from_page(target_url)
    total_time = time.time() - start_time
    
    # Print results
    logger.info("\n" + "="*70)
    logger.info("📊 EXTRACTION RESULTS")
    logger.info("="*70)
    logger.info(f"⏱️ Total time: {total_time:.2f} seconds")
    logger.info(f"📊 Articles found: {len(articles)}")
    logger.info(f"🎯 Expected count: {len(expected_articles)}")
    logger.info(f"📈 Success rate: {(len(articles)/len(expected_articles))*100:.1f}%")
    
    if articles:
        logger.info("\n📄 EXTRACTED ARTICLES:")
        for i, article in enumerate(articles, 1):
            logger.info(f"\n{i}. Title: {article['title']}")
            logger.info(f"   Content: {article['content'][:100]}...")
            logger.info(f"   Length: {article['content_length']} chars")
            logger.info(f"   Method: {article['extraction_method']}")
            logger.info(f"   Selector: {article['selector_used']}")
    else:
        logger.error("❌ NO ARTICLES EXTRACTED!")
    
    # Compare with expected
    logger.info("\n🔍 ACCURACY ANALYSIS:")
    found_titles = [article['title'] for article in articles]
    
    matches = 0
    for expected in expected_articles:
        found_match = any(expected.lower() in title.lower() or title.lower() in expected.lower() 
                         for title in found_titles)
        if found_match:
            matches += 1
            logger.info(f"✅ FOUND: {expected}")
        else:
            logger.info(f"❌ MISSING: {expected}")
    
    accuracy = (matches / len(expected_articles)) * 100
    logger.info(f"\n🎯 FINAL ACCURACY: {matches}/{len(expected_articles)} = {accuracy:.1f}%")
    
    return {
        'articles_found': len(articles),
        'expected_count': len(expected_articles),
        'accuracy_percentage': accuracy,
        'extraction_time': total_time,
        'articles': articles,
        'success': len(articles) >= 4  # Consider success if we get 4+ articles
    }

if __name__ == "__main__":
    test_results = test_http_extraction()
    
    print("\n" + "="*70)
    print("🏁 TEST SUMMARY")
    print("="*70)
    print(f"Approach: HTTP + BeautifulSoup")
    print(f"Articles Found: {test_results['articles_found']}")
    print(f"Expected Count: {test_results['expected_count']}")
    print(f"Accuracy: {test_results['accuracy_percentage']:.1f}%")
    print(f"Time: {test_results['extraction_time']:.2f}s")
    print(f"Success: {'✅ PASS' if test_results['success'] else '❌ FAIL'}")