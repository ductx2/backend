#!/usr/bin/env python3
"""
Simple API Endpoint Audit
"""

import sys
import re
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main audit function"""
    api_dir = Path(__file__).parent / "app" / "api"
    
    print("=" * 50)
    print("API ENDPOINT AUDIT")
    print("=" * 50)
    
    endpoints = []
    
    # Get all Python files
    api_files = [f for f in api_dir.glob("*.py") if f.name != "__init__.py"]
    
    for api_file in api_files:
        print(f"\nFile: {api_file.name}")
        
        try:
            with open(api_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find router decorators
            pattern = r'@router\.(get|post|put|delete|patch)\("([^"]+)"'
            matches = re.findall(pattern, content)
            
            for method, path in matches:
                endpoint = f"{method.upper()} {path}"
                endpoints.append((api_file.name, endpoint))
                print(f"  {endpoint}")
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print(f"\n{'-'*50}")
    print("SUMMARY")
    print(f"{'-'*50}")
    
    # Group by category
    rss_count = sum(1 for _, ep in endpoints if 'rss' in ep.lower())
    drishti_count = sum(1 for _, ep in endpoints if 'drishti' in ep.lower())
    unified_count = sum(1 for _, ep in endpoints if 'unified' in ep.lower())
    extraction_count = sum(1 for _, ep in endpoints if 'extract' in ep.lower())
    ai_count = sum(1 for _, ep in endpoints if '/ai/' in ep.lower())
    automation_count = sum(1 for _, ep in endpoints if 'automation' in ep.lower())
    current_affairs_count = sum(1 for _, ep in endpoints if 'current-affairs' in ep.lower())
    
    print(f"RSS endpoints: {rss_count}")
    print(f"Drishti endpoints: {drishti_count}")
    print(f"Unified endpoints: {unified_count}")
    print(f"Extraction endpoints: {extraction_count}")
    print(f"AI endpoints: {ai_count}")
    print(f"Automation endpoints: {automation_count}")
    print(f"Current Affairs endpoints: {current_affairs_count}")
    
    total = len(endpoints)
    print(f"\nTotal endpoints: {total}")
    
    if total > 20:
        print("STATUS: TOO MANY ENDPOINTS - Needs simplification")
    elif total > 15:
        print("STATUS: HIGH COMPLEXITY - Consider consolidation")
    else:
        print("STATUS: REASONABLE COMPLEXITY")
    
    print("\n" + "=" * 50)
    print("SIMPLIFICATION RECOMMENDATIONS")
    print("=" * 50)
    
    print("""
RECOMMENDED 5-STEP LINEAR FLOW:

1. POST /api/rss/extract           # Raw RSS extraction
2. POST /api/ai/analyze            # UPSC relevance analysis  
3. POST /api/content/extract       # Full content extraction
4. POST /api/ai/refine            # AI content refinement
5. POST /api/database/save        # Database storage

KEEP ESSENTIAL ENDPOINTS:
- GET /api/health                  # Health checks
- GET /api/current-affairs/{date}  # Data retrieval
- POST /api/automation/daily       # Daily automation

ELIMINATE REDUNDANT ENDPOINTS:
- Multiple RSS processing endpoints
- Overlapping unified processors
- Duplicate extraction endpoints

TARGET: Reduce to 10-12 focused endpoints maximum
    """)

if __name__ == "__main__":
    main()