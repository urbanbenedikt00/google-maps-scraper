# Quick debugging helper for the Google Maps Scraper (Windows/PowerShell)

Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Google Maps Scraper Debug Helper" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

# Check for debug files (in current directory as fallback on Windows)
Write-Host "🔍 Checking for debug artifacts..." -ForegroundColor Yellow

$debugFiles = Get-ChildItem -Path . -Filter "maps_debug_*" -ErrorAction SilentlyContinue

if ($debugFiles.Count -eq 0) {
    Write-Host "✅ No debug files found (scraper working normally)" -ForegroundColor Green
} else {
    Write-Host "⚠️  Found $($debugFiles.Count) debug file(s):" -ForegroundColor Yellow
    Write-Host ""
    $debugFiles | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
    Write-Host ""
    Write-Host "Most recent failures:" -ForegroundColor Yellow
    $debugFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 2 | Format-Table Name, LastWriteTime
}

Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host "Quick Actions:" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. View latest screenshot:" -ForegroundColor White
Write-Host "   `$latest = Get-ChildItem -Filter 'maps_debug_*.png' | Sort-Object LastWriteTime -Descending | Select-Object -First 1" -ForegroundColor Gray
Write-Host "   Start-Process `$latest.FullName" -ForegroundColor Gray
Write-Host ""

Write-Host "2. View latest HTML:" -ForegroundColor White
Write-Host "   `$latest = Get-ChildItem -Filter 'maps_debug_*.html' | Sort-Object LastWriteTime -Descending | Select-Object -First 1" -ForegroundColor Gray
Write-Host "   Get-Content `$latest.FullName | Out-Host -Paging" -ForegroundColor Gray
Write-Host ""

Write-Host "3. Clean debug files:" -ForegroundColor White
Write-Host "   Remove-Item maps_debug_*" -ForegroundColor Gray
Write-Host ""

Write-Host "4. Test scraper:" -ForegroundColor White
Write-Host "   python test_scraper.py" -ForegroundColor Gray
Write-Host ""

Write-Host "5. Start FastAPI server:" -ForegroundColor White
Write-Host "   uvicorn gmaps_scraper_server.main_api:app --reload" -ForegroundColor Gray
Write-Host ""

Write-Host "6. Test via API (requires running server):" -ForegroundColor White
Write-Host "   Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/scrape?query=restaurants%20in%20Berlin&max_places=5' | ConvertTo-Json" -ForegroundColor Gray
Write-Host ""

# Offer to view latest screenshot if available
$latestScreenshot = Get-ChildItem -Filter "maps_debug_*.png" -ErrorAction SilentlyContinue | 
                    Sort-Object LastWriteTime -Descending | 
                    Select-Object -First 1

if ($latestScreenshot) {
    Write-Host ""
    Write-Host "📸 Latest screenshot found: $($latestScreenshot.Name)" -ForegroundColor Cyan
    Write-Host "   Last modified: $($latestScreenshot.LastWriteTime)" -ForegroundColor Gray
    $response = Read-Host "Open it now? (y/n)"
    if ($response -eq 'y') {
        Start-Process $latestScreenshot.FullName
    }
}
