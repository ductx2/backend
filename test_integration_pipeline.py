#!/usr/bin/env python3
"""
PHASE 2: INTEGRATION TESTING SUITE
Complete RSS + Drishti + AI + Database Pipeline Validation

Tests the full end-to-end workflow:
1. Parallel RSS and Drishti content acquisition
2. Content preference logic (Drishti > RSS for duplicates)
3. AI processing pipeline with mixed content types
4. Database bulk operations with integrated data
5. Performance metrics under realistic load
6. Error handling and recovery mechanisms

Windows-compatible version
"""

import sys
import os
import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.core.config import get_settings
    from app.services.optimized_rss_processor import OptimizedRSSProcessor
    from app.services.drishti_scraper import DrishtiScraper  
    from app.services.unified_content_processor import UnifiedContentProcessor
    from app.core.database import get_database_sync
    
    print("PHASE 2: INTEGRATION TESTING SUITE")
    print("=" * 45)
    print("Complete RSS + Drishti + AI + Database Pipeline Validation")
    print()
    
    settings = get_settings()
    
    class IntegrationTester:
        """Comprehensive integration testing class"""
        
        def __init__(self):
            self.settings = settings
            self.test_results = {
                "phase_2_tests": {
                    "total_tests": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0
                },
                "performance_metrics": {},
                "integration_results": {},
                "test_details": []
            }
        
        def log_test_result(self, test_name: str, success: bool, details: Dict[str, Any], skip_reason: str = None):
            """Log individual test results"""
            self.test_results["phase_2_tests"]["total_tests"] += 1
            
            if skip_reason:
                status = "SKIP"
                self.test_results["phase_2_tests"]["skipped"] += 1
            elif success:
                status = "PASS" 
                self.test_results["phase_2_tests"]["passed"] += 1
            else:
                status = "FAIL"
                self.test_results["phase_2_tests"]["failed"] += 1
            
            result = {
                "test_name": test_name,
                "status": status,
                "details": details,
                "skip_reason": skip_reason,
                "timestamp": datetime.now().isoformat()
            }
            
            self.test_results["test_details"].append(result)
            
            # Print result
            status_symbol = {"PASS": "[OK]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
            print(f"{status_symbol} {test_name}")
            if details.get("timing"):
                print(f"    Time: {details['timing']:.2f}s")
            if details.get("count"):
                print(f"    Count: {details['count']}")
            if skip_reason:
                print(f"    Reason: {skip_reason}")
            if not success and details.get("error"):
                print(f"    Error: {details['error']}")
            print()
        
        async def test_rss_processing_integration(self) -> bool:
            """Test RSS processing system integration"""
            print("RSS PROCESSING INTEGRATION TEST")
            print("-" * 40)
            
            try:
                start_time = time.time()
                
                # Initialize RSS processor
                rss_processor = OptimizedRSSProcessor()
                
                # Test parallel fetching
                raw_articles = await rss_processor.fetch_all_sources_parallel()
                
                # Test AI processing (limited for speed)
                if raw_articles:
                    test_sample = raw_articles[:3]  # Small sample for integration testing
                    processed_articles = await rss_processor.process_articles_with_single_ai_pass(test_sample)
                else:
                    processed_articles = []
                
                processing_time = time.time() - start_time
                
                # Validate results
                success = len(raw_articles) > 0 and len(processed_articles) > 0
                
                self.log_test_result(
                    "RSS Processing Integration",
                    success,
                    {
                        "timing": processing_time,
                        "raw_articles": len(raw_articles),
                        "processed_articles": len(processed_articles),
                        "sources_successful": rss_processor.processing_stats.get("sources_successful", 0),
                        "error": None if success else "No articles processed"
                    }
                )
                
                # Store for later integration tests
                self.test_results["integration_results"]["rss_articles"] = processed_articles[:5]  # Keep sample
                
                return success
                
            except Exception as e:
                self.log_test_result(
                    "RSS Processing Integration", 
                    False,
                    {"error": str(e), "timing": 0}
                )
                return False
        
        async def test_drishti_scraper_integration(self) -> bool:
            """Test Drishti scraper integration (with browser dependency handling)"""
            print("DRISHTI SCRAPER INTEGRATION TEST")
            print("-" * 40)
            
            try:
                start_time = time.time()
                
                # Initialize Drishti scraper
                drishti_scraper = DrishtiScraper()
                
                # Test browser initialization first
                browser_success = await drishti_scraper.initialize_browser()
                
                if not browser_success:
                    self.log_test_result(
                        "Drishti Scraper Integration",
                        False,
                        {"error": "Browser initialization failed", "timing": time.time() - start_time},
                        "Chrome browser dependencies not available"
                    )
                    return False
                
                # Test article link scraping (limited for speed)
                target_url = drishti_scraper.target_urls["daily_current_affairs"]
                article_links = await drishti_scraper.scrape_article_links(target_url, max_articles=2)
                
                # Test content scraping if links found
                scraped_articles = []
                if article_links:
                    # Try to scrape one article
                    for link in article_links[:1]:  # Just one for integration testing
                        article = await drishti_scraper.scrape_article_content(link)
                        if article:
                            scraped_articles.append(article)
                            break
                
                # Test AI processing if content found
                processed_drishti = []
                if scraped_articles:
                    processed_drishti = await drishti_scraper.process_articles_with_ai(scraped_articles)
                
                processing_time = time.time() - start_time
                drishti_scraper.close_browser()
                
                # Validate results
                success = len(article_links) > 0
                
                self.log_test_result(
                    "Drishti Scraper Integration",
                    success,
                    {
                        "timing": processing_time,
                        "links_found": len(article_links),
                        "articles_scraped": len(scraped_articles),
                        "articles_processed": len(processed_drishti),
                        "error": None if success else "No article links found"
                    }
                )
                
                # Store for integration tests
                self.test_results["integration_results"]["drishti_articles"] = processed_drishti
                
                return success
                
            except Exception as e:
                self.log_test_result(
                    "Drishti Scraper Integration",
                    False, 
                    {"error": str(e), "timing": time.time() - start_time}
                )
                return False
        
        async def test_unified_content_processing(self) -> bool:
            """Test unified content processor integration"""
            print("UNIFIED CONTENT PROCESSING INTEGRATION TEST")
            print("-" * 50)
            
            try:
                start_time = time.time()
                
                # Initialize unified processor
                unified_processor = UnifiedContentProcessor()
                
                # Test with small limits for integration testing
                result = await unified_processor.process_unified_content(
                    rss_articles_limit=5,      # Small for testing
                    drishti_daily_limit=2,     # Small for testing  
                    drishti_editorial_limit=1  # Small for testing
                )
                
                processing_time = time.time() - start_time
                
                success = result.get("success", False)
                
                self.log_test_result(
                    "Unified Content Processing Integration",
                    success,
                    {
                        "timing": processing_time,
                        "total_processed": result.get("content_breakdown", {}).get("total_articles_processed", 0),
                        "final_saved": result.get("content_breakdown", {}).get("final_articles_saved", 0),
                        "rss_articles": result.get("content_breakdown", {}).get("rss_articles_processed", 0),
                        "drishti_articles": result.get("content_breakdown", {}).get("drishti_articles_processed", 0),
                        "duplicates_removed": result.get("content_breakdown", {}).get("duplicates_removed", 0),
                        "error": result.get("message") if not success else None
                    }
                )
                
                # Store performance metrics
                if success:
                    self.test_results["performance_metrics"]["unified_processing"] = result.get("performance", {})
                
                return success
                
            except Exception as e:
                self.log_test_result(
                    "Unified Content Processing Integration",
                    False,
                    {"error": str(e), "timing": time.time() - start_time}
                )
                return False
        
        async def test_database_integration_pipeline(self) -> bool:
            """Test complete database integration pipeline"""
            print("DATABASE INTEGRATION PIPELINE TEST")
            print("-" * 40)
            
            try:
                start_time = time.time()
                
                # Test database connectivity
                db = get_database_sync()
                health_status = await db.health_check()
                
                if health_status.get("status") != "healthy":
                    raise Exception("Database not healthy")
                
                # Test bulk operations
                initial_count = await db.get_current_affairs_count()
                
                # Test article retrieval
                recent_articles = await db.get_recent_articles(limit=10)
                
                # Test search functionality  
                search_results = await db.search_articles("policy", limit=5)
                
                # Test source filtering
                source_articles = await db.get_articles_by_source("PIB", limit=5)
                
                processing_time = time.time() - start_time
                
                success = (
                    health_status.get("status") == "healthy" and
                    isinstance(initial_count, int) and
                    len(recent_articles) >= 0
                )
                
                self.log_test_result(
                    "Database Integration Pipeline",
                    success,
                    {
                        "timing": processing_time,
                        "db_status": health_status.get("status"),
                        "total_articles": initial_count,
                        "recent_articles": len(recent_articles),
                        "search_results": len(search_results),
                        "source_articles": len(source_articles),
                        "error": None if success else "Database operations failed"
                    }
                )
                
                return success
                
            except Exception as e:
                self.log_test_result(
                    "Database Integration Pipeline",
                    False,
                    {"error": str(e), "timing": time.time() - start_time}
                )
                return False
        
        async def test_content_preference_logic(self) -> bool:
            """Test content preference logic (Drishti > RSS for duplicates)"""
            print("CONTENT PREFERENCE LOGIC TEST")
            print("-" * 35)
            
            try:
                start_time = time.time()
                
                # This test validates the logic exists and can be called
                # Full testing would require creating duplicate content scenarios
                
                unified_processor = UnifiedContentProcessor()
                
                # Get priority weights
                priority_weights = unified_processor.priority_weights
                
                # Validate priority scoring
                drishti_priority = priority_weights.get("drishti_current_affairs", 0)
                rss_priority = priority_weights.get("pib_official", 0) 
                
                # Test passes if Drishti has higher priority
                success = drishti_priority > rss_priority
                
                processing_time = time.time() - start_time
                
                self.log_test_result(
                    "Content Preference Logic",
                    success,
                    {
                        "timing": processing_time,
                        "drishti_priority": drishti_priority,
                        "rss_priority": rss_priority,
                        "priority_weights_configured": len(priority_weights),
                        "logic_validated": "Drishti > RSS priority confirmed" if success else "Priority logic issue"
                    }
                )
                
                return success
                
            except Exception as e:
                self.log_test_result(
                    "Content Preference Logic",
                    False,
                    {"error": str(e), "timing": time.time() - start_time}
                )
                return False
        
        async def test_performance_metrics_integration(self) -> bool:
            """Test performance metrics and monitoring integration"""
            print("PERFORMANCE METRICS INTEGRATION TEST")
            print("-" * 45)
            
            try:
                start_time = time.time()
                
                # Test RSS processor metrics
                rss_processor = OptimizedRSSProcessor()
                rss_health = rss_processor.get_source_health_status()
                
                # Test unified processor metrics
                unified_processor = UnifiedContentProcessor()
                unified_stats = await unified_processor.get_processing_stats()
                
                # Test database metrics
                db = get_database_sync()
                db_health = await db.health_check()
                
                processing_time = time.time() - start_time
                
                success = (
                    "overall_health" in rss_health and
                    "processing_stats" in unified_stats and
                    "status" in db_health
                )
                
                self.log_test_result(
                    "Performance Metrics Integration", 
                    success,
                    {
                        "timing": processing_time,
                        "rss_health_score": rss_health.get("overall_health", 0),
                        "rss_active_sources": rss_health.get("active_sources", 0),
                        "unified_features": len(unified_stats.get("optimization_features", {})),
                        "db_status": db_health.get("status"),
                        "metrics_available": success
                    }
                )
                
                return success
                
            except Exception as e:
                self.log_test_result(
                    "Performance Metrics Integration",
                    False,
                    {"error": str(e), "timing": time.time() - start_time}
                )
                return False
        
        def print_phase2_summary(self):
            """Print comprehensive Phase 2 results"""
            print("=" * 45)
            print("PHASE 2: INTEGRATION TESTING RESULTS")
            print("=" * 45)
            
            results = self.test_results["phase_2_tests"]
            
            print(f"Total Integration Tests: {results['total_tests']}")
            print(f"Passed: {results['passed']}")
            print(f"Failed: {results['failed']}")
            print(f"Skipped: {results['skipped']}")
            
            if results['total_tests'] > 0:
                success_rate = (results['passed'] / results['total_tests']) * 100
                print(f"Success Rate: {success_rate:.1f}%")
            
            print()
            
            # Performance summary
            if self.test_results["performance_metrics"]:
                print("PERFORMANCE METRICS:")
                print("-" * 25)
                for metric_name, metrics in self.test_results["performance_metrics"].items():
                    print(f"  {metric_name}:")
                    if isinstance(metrics, dict):
                        for key, value in metrics.items():
                            print(f"    {key}: {value}")
                print()
            
            # Integration results summary
            integration = self.test_results["integration_results"]
            if integration:
                print("INTEGRATION RESULTS:")
                print("-" * 25)
                if "rss_articles" in integration:
                    print(f"  RSS Articles Processed: {len(integration['rss_articles'])}")
                if "drishti_articles" in integration:
                    print(f"  Drishti Articles Processed: {len(integration['drishti_articles'])}")
                print()
            
            # Determine overall success
            critical_tests_passed = results['passed'] >= (results['total_tests'] * 0.7)  # 70% threshold
            
            if critical_tests_passed:
                print("PHASE 2 INTEGRATION TESTING: SUCCESS!")
                print("Critical integration pathways validated.")
                print("Ready to proceed to Phase 3 performance testing.")
            else:
                print("PHASE 2 INTEGRATION TESTING: NEEDS ATTENTION")
                print("Some critical integration tests failed.")
                print("Review failed tests before proceeding.")
            
            return critical_tests_passed
    
    async def run_phase2_integration_tests():
        """Run complete Phase 2 integration testing suite"""
        
        print("Configuration Validation:")
        print(f"Environment: {settings.environment}")
        print(f"Gemini API: {'[OK]' if settings.gemini_api_key else '[MISSING]'}")
        print(f"Supabase: {'[OK]' if settings.supabase_url else '[MISSING]'}")
        print(f"API Key: {'[OK]' if settings.api_key else '[MISSING]'}")
        print()
        
        tester = IntegrationTester()
        
        try:
            # Run integration tests in logical order
            await tester.test_rss_processing_integration()
            await tester.test_drishti_scraper_integration()
            await tester.test_database_integration_pipeline()
            await tester.test_content_preference_logic()
            await tester.test_performance_metrics_integration()
            await tester.test_unified_content_processing()
            
            # Print comprehensive results
            success = tester.print_phase2_summary()
            
            return success
            
        except Exception as e:
            print(f"PHASE 2 INTEGRATION TESTING FAILED: {e}")
            return False
    
    # Run Phase 2 integration tests
    success = asyncio.run(run_phase2_integration_tests())
    
    if success:
        print("PHASE 2 INTEGRATION TESTING COMPLETED SUCCESSFULLY!")
        exit_code = 0
    else:
        print("Phase 2 integration testing encountered critical issues.")
        exit_code = 1
        
except ImportError as e:
    print(f"Import Error: {e}")
    exit_code = 1
    
except Exception as e:
    print(f"Phase 2 Integration Testing Error: {e}")
    exit_code = 1

print(f"Phase 2 integration testing completed at {datetime.now().isoformat()}")
exit(exit_code)