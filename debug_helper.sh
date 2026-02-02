#!/bin/bash
# Quick debugging helper for the Google Maps Scraper

echo "==================================="
echo "Google Maps Scraper Debug Helper"
echo "==================================="
echo ""

# Check for debug files
echo "🔍 Checking for debug artifacts in /tmp..."
debug_files=$(ls /tmp/maps_debug_* 2>/dev/null | wc -l)

if [ $debug_files -eq 0 ]; then
    echo "✅ No debug files found (scraper working normally)"
else
    echo "⚠️  Found $debug_files debug file(s):"
    echo ""
    ls -lh /tmp/maps_debug_* 2>/dev/null
    echo ""
    echo "Recent failures:"
    ls -t /tmp/maps_debug_* 2>/dev/null | head -n 2
fi

echo ""
echo "==================================="
echo "Quick Actions:"
echo "==================================="
echo ""
echo "1. View latest screenshot:"
echo "   xdg-open \$(ls -t /tmp/maps_debug_*.png 2>/dev/null | head -n 1)"
echo ""
echo "2. View latest HTML:"
echo "   cat \$(ls -t /tmp/maps_debug_*.html 2>/dev/null | head -n 1) | less"
echo ""
echo "3. Clean debug files:"
echo "   rm /tmp/maps_debug_*"
echo ""
echo "4. Test scraper:"
echo "   python test_scraper.py"
echo ""
echo "5. Start FastAPI server:"
echo "   uvicorn gmaps_scraper_server.main_api:app --reload"
echo ""
