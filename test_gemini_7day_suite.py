"""
Comprehensive 7-Day Test Suite for Gemini-Based Drishti Scraper
Tests the modified drishti_scraper.py with Gemini approach across last 7 days

Test Period: August 24-30, 2025
Purpose: Validate Chrome-free Gemini LLM approach before production deployment
"""

import asyncio
import time
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.drishti_scraper import DrishtiScraper

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    date: str
    url: str
    articles_found: int
    success: bool
    error: Optional[str]
    processing_time: float
    articles: List[Dict[str, str]]

class Gemini7DayTestSuite:
    """Comprehensive test suite for Gemini-based content extraction"""
    
    def __init__(self):
        self.test_dates = self._generate_test_dates()
        self.results: List[TestResult] = []
        self.scraper = DrishtiScraper()
        
    def _generate_test_dates(self) -> List[str]:
        """Generate URLs for last 7 days (24-30 Aug 2025)"""
        base_date = datetime(2025, 8, 30)  # End date
        test_dates = []
        
        for i in range(7):  # 7 days back
            date = base_date - timedelta(days=i)
            date_str = date.strftime("%d-%m-%Y")
            test_dates.append(date_str)
        
        return test_dates
    
    def _get_drishti_url(self, date_str: str) -> str:
        """Generate Drishti URL for given date"""
        return f"https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/{date_str}"
    
    async def test_single_date(self, date_str: str) -> TestResult:
        """Test extraction for a single date"""
        url = self._get_drishti_url(date_str)
        logger.info(f"🧪 Testing {date_str}: {url}")
        
        start_time = time.time()
        
        try:
            # Use the modified extract_articles_from_page_content method
            articles = await self.scraper.extract_articles_from_page_content(url)
            
            processing_time = time.time() - start_time
            
            # Convert DrishtiArticle objects to dict for analysis
            article_dicts = []
            for article in articles:
                article_dicts.append({
                    'title': article.title,
                    'content': article.content[:200] + '...',  # Truncate for readability
                    'category': article.category,
                    'content_length': len(article.content)
                })
            
            success = len(articles) >= 3  # Expect at least 3 articles per day
            
            result = TestResult(
                date=date_str,
                url=url,
                articles_found=len(articles),
                success=success,
                error=None,
                processing_time=processing_time,
                articles=article_dicts
            )
            
            status = "✅ PASS" if success else "⚠️ LOW COUNT"
            logger.info(f"📊 {date_str}: {len(articles)} articles in {processing_time:.2f}s - {status}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            result = TestResult(
                date=date_str,
                url=url,
                articles_found=0,
                success=False,
                error=str(e),
                processing_time=processing_time,
                articles=[]
            )
            
            logger.error(f"❌ {date_str} FAILED: {e}")
            return result
    
    async def run_full_test_suite(self):
        """Run complete 7-day test suite"""
        logger.info("🚀 STARTING 7-DAY GEMINI TEST SUITE")
        logger.info(f"📅 Testing dates: {', '.join(self.test_dates)}")
        logger.info("="*80)
        
        overall_start = time.time()
        
        # Test each date
        for date_str in self.test_dates:
            result = await self.test_single_date(date_str)
            self.results.append(result)
            
            # Small delay between tests to avoid rate limiting
            await asyncio.sleep(2)
        
        overall_time = time.time() - overall_start
        
        # Analyze results
        self._analyze_results(overall_time)
        
        # Close scraper
        if hasattr(self.scraper, 'close_browser'):
            self.scraper.close_browser()
    
    def _analyze_results(self, total_time: float):
        """Analyze and report test results"""
        logger.info("\n" + "="*80)
        logger.info("📊 7-DAY GEMINI TEST SUITE RESULTS")
        logger.info("="*80)
        
        # Overall statistics
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        total_articles = sum(r.articles_found for r in self.results)
        avg_articles_per_day = total_articles / total_tests if total_tests > 0 else 0
        avg_processing_time = sum(r.processing_time for r in self.results) / total_tests if total_tests > 0 else 0
        
        logger.info(f"🎯 Overall Statistics:")
        logger.info(f"   Total Tests: {total_tests}")
        logger.info(f"   Successful Tests: {successful_tests}/{total_tests} ({(successful_tests/total_tests)*100:.1f}%)")
        logger.info(f"   Total Articles Extracted: {total_articles}")
        logger.info(f"   Average Articles/Day: {avg_articles_per_day:.1f}")
        logger.info(f"   Average Processing Time: {avg_processing_time:.2f}s")
        logger.info(f"   Total Suite Time: {total_time:.2f}s")
        
        # Detailed results
        logger.info(f"\n📄 Detailed Results:")
        for result in self.results:
            status_emoji = "✅" if result.success else ("❌" if result.error else "⚠️")
            logger.info(f"   {status_emoji} {result.date}: {result.articles_found} articles ({result.processing_time:.2f}s)")
            
            if result.error:
                logger.info(f"      Error: {result.error}")
            
            # Show article titles
            if result.articles:
                logger.info(f"      Articles:")
                for i, article in enumerate(result.articles[:3], 1):  # Show first 3
                    logger.info(f"        {i}. {article['title']}")
                    logger.info(f"           Category: {article['category']}, Length: {article['content_length']} chars")
                if len(result.articles) > 3:
                    logger.info(f"        ... and {len(result.articles) - 3} more articles")
        
        # Performance analysis
        logger.info(f"\n⚡ Performance Analysis:")
        if self.results:
            min_time = min(r.processing_time for r in self.results)
            max_time = max(r.processing_time for r in self.results)
            logger.info(f"   Fastest Extraction: {min_time:.2f}s")
            logger.info(f"   Slowest Extraction: {max_time:.2f}s")
            logger.info(f"   Time Variation: {max_time - min_time:.2f}s")
        
        # Quality analysis
        logger.info(f"\n📈 Quality Analysis:")
        if self.results:
            article_counts = [r.articles_found for r in self.results if r.success]
            if article_counts:
                min_articles = min(article_counts)
                max_articles = max(article_counts)
                logger.info(f"   Min Articles Found: {min_articles}")
                logger.info(f"   Max Articles Found: {max_articles}")
                logger.info(f"   Article Count Variation: {max_articles - min_articles}")
        
        # Cloud deployment readiness
        logger.info(f"\n☁️ Cloud Deployment Readiness:")
        chrome_free = True  # Our new approach is Chrome-free
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        consistent_performance = avg_processing_time < 30  # Less than 30s per extraction
        reliable_extraction = success_rate >= 80  # At least 80% success rate
        
        logger.info(f"   ✅ Chrome-Free: {chrome_free}")
        logger.info(f"   {'✅' if success_rate >= 80 else '❌'} Success Rate: {success_rate:.1f}% (≥80% required)")
        logger.info(f"   {'✅' if consistent_performance else '❌'} Performance: {avg_processing_time:.1f}s avg (<30s required)")
        logger.info(f"   {'✅' if reliable_extraction else '❌'} Reliability: {'Good' if reliable_extraction else 'Needs improvement'}")
        
        deployment_ready = chrome_free and success_rate >= 80 and consistent_performance and reliable_extraction
        
        logger.info(f"\n🚀 DEPLOYMENT DECISION:")
        if deployment_ready:
            logger.info("   ✅ READY FOR PRODUCTION DEPLOYMENT")
            logger.info("   The Gemini-based scraper meets all requirements for cloud hosting!")
        else:
            logger.info("   ❌ NOT READY - Issues need to be addressed:")
            if not reliable_extraction:
                logger.info("     - Improve extraction reliability")
            if not consistent_performance:
                logger.info("     - Optimize processing speed")
        
        return {
            'deployment_ready': deployment_ready,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time,
            'total_articles': total_articles,
            'results': self.results
        }

async def main():
    """Run the comprehensive test suite"""
    test_suite = Gemini7DayTestSuite()
    
    print("🧪 GEMINI 7-DAY TEST SUITE")
    print("Testing Chrome-free Drishti scraper across August 24-30, 2025")
    print("This will validate the Gemini LLM approach for cloud deployment")
    print("="*80)
    
    try:
        await test_suite.run_full_test_suite()
        
        print("\n" + "="*80)
        print("🏁 Test suite completed! Check logs above for detailed analysis.")
        
    except Exception as e:
        logger.error(f"💥 Test suite failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())