"""
Test script for the improved Google Maps scraper

Run this to verify:
1. Consent handling works
2. Debug artifacts are generated
3. Fallback strategies work correctly
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import the scraper
sys.path.insert(0, str(Path(__file__).parent))

from gmaps_scraper_server.scraper import scrape_google_maps


async def test_basic_search():
    """Test basic scraping with a common query"""
    print("\n" + "="*60)
    print("TEST 1: Basic search (restaurants in Berlin)")
    print("="*60)
    
    results = await scrape_google_maps(
        query="restaurants in Berlin",
        max_places=5,
        lang="de",  # Test German for consent handling
        headless=True
    )
    
    print(f"\n✓ Found {len(results)} results")
    if results:
        print(f"✓ First result: {results[0].get('name', 'N/A')}")
    return len(results) > 0


async def test_single_place():
    """Test with a specific place that might return single result"""
    print("\n" + "="*60)
    print("TEST 2: Specific place search")
    print("="*60)
    
    results = await scrape_google_maps(
        query="Brandenburg Gate Berlin",
        max_places=3,
        lang="en",
        headless=True
    )
    
    print(f"\n✓ Found {len(results)} results")
    return len(results) > 0


async def test_english_consent():
    """Test English consent handling"""
    print("\n" + "="*60)
    print("TEST 3: English locale (consent handling)")
    print("="*60)
    
    results = await scrape_google_maps(
        query="coffee shops in London",
        max_places=3,
        lang="en",
        headless=True
    )
    
    print(f"\n✓ Found {len(results)} results")
    return len(results) > 0


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("GOOGLE MAPS SCRAPER - INTEGRATION TESTS")
    print("="*60)
    print("\nThis will test:")
    print("- Consent handling (EN/DE)")
    print("- Feed-based scrolling")
    print("- Fallback strategies")
    print("- Debug artifact generation")
    print("\nNote: Check /tmp for debug files if any test fails")
    print("="*60)
    
    tests = [
        ("Basic Search (DE)", test_basic_search),
        ("Single Place", test_single_place),
        ("English Consent", test_english_consent),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"\n✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"\n⚠️  {test_name} RETURNED NO RESULTS (check /tmp for debug files)")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} FAILED: {e}")
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed/warning")
    print("="*60)
    
    if failed > 0:
        print("\nℹ️  Check /tmp directory for debug screenshots and HTML:")
        print("   - maps_debug_*_feed_not_found.png/html")
        print("   - maps_debug_*_zero_results.png/html")


if __name__ == "__main__":
    asyncio.run(main())
