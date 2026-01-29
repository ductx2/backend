#!/usr/bin/env python3
"""
FastAPI Backend Endpoint Audit
Analyzes all current endpoints and identifies redundancies

Created: 2025-08-31
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

def analyze_api_files():
    """Analyze all API files and extract endpoints"""
    
    api_dir = Path(__file__).parent / "app" / "api"
    
    if not api_dir.exists():
        print("ERROR: API directory not found")
        return
    
    print("=" * 60)
    print("FASTAPI BACKEND ENDPOINT AUDIT")
    print("=" * 60)
    
    endpoints = {}
    
    # Get all Python files in API directory
    api_files = list(api_dir.glob("*.py"))
    api_files = [f for f in api_files if f.name != "__init__.py"]
    
    print(f"\nFound {len(api_files)} API files:")
    
    for api_file in api_files:
        print(f"  • {api_file.name}")
        
        # Read file and extract route definitions
        try:
            with open(api_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_endpoints = extract_endpoints_from_content(content, api_file.name)
            endpoints[api_file.name] = file_endpoints
            
        except Exception as e:
            print(f"    ERROR reading {api_file.name}: {e}")
    
    # Analyze endpoints
    print("\n" + "=" * 60)
    print("ENDPOINT ANALYSIS")
    print("=" * 60)
    
    all_endpoints = []
    
    for file_name, file_endpoints in endpoints.items():
        print(f"\n📁 {file_name}:")
        
        for endpoint in file_endpoints:
            print(f"  {endpoint['method']} {endpoint['path']} - {endpoint['function']}")
            all_endpoints.append({
                'file': file_name,
                'method': endpoint['method'],
                'path': endpoint['path'],
                'function': endpoint['function'],
                'description': endpoint.get('description', '')
            })
    
    # Find potential duplicates and analyze flow
    analyze_endpoint_relationships(all_endpoints)

def extract_endpoints_from_content(content, filename):
    """Extract endpoint definitions from file content"""
    import re
    
    endpoints = []
    
    # Patterns to match FastAPI route decorators
    patterns = [
        r'@router\.(get|post|put|delete|patch)\("([^"]+)"[^)]*\)',
        r'@router\.(get|post|put|delete|patch)\(\'([^\']+)\'[^)]*\)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Try to find the function name (next non-decorator line)
            start_pos = match.end()
            remaining_content = content[start_pos:]
            
            # Look for async def or def
            func_match = re.search(r'async\s+def\s+(\w+)|def\s+(\w+)', remaining_content)
            function_name = "unknown"
            
            if func_match:
                function_name = func_match.group(1) or func_match.group(2)
            
            endpoints.append({
                'method': method,
                'path': path,
                'function': function_name,
                'description': ''
            })
    
    return endpoints

def analyze_endpoint_relationships(endpoints):
    """Analyze relationships and potential issues"""
    
    print("\n" + "=" * 60)
    print("ENDPOINT RELATIONSHIP ANALYSIS")
    print("=" * 60)
    
    # Group by functionality
    rss_endpoints = [e for e in endpoints if 'rss' in e['path'].lower() or 'rss' in e['function'].lower()]
    drishti_endpoints = [e for e in endpoints if 'drishti' in e['path'].lower()]
    unified_endpoints = [e for e in endpoints if 'unified' in e['path'].lower()]
    current_affairs_endpoints = [e for e in endpoints if 'current-affairs' in e['path']]
    automation_endpoints = [e for e in endpoints if 'automation' in e['path']]
    extraction_endpoints = [e for e in endpoints if 'extract' in e['path']]
    ai_endpoints = [e for e in endpoints if '/ai/' in e['path']]
    
    categories = {
        "RSS Processing": rss_endpoints,
        "Drishti Scraping": drishti_endpoints,
        "Unified Processing": unified_endpoints,
        "Current Affairs": current_affairs_endpoints,
        "Automation": automation_endpoints,
        "Content Extraction": extraction_endpoints,
        "AI Processing": ai_endpoints
    }
    
    print("\n📊 ENDPOINTS BY CATEGORY:")
    
    for category, category_endpoints in categories.items():
        if category_endpoints:
            print(f"\n🏷️  {category} ({len(category_endpoints)} endpoints):")
            for ep in category_endpoints:
                print(f"   {ep['method']} {ep['path']} ({ep['file']})")
    
    # Identify potential issues
    print("\n" + "=" * 60)
    print("POTENTIAL ISSUES IDENTIFIED")
    print("=" * 60)
    
    # Check for similar paths
    similar_paths = find_similar_paths(endpoints)
    if similar_paths:
        print("\n⚠️  SIMILAR/OVERLAPPING PATHS:")
        for group in similar_paths:
            print(f"   Group: {[ep['path'] for ep in group]}")
    
    # Check for too many endpoints in one category
    print(f"\n📈 COMPLEXITY ANALYSIS:")
    for category, category_endpoints in categories.items():
        count = len(category_endpoints)
        if count > 5:
            print(f"   ⚠️  {category}: {count} endpoints (consider consolidation)")
        elif count > 0:
            print(f"   ✅ {category}: {count} endpoints (reasonable)")
    
    # Total count
    total_endpoints = len(endpoints)
    print(f"\n📊 TOTAL ENDPOINTS: {total_endpoints}")
    
    if total_endpoints > 25:
        print("   ⚠️  HIGH COMPLEXITY: Consider simplifying API structure")
    elif total_endpoints > 15:
        print("   ⚠️  MODERATE COMPLEXITY: Monitor for redundancy")
    else:
        print("   ✅ REASONABLE COMPLEXITY: Well-structured API")

def find_similar_paths(endpoints):
    """Find endpoints with similar paths that might be redundant"""
    similar_groups = []
    processed = set()
    
    for i, ep1 in enumerate(endpoints):
        if i in processed:
            continue
            
        similar = [ep1]
        
        for j, ep2 in enumerate(endpoints):
            if i != j and j not in processed:
                # Check if paths are similar (excluding exact matches)
                if paths_are_similar(ep1['path'], ep2['path']) and ep1['path'] != ep2['path']:
                    similar.append(ep2)
                    processed.add(j)
        
        if len(similar) > 1:
            similar_groups.append(similar)
            processed.add(i)
    
    return similar_groups

def paths_are_similar(path1, path2):
    """Check if two paths are functionally similar"""
    # Remove parameters and normalize
    p1_clean = path1.split('?')[0].rstrip('/').lower()
    p2_clean = path2.split('?')[0].rstrip('/').lower()
    
    # Check for substring matches or similar keywords
    p1_words = set(p1_clean.split('/'))
    p2_words = set(p2_clean.split('/'))
    
    # If they share significant words, they might be similar
    common_words = p1_words.intersection(p2_words)
    
    return len(common_words) >= 2

def main():
    """Main audit function"""
    analyze_api_files()
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    print("""
SIMPLIFICATION RECOMMENDATIONS:

1. 🎯 CREATE 5-STEP LINEAR FLOW:
   Step 1: POST /api/rss/extract-raw         (RSS extraction only)
   Step 2: POST /api/ai/analyze-relevance    (UPSC filtering)  
   Step 3: POST /api/content/extract-full    (Full content extraction)
   Step 4: POST /api/ai/refine-content       (AI enhancement)
   Step 5: POST /api/database/save           (Database storage)

2. 🗑️  ELIMINATE REDUNDANT ENDPOINTS:
   - Keep only the working endpoints from each category
   - Remove overlapping functionality
   - Consolidate similar operations

3. 🔄 KEEP ESSENTIAL ENDPOINTS:
   - Health checks (/api/health)
   - Authentication (/api/auth/*)
   - Data retrieval (/api/current-affairs/{date})
   - Manual triggers for admins

4. 📊 MAINTAIN MONITORING:
   - Performance metrics endpoints
   - System status endpoints
   - Statistics and analytics

GOAL: Reduce from 20+ endpoints to ~10 clear, focused endpoints
    """)

if __name__ == "__main__":
    main()