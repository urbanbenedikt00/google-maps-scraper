# Google Maps Scraper - Implementation Changes

## Overview
This document describes the major improvements made to fix zero-result issues and make the scraper resilient to Google Maps UI changes and EU consent flows.

## Problems Identified

### 1. Broken Consent Handling
**Issue**: The consent handling used XPath strings incorrectly with `wait_for_selector()`, which doesn't support XPath syntax without the `xpath=` prefix. This caused consent dialogs to be skipped, leading to the scraper being stuck on consent pages.

```python
# ❌ BROKEN - XPath string passed to wait_for_selector
consent_button_xpath = "//button[.//span[contains(text(), 'Accept all')]]"
await page.wait_for_selector(consent_button_xpath, state='visible', timeout=5000)
```

### 2. No Debug Output
**Issue**: When the scraper returned zero results, there was no diagnostic information to understand why. No screenshots, no HTML dumps, no URL logging.

### 3. Fragile DOM Assumptions
**Issue**: The scraper hard-coded dependency on `[role="feed"]` and would completely fail if this element wasn't present, even though place links might be available elsewhere in the DOM.

```python
# ❌ BROKEN - Hard fail on missing feed
if feed_element_not_found:
    return []  # No debug info, no fallback
```

## Solutions Implemented

### 1. Fixed Consent Handling ✅

**Location**: `scraper.py` lines 65-149

**Changes**:
- Created dedicated `handle_consent_dialog()` function
- Uses Playwright's recommended `get_by_role("button").filter(has_text=...)` API
- Supports multiple consent variants:
  - English: "Accept all", "Reject all", "I agree"
  - German: "Alle akzeptieren", "Alle ablehnen", "Akzeptieren"
- Properly waits for network idle after clicking
- Logs all consent attempts for visibility

**New Code**:
```python
# ✅ CORRECT - Uses Playwright locator API
button = page.get_by_role("button").filter(has_text="Accept all")
if await button.count() > 0:
    await button.first.click(timeout=5000)
    await page.wait_for_load_state('networkidle', timeout=8000)
```

### 2. Added Debug Artifacts ✅

**Location**: `scraper.py` lines 33-62

**Features**:
- New `save_debug_artifacts()` function
- Automatically saves:
  - Full-page screenshot (PNG)
  - Complete HTML DOM
  - Current page URL
- Files saved to `/tmp` (Docker-compatible) with fallback to current directory
- Timestamped filenames with failure reason: `maps_debug_YYYYMMDD_HHMMSS_reason.png`

**When Triggered**:
- Feed container `[role="feed"]` not found
- Zero results after all strategies exhausted

**Example Output**:
```
DEBUG: Screenshot saved to /tmp/maps_debug_20260202_143022_feed_not_found.png
DEBUG: HTML saved to /tmp/maps_debug_20260202_143022_feed_not_found.html
DEBUG: Current page URL: https://www.google.com/maps/search/...
```

### 3. Implemented DOM Fallback Strategy ✅

**Location**: `scraper.py` lines 152-207, 278-345

**Three-Tier Strategy**:

1. **Feed-based scrolling (Preferred)**
   - Uses `[role="feed"]` if present
   - Scrolls feed container
   - Extracts links from within feed

2. **Single place detection**
   - Detects if URL contains `/maps/place/`
   - Adds URL directly without scrolling

3. **Global DOM fallback**
   - Searches entire page for `/maps/place/` links
   - Uses mouse wheel scrolling for page-level navigation
   - Collects links across multiple layout variants

**New Function**:
```python
async def collect_place_links_global(page, max_places=None):
    """
    Collects place links from entire page DOM (fallback strategy).
    Does not assume specific DOM structure.
    """
    # Scrolls page and collects all /maps/place/ links
    all_links = await page.locator('a[href*="/maps/place/"]').evaluate_all(
        'elements => elements.map(a => a.href)'
    )
    # ...
```

### 4. Fixed XPath Usage ✅

**Location**: `scraper.py` line 315

**Change**: Added `xpath=` prefix when using XPath with locator

```python
# ❌ BEFORE - Incorrect XPath usage
if await page.locator(end_marker_xpath).count() > 0:

# ✅ AFTER - Correct XPath usage
if await page.locator(f"xpath={end_marker_xpath}").count() > 0:
```

## Preserved Behavior

✅ Async Playwright structure maintained  
✅ `headless=true` remains default  
✅ No external dependencies added  
✅ FastAPI interface unchanged  
✅ All existing parameters preserved  
✅ Return structure identical  

## Testing

### Run Test Suite
```bash
python test_scraper.py
```

### Test Cases Included
1. **Basic Search (DE)** - Tests German consent handling
2. **Single Place** - Tests specific place detection
3. **English Consent** - Tests English consent handling

### Manual Testing
```bash
# Start the FastAPI server
uvicorn gmaps_scraper_server.main_api:app --reload

# Test via API
curl -X POST "http://localhost:8000/scrape?query=restaurants%20in%20Berlin&max_places=5&lang=de"
```

## Debugging

### When Zero Results Occur

1. **Check debug files** in `/tmp`:
   ```bash
   ls -la /tmp/maps_debug_*
   ```

2. **Review screenshot** to see actual page state:
   ```bash
   # Copy from Docker container if needed
   docker cp <container_id>:/tmp/maps_debug_*.png .
   ```

3. **Examine HTML dump** to understand DOM structure:
   ```bash
   docker cp <container_id>:/tmp/maps_debug_*.html .
   ```

4. **Check logs** for:
   - Consent handling messages
   - Feed detection status
   - Fallback strategy activation
   - Final URL

### Common Failure Patterns

| Symptom | Debug File | Likely Cause | Solution |
|---------|-----------|--------------|----------|
| Zero results | `feed_not_found.png` | Consent not handled | Check screenshot for consent dialog |
| Zero results | `zero_results.png` | Wrong search query | Review query syntax |
| Timeout | N/A | Network issues | Check Docker networking |

## Docker Compatibility

All features work in headless Docker environment:

```dockerfile
# Dockerfile already has required Playwright dependencies
FROM python:3.11-slim
# ... Playwright browsers installed ...
```

### Volume Mount for Debug Files
```yaml
# docker-compose.yml
services:
  scraper:
    volumes:
      - ./debug_output:/tmp  # Mount /tmp to view debug files
```

## API Usage (Unchanged)

```python
# POST /scrape
{
  "query": "restaurants in Berlin",
  "max_places": 10,
  "lang": "de",
  "headless": true
}

# Response
[
  {
    "name": "Restaurant Name",
    "rating": 4.5,
    "address": "...",
    "link": "https://www.google.com/maps/place/..."
    // ... other fields
  }
]
```

## Performance Considerations

- **Fallback strategy** adds ~10-20 seconds if feed not found
- **Debug artifacts** add ~2-3 seconds when triggered
- **Mouse wheel scrolling** is slightly slower than feed scrolling
- Overall impact: Minimal for successful scrapes, acceptable for failures

## Future Improvements

- [ ] Add more consent text variants for other languages (FR, ES, IT)
- [ ] Implement retry logic for transient network failures
- [ ] Add configurable debug output directory
- [ ] Optimize fallback scrolling with viewport detection
- [ ] Add metrics/telemetry for monitoring consent success rates

## Change Summary

| Component | Status | Lines Changed |
|-----------|--------|---------------|
| Consent handling | ✅ Rewritten | ~85 lines |
| Debug artifacts | ✅ New feature | ~30 lines |
| DOM fallback | ✅ New feature | ~55 lines |
| XPath fixes | ✅ Fixed | ~5 lines |
| Documentation | ✅ Complete | ~70 lines |

---

**Last Updated**: February 2, 2026  
**Author**: Backend & Web Scraping Engineering Team  
**Version**: 2.0.0 (Resilient Implementation)
