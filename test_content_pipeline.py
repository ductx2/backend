#!/usr/bin/env python3
"""
🧪 COMPREHENSIVE END-TO-END TESTING SUITE
Universal Content Extraction & AI Enhancement Pipeline

Test Scenarios:
1. Single URL content extraction
2. Batch URL content extraction  
3. Content cleaning and normalization
4. Gemini AI enhancement (comprehensive + UPSC-focused)
5. Complete RSS to database flow
6. Error handling and edge cases

Compatible with: Python 3.13.5, FastAPI 0.116.1
Created: 2025-08-30
"""

import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentPipelineTest:
    """Comprehensive test suite for content extraction and enhancement pipeline"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else None
        }
        self.test_results = []
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute comprehensive end-to-end testing suite"""
        
        logger.info("🧪 Starting Comprehensive Content Pipeline Testing Suite")
        overall_start = time.time()
        
        test_cases = [
            ("Health Check", self.test_health_check),
            ("Authentication", self.test_authentication),
            ("Single URL Extraction", self.test_single_url_extraction),
            ("Batch URL Extraction", self.test_batch_url_extraction),
            ("Content Cleaning", self.test_content_cleaning),
            ("Gemini Enhancement - Comprehensive", self.test_gemini_comprehensive),
            ("Gemini Enhancement - UPSC Focused", self.test_gemini_upsc_focused),
            ("RSS Processing Flow", self.test_rss_processing_flow),
            ("Error Handling", self.test_error_handling),
            ("Performance Benchmarks", self.test_performance_benchmarks)
        ]
        
        successful_tests = 0
        failed_tests = 0
        
        for test_name, test_func in test_cases:
            logger.info(f"🔍 Running test: {test_name}")
            
            try:
                result = await test_func()
                if result.get('success', False):
                    successful_tests += 1
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    failed_tests += 1
                    logger.error(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
                    
                self.test_results.append({
                    'test': test_name,
                    'status': 'PASSED' if result.get('success') else 'FAILED',
                    'result': result,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                failed_tests += 1
                logger.error(f"❌ {test_name}: EXCEPTION - {str(e)}")
                self.test_results.append({
                    'test': test_name,
                    'status': 'EXCEPTION',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        total_time = time.time() - overall_start
        
        # Generate comprehensive test report
        test_summary = {
            'success': failed_tests == 0,
            'message': f'Content Pipeline Testing Complete: {successful_tests}/{len(test_cases)} tests passed',
            'statistics': {
                'total_tests': len(test_cases),
                'passed_tests': successful_tests,
                'failed_tests': failed_tests,
                'success_rate': (successful_tests / len(test_cases)) * 100,
                'total_test_time': total_time,
                'average_test_time': total_time / len(test_cases)
            },
            'test_results': self.test_results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"🎯 Test Suite Complete: {successful_tests}/{len(test_cases)} passed in {total_time:.2f}s")
        
        return test_summary

    async def test_health_check(self) -> Dict[str, Any]:
        """Test API health and connectivity"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/health")
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': data.get('status') == 'healthy',
                    'response': data
                }
            else:
                return {
                    'success': False,
                    'error': f'Health check failed with status {response.status_code}'
                }

    async def test_authentication(self) -> Dict[str, Any]:
        """Test API authentication"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/auth/verify", 
                headers=self.headers
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'response': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'Authentication failed with status {response.status_code}'
                }

    async def test_single_url_extraction(self) -> Dict[str, Any]:
        """Test single URL content extraction"""
        
        test_urls = [
            "https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2077324",  # PIB article
            "https://www.thehindu.com/news/national/",  # The Hindu
            "https://economictimes.indiatimes.com/news/"  # Economic Times
        ]
        
        results = []
        
        async with httpx.AsyncClient() as client:
            for url in test_urls:
                try:
                    request_data = {
                        "url": url,
                        "strategy": "auto"
                    }
                    
                    response = await client.post(
                        f"{self.base_url}/api/content/extract-url",
                        json=request_data,
                        headers=self.headers,
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results.append({
                            'url': url,
                            'success': data.get('success', False),
                            'content_length': len(data.get('data', {}).get('content', '')) if data.get('data') else 0,
                            'processing_time': data.get('processing_time', 0)
                        })
                    else:
                        results.append({
                            'url': url,
                            'success': False,
                            'error': f'Status {response.status_code}'
                        })
                        
                except Exception as e:
                    results.append({
                        'url': url,
                        'success': False,
                        'error': str(e)
                    })
        
        successful_extractions = sum(1 for r in results if r.get('success', False))
        
        return {
            'success': successful_extractions > 0,
            'results': results,
            'statistics': {
                'total_urls': len(test_urls),
                'successful_extractions': successful_extractions,
                'success_rate': (successful_extractions / len(test_urls)) * 100
            }
        }

    async def test_batch_url_extraction(self) -> Dict[str, Any]:
        """Test batch URL content extraction"""
        
        test_urls = [
            "https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2077324",
            "https://www.thehindu.com/news/national/",
            "https://economictimes.indiatimes.com/news/"
        ]
        
        request_data = {
            "urls": test_urls,
            "max_concurrent": 3,
            "strategy": "auto"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/content/extract-batch",
                    json=request_data,
                    headers=self.headers,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'success': data.get('success', False),
                        'statistics': data.get('statistics', {}),
                        'processing_time': data.get('processing_time', 0)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Batch extraction failed with status {response.status_code}'
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }

    async def test_content_cleaning(self) -> Dict[str, Any]:
        """Test content cleaning and normalization"""
        
        test_content = {
            "title": "Test   Article   Title",
            "content": "<p>This is a <strong>test</strong> article with   extra   spaces  and HTML tags.</p><br/><div>More content here…</div>",
            "remove_extra_whitespace": True,
            "normalize_quotes": True,
            "remove_html": True
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/content/clean",
                    json=test_content,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    cleaned_data = data.get('data', {})
                    
                    return {
                        'success': data.get('success', False),
                        'original_length': cleaned_data.get('cleaning_statistics', {}).get('original_length', 0),
                        'cleaned_length': cleaned_data.get('cleaning_statistics', {}).get('cleaned_length', 0),
                        'character_reduction': cleaned_data.get('cleaning_statistics', {}).get('character_reduction', 0)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Content cleaning failed with status {response.status_code}'
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }

    async def test_gemini_comprehensive(self) -> Dict[str, Any]:
        """Test Gemini comprehensive enhancement"""
        
        test_content = {
            "title": "Economic Survey 2024 Highlights Key Policy Reforms",
            "content": "The Economic Survey 2024 presents a comprehensive analysis of India's economic performance. Key highlights include GDP growth projections, inflation management strategies, and fiscal policy reforms. The survey emphasizes digital infrastructure development and sustainable growth initiatives.",
            "enhancement_mode": "comprehensive",
            "source_url": "https://example.com/economic-survey"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/ai/enhance-content",
                    json=test_content,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    enhanced_data = data.get('data', {})
                    
                    return {
                        'success': data.get('success', False),
                        'upsc_relevance_score': enhanced_data.get('upsc_relevance', 0),
                        'relevant_papers': enhanced_data.get('relevant_papers', []),
                        'processing_time': data.get('processing_time', 0)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Comprehensive enhancement failed with status {response.status_code}'
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }

    async def test_gemini_upsc_focused(self) -> Dict[str, Any]:
        """Test Gemini UPSC-focused enhancement"""
        
        test_content = {
            "title": "Digital India Initiative Progress Report",
            "content": "Digital India initiative has transformed governance through technology. Key achievements include digital payments growth, online service delivery, and rural connectivity improvements. The program supports financial inclusion and transparent governance mechanisms.",
            "enhancement_mode": "upsc_focused",
            "focus_areas": ["Governance", "Technology", "Rural Development"],
            "source_url": "https://example.com/digital-india"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/ai/enhance-content",
                    json=test_content,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    enhanced_data = data.get('data', {})
                    
                    return {
                        'success': data.get('success', False),
                        'upsc_relevance_score': enhanced_data.get('upsc_relevance', 0),
                        'focus_area_analysis': enhanced_data.get('focus_area_analysis', {}),
                        'question_bank': len(enhanced_data.get('potential_questions', []))
                    }
                else:
                    return {
                        'success': False,
                        'error': f'UPSC focused enhancement failed with status {response.status_code}'
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }

    async def test_rss_processing_flow(self) -> Dict[str, Any]:
        """Test complete RSS processing with content extraction flow"""
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/rss/process-all",
                    headers=self.headers,
                    timeout=120.0  # RSS processing can take longer
                )
                
                if response.status_code == 200:
                    data = response.json()
                    stats = data.get('stats', {})
                    
                    return {
                        'success': data.get('success', False),
                        'articles_processed': stats.get('articles_processed', 0),
                        'articles_saved': stats.get('articles_saved', 0),
                        'processing_time': stats.get('total_processing_time', 0),
                        'performance_metrics': data.get('performance_metrics', {})
                    }
                else:
                    return {
                        'success': False,
                        'error': f'RSS processing failed with status {response.status_code}'
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }

    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and edge cases"""
        
        test_cases = [
            {
                'name': 'Invalid URL extraction',
                'endpoint': '/api/content/extract-url',
                'data': {'url': 'invalid-url', 'strategy': 'auto'},
                'expected_status': 422
            },
            {
                'name': 'Empty content cleaning',
                'endpoint': '/api/content/clean',
                'data': {'title': '', 'content': ''},
                'expected_status': 200  # Should handle empty content gracefully
            },
            {
                'name': 'Invalid enhancement mode',
                'endpoint': '/api/ai/enhance-content',
                'data': {
                    'title': 'Test',
                    'content': 'Test content',
                    'enhancement_mode': 'invalid_mode'
                },
                'expected_status': 422
            }
        ]
        
        results = []
        
        async with httpx.AsyncClient() as client:
            for test_case in test_cases:
                try:
                    response = await client.post(
                        f"{self.base_url}{test_case['endpoint']}",
                        json=test_case['data'],
                        headers=self.headers
                    )
                    
                    results.append({
                        'test': test_case['name'],
                        'success': response.status_code == test_case['expected_status'],
                        'status_code': response.status_code,
                        'expected_status': test_case['expected_status']
                    })
                    
                except Exception as e:
                    results.append({
                        'test': test_case['name'],
                        'success': False,
                        'error': str(e)
                    })
        
        successful_error_tests = sum(1 for r in results if r.get('success', False))
        
        return {
            'success': successful_error_tests == len(test_cases),
            'results': results,
            'statistics': {
                'total_error_tests': len(test_cases),
                'passed_error_tests': successful_error_tests
            }
        }

    async def test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test performance benchmarks and response times"""
        
        benchmarks = []
        
        # Test single URL extraction performance
        start_time = time.time()
        single_url_result = await self.test_single_url_extraction()
        single_url_time = time.time() - start_time
        
        benchmarks.append({
            'test': 'Single URL Extraction',
            'response_time': single_url_time,
            'success': single_url_result.get('success', False)
        })
        
        # Test content cleaning performance
        start_time = time.time()
        cleaning_result = await self.test_content_cleaning()
        cleaning_time = time.time() - start_time
        
        benchmarks.append({
            'test': 'Content Cleaning',
            'response_time': cleaning_time,
            'success': cleaning_result.get('success', False)
        })
        
        # Performance analysis
        avg_response_time = sum(b['response_time'] for b in benchmarks) / len(benchmarks)
        
        return {
            'success': all(b['success'] for b in benchmarks),
            'benchmarks': benchmarks,
            'statistics': {
                'average_response_time': avg_response_time,
                'fastest_operation': min(benchmarks, key=lambda x: x['response_time'])['test'],
                'slowest_operation': max(benchmarks, key=lambda x: x['response_time'])['test']
            }
        }


async def main():
    """Main test execution function"""
    
    # Configuration
    BASE_URL = "http://localhost:8000"
    API_KEY = None  # Set your API key here if authentication is enabled
    
    # Initialize test suite
    test_suite = ContentPipelineTest(base_url=BASE_URL, api_key=API_KEY)
    
    # Run comprehensive tests
    test_results = await test_suite.run_all_tests()
    
    # Save results to file
    with open('content_pipeline_test_results.json', 'w') as f:
        json.dump(test_results, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("🧪 CONTENT PIPELINE TEST RESULTS")
    print("="*80)
    print(f"Total Tests: {test_results['statistics']['total_tests']}")
    print(f"Passed: {test_results['statistics']['passed_tests']}")
    print(f"Failed: {test_results['statistics']['failed_tests']}")
    print(f"Success Rate: {test_results['statistics']['success_rate']:.1f}%")
    print(f"Total Time: {test_results['statistics']['total_test_time']:.2f}s")
    print(f"Average Test Time: {test_results['statistics']['average_test_time']:.2f}s")
    
    if test_results['success']:
        print("\n✅ ALL TESTS PASSED - Content pipeline is ready for production!")
    else:
        print("\n❌ SOME TESTS FAILED - Review results and fix issues before deployment")
    
    print("\n📄 Detailed results saved to: content_pipeline_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())