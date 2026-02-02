"""
Google Maps Scraper - Resilient Implementation with Robust Error Handling

=== MAJOR CHANGES IMPLEMENTED ===

1. FIXED CONSENT HANDLING (Lines 65-149)
   Problem: Previous implementation used XPath strings incorrectly with wait_for_selector(),
            which doesn't support XPath syntax directly. Also had incomplete language support.
   
   Solution: 
   - Replaced with handle_consent_dialog() function using Playwright's locator API
   - Uses get_by_role("button").filter(has_text=...) for robust text matching
   - Supports multiple consent variants: EN ("Accept all", "Reject all") and 
     DE ("Alle akzeptieren", "Alle ablehnen")
   - Properly waits for network idle after clicking consent
   - No longer silently fails on consent - logs all attempts

2. ADDED DEBUG ARTIFACT GENERATION (Lines 33-62)
   Problem: When scraper returned zero results, there was no way to diagnose why
   
   Solution:
   - New save_debug_artifacts() function saves screenshot + HTML on failure
   - Automatically triggered when [role="feed"] not found or zero results
   - Saves to /tmp (Docker-compatible) with fallback to current directory
   - Files timestamped and named by failure reason (e.g., maps_debug_20260202_120000_feed_not_found.png)
   - Always logs final resolved URL for debugging

3. IMPLEMENTED DOM FALLBACK STRATEGY (Lines 152-207, 278-345)
   Problem: Hard-coded dependency on [role="feed"] caused complete failure on layout changes
   
   Solution:
   - New collect_place_links_global() fallback function
   - No longer fails if feed container missing - tries global /maps/place/ link collection
   - Uses page.mouse.wheel() for scrolling (more reliable than scrollTo in varied layouts)
   - Three-tier strategy:
     a) Feed-based scrolling (preferred, if [role="feed"] exists)
     b) Single place page detection (if URL contains /maps/place/)
     c) Global DOM fallback (searches entire page for place links)
   - Fixed XPath usage in end-of-list detection (line 315: added xpath= prefix)

4. PRESERVED EXISTING BEHAVIOR
   - Maintained async Playwright structure
   - Kept headless=true as default
   - No external dependencies added (no stealth plugins or proxies)
   - FastAPI interface unchanged
   - All existing parameters and return structure preserved

5. IMPROVED LOGGING AND VISIBILITY
   - Added progress messages for each strategy (feed-based, fallback, etc.)
   - Clear indication when consent is handled
   - Debug artifacts automatically saved with descriptive names
   - Final URL always logged to help diagnose redirect issues

=== TESTING RECOMMENDATIONS ===
- Test with EU region to verify consent handling (DE/EN)
- Test with queries that return zero results to verify debug artifacts
- Test with single place result to verify direct URL handling
- Monitor /tmp directory for debug screenshots/HTML on failures

=== DOCKER COMPATIBILITY ===
- All features work in headless mode without X server
- Debug files save to /tmp (standard Docker volume mount point)
- Screenshot generation works without display (Playwright supports this natively)
"""

import json
import asyncio # Changed from time
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError # Changed to async
from urllib.parse import urlencode
from pathlib import Path
from datetime import datetime

# Import the extraction functions from our helper module
from . import extractor

# --- Constants ---
BASE_URL = "https://www.google.com/maps/search/"
DEFAULT_TIMEOUT = 30000  # 30 seconds for navigation and selectors
SCROLL_PAUSE_TIME = 1.5  # Pause between scrolls
MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS = 5 # Stop scrolling if no new links found after this many scrolls

# Debug output directory (Docker-compatible)
DEBUG_DIR = Path("/tmp")
if not DEBUG_DIR.exists():
    DEBUG_DIR = Path(".") # Fallback to current directory if /tmp doesn't exist

# --- Helper Functions ---
def create_search_url(query, lang="en", geo_coordinates=None, zoom=None):
    """Creates a Google Maps search URL."""
    params = {'q': query, 'hl': lang}
    # Note: geo_coordinates and zoom might require different URL structure (/maps/@lat,lng,zoom)
    # For simplicity, starting with basic query search
    return BASE_URL + "?" + urlencode(params)


async def save_debug_artifacts(page, reason="unknown"):
    """
    Saves debugging artifacts when scraping fails.
    
    CHANGE: New function added to capture full page state on failure.
    Saves both screenshot and HTML DOM to disk for post-mortem analysis.
    
    Args:
        page: Playwright page object
        reason: String describing why debug artifacts are being saved
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        # Save screenshot
        screenshot_path = DEBUG_DIR / f"maps_debug_{timestamp}_{reason}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"DEBUG: Screenshot saved to {screenshot_path}")
        
        # Save HTML
        html_path = DEBUG_DIR / f"maps_debug_{timestamp}_{reason}.html"
        html_content = await page.content()
        html_path.write_text(html_content, encoding='utf-8')
        print(f"DEBUG: HTML saved to {html_path}")
        
        # Log current URL
        current_url = page.url
        print(f"DEBUG: Current page URL: {current_url}")
        
    except Exception as e:
        print(f"ERROR: Failed to save debug artifacts: {e}")


async def handle_consent_dialog(page):
    """
    Handles Google consent dialogs in both English and German.
    
    CHANGE: Complete rewrite of consent handling logic.
    - Uses proper Playwright locator API instead of incorrect XPath with wait_for_selector
    - Supports multiple consent button variants in EN and DE
    - Uses text-based matching with case-insensitive partial matching
    - Reliably clicks consent buttons using Playwright's auto-wait mechanisms
    
    Previous implementation issues:
    - Used XPath strings directly with wait_for_selector (not supported)
    - Only tried query_selector which doesn't auto-wait
    - Had incomplete consent text matching
    
    Args:
        page: Playwright page object
        
    Returns:
        bool: True if consent was handled, False if no consent dialog found
    """
    try:
        print("Checking for consent dialog...")
        
        # Define consent button texts in multiple languages
        # These are common patterns found in Google's consent forms
        accept_texts = [
            "Accept all",
            "Alle akzeptieren",
            "I agree",
            "Ich stimme zu",
            "Akzeptieren"
        ]
        
        reject_texts = [
            "Reject all", 
            "Alle ablehnen",
            "Ablehnen"
        ]
        
        # Try to find and click Accept button (preferred)
        for text in accept_texts:
            try:
                # Use Playwright's text-based locator with case-insensitive matching
                # This is more robust than XPath and handles nested elements correctly
                button = page.get_by_role("button").filter(has_text=text)
                if await button.count() > 0:
                    print(f"Found consent button with text: '{text}' - clicking...")
                    await button.first.click(timeout=5000)
                    # Wait for navigation/dialog dismissal
                    await page.wait_for_load_state('networkidle', timeout=8000)
                    print("Consent accepted successfully")
                    return True
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                print(f"Error clicking accept button '{text}': {e}")
                continue
        
        # If Accept not found, try Reject as fallback
        for text in reject_texts:
            try:
                button = page.get_by_role("button").filter(has_text=text)
                if await button.count() > 0:
                    print(f"Found consent button with text: '{text}' - clicking...")
                    await button.first.click(timeout=5000)
                    await page.wait_for_load_state('networkidle', timeout=8000)
                    print("Consent rejected successfully")
                    return True
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                print(f"Error clicking reject button '{text}': {e}")
                continue
        
        print("No consent dialog detected")
        return False
        
    except Exception as e:
        print(f"Error during consent handling: {e}")
        return False


async def collect_place_links_global(page, max_places=None):
    """
    Collects place links from the entire page DOM (fallback strategy).
    
    CHANGE: New fallback function when [role="feed"] is not found.
    - Searches entire page for /maps/place/ links
    - Does not assume specific DOM structure
    - Performs page-level scrolling using mouse wheel simulation
    - More resilient to Google Maps layout changes
    
    Args:
        page: Playwright page object
        max_places: Maximum number of links to collect
        
    Returns:
        set: Unique place URLs found on the page
    """
    print("Using global DOM fallback strategy to collect place links...")
    place_links = set()
    scroll_attempts_no_new = 0
    
    # Perform page-level scrolling
    for scroll_iteration in range(20):  # Max 20 scroll attempts
        # Extract all /maps/place/ links from the entire page
        try:
            all_links = await page.locator('a[href*="/maps/place/"]').evaluate_all(
                'elements => elements.map(a => a.href)'
            )
            current_links = set(all_links)
            new_links_found = len(current_links - place_links) > 0
            place_links.update(current_links)
            
            print(f"Global fallback: Found {len(place_links)} unique place links (iteration {scroll_iteration + 1})")
            
            if max_places and len(place_links) >= max_places:
                print(f"Reached max_places limit ({max_places}) in global fallback")
                break
                
            if not new_links_found:
                scroll_attempts_no_new += 1
                if scroll_attempts_no_new >= MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS:
                    print("Global fallback: Stopping due to no new links found")
                    break
            else:
                scroll_attempts_no_new = 0
            
            # Scroll the page using mouse wheel (works more reliably than scrollTo in some layouts)
            await page.mouse.wheel(0, 3000)
            await asyncio.sleep(SCROLL_PAUSE_TIME)
            
        except Exception as e:
            print(f"Error during global link collection: {e}")
            break
    
    return place_links

# --- Main Scraping Logic ---
async def scrape_google_maps(query, max_places=None, lang="en", headless=True): # Added async
    """
    Scrapes Google Maps for places based on a query.

    Args:
        query (str): The search query (e.g., "restaurants in New York").
        max_places (int, optional): Maximum number of places to scrape. Defaults to None (scrape all found).
        lang (str, optional): Language code for Google Maps (e.g., 'en', 'es'). Defaults to "en".
        headless (bool, optional): Whether to run the browser in headless mode. Defaults to True.

    Returns:
        list: A list of dictionaries, each containing details for a scraped place.
              Returns an empty list if no places are found or an error occurs.
    """
    results = []
    place_links = set()
    scroll_attempts_no_new = 0
    browser = None

    async with async_playwright() as p: # Changed to async
        try:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-dev-shm-usage',  # Use /tmp instead of /dev/shm for shared memory
                    '--no-sandbox',  # Required for running in Docker
                    '--disable-setuid-sandbox',
                ]
            ) # Added await
            context = await browser.new_context( # Added await
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                java_script_enabled=True,
                accept_downloads=False,
                # Consider setting viewport, locale, timezone if needed
                locale=lang,
            )
            page = await context.new_page() # Added await
            if not page:
                await browser.close() # Close browser before raising
                raise Exception("Failed to create a new browser page (context.new_page() returned None).")
            # Removed problematic: await page.set_default_timeout(DEFAULT_TIMEOUT)
            # Removed associated debug prints

            search_url = create_search_url(query, lang)
            print(f"Navigating to search URL: {search_url}")
            await page.goto(search_url, wait_until='domcontentloaded') # Added await
            await asyncio.sleep(2) # Changed to asyncio.sleep, added await

            # --- Handle potential consent forms ---
            # CHANGE: Replaced broken XPath-based consent handling with robust locator-based approach
            # Now properly handles EN/DE consent variants and uses Playwright's recommended APIs
            await handle_consent_dialog(page)

            # --- Scrolling and Link Extraction ---
            # CHANGE: Major refactoring of link collection strategy
            # - No longer hard-fails when [role="feed"] is missing
            # - Implements fallback strategy using global DOM search
            # - Saves debug artifacts (screenshot + HTML) when feed not found
            # - Logs final resolved URL for debugging
            
            print("Scrolling to load places...")
            feed_selector = '[role="feed"]'
            feed_found = False
            
            try:
                await page.wait_for_selector(feed_selector, state='visible', timeout=25000)
                feed_found = True
                print(f"Feed container found: {feed_selector}")
            except PlaywrightTimeoutError:
                # Check if it's a single result page (maps/place/)
                current_url = page.url
                print(f"Feed element '{feed_selector}' not found. Current URL: {current_url}")
                
                if "/maps/place/" in current_url:
                    print("Detected single place page - adding URL directly")
                    place_links.add(current_url)
                    feed_found = False  # Skip feed scrolling
                else:
                    print("WARNING: Feed container not detected - will attempt fallback strategy")
                    # Save debug artifacts before attempting fallback
                    await save_debug_artifacts(page, "feed_not_found")
                    feed_found = False

            # Strategy 1: Feed-based scrolling (preferred)
            if feed_found and await page.locator(feed_selector).count() > 0:
                print("Using feed-based scrolling strategy...")
                last_height = await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollHeight')
                while True:
                    # Scroll down
                    await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollTop = document.querySelector(\'{feed_selector}\').scrollHeight')
                    await asyncio.sleep(SCROLL_PAUSE_TIME)

                    # Extract links after scroll
                    current_links_list = await page.locator(f'{feed_selector} a[href*="/maps/place/"]').evaluate_all('elements => elements.map(a => a.href)')
                    current_links = set(current_links_list)
                    new_links_found = len(current_links - place_links) > 0
                    place_links.update(current_links)
                    print(f"Found {len(place_links)} unique place links so far...")

                    if max_places is not None and len(place_links) >= max_places:
                        print(f"Reached max_places limit ({max_places}).")
                        place_links = set(list(place_links)[:max_places]) # Trim excess links
                        break

                    # Check if scroll height has changed
                    new_height = await page.evaluate(f'document.querySelector(\'{feed_selector}\').scrollHeight')
                    if new_height == last_height:
                        # Check for the "end of results" marker
                        end_marker_xpath = "//span[contains(text(), \"You've reached the end of the list.\")]"
                        if await page.locator(f"xpath={end_marker_xpath}").count() > 0:  # CHANGE: Fixed XPath usage
                            print("Reached the end of the results list.")
                            break
                        else:
                            # If height didn't change but end marker isn't there, maybe loading issue?
                            # Increment no-new-links counter
                            if not new_links_found:
                                scroll_attempts_no_new += 1
                                print(f"Scroll height unchanged and no new links. Attempt {scroll_attempts_no_new}/{MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS}")
                                if scroll_attempts_no_new >= MAX_SCROLL_ATTEMPTS_WITHOUT_NEW_LINKS:
                                    print("Stopping scroll due to lack of new links.")
                                    break
                            else:
                                scroll_attempts_no_new = 0 # Reset if new links were found this cycle
                    else:
                        last_height = new_height
                        scroll_attempts_no_new = 0 # Reset if scroll height changed

            # Strategy 2: Global fallback when feed not found or single place page not detected
            elif not feed_found and "/maps/place/" not in page.url:
                place_links = await collect_place_links_global(page, max_places)
                
            # If still no links found, save debug artifacts and log final state
            if len(place_links) == 0:
                print("ERROR: No place links found after all strategies")
                await save_debug_artifacts(page, "zero_results")
                print(f"Final page URL: {page.url}")
                # Don't return empty immediately - continue to see if there's data to extract

            # --- Scraping Individual Places ---
            print(f"\nScraping details for {len(place_links)} places...")
            count = 0
            for link in place_links:
                count += 1
                print(f"Processing link {count}/{len(place_links)}: {link}") # Keep sync print
                try:
                    await page.goto(link, wait_until='domcontentloaded') # Added await
                    # Wait a bit for dynamic content if needed, or wait for a specific element
                    # await page.wait_for_load_state('networkidle', timeout=10000) # Or networkidle if needed

                    html_content = await page.content() # Added await
                    place_data = extractor.extract_place_data(html_content)

                    if place_data:
                        place_data['link'] = link # Add the source link
                        results.append(place_data)
                        # print(json.dumps(place_data, indent=2)) # Optional: print data as it's scraped
                    else:
                        print(f"  - Failed to extract data for: {link}")
                        # Optionally save the HTML for debugging
                        # with open(f"error_page_{count}.html", "w", encoding="utf-8") as f:
                        #     f.write(html_content)

                except PlaywrightTimeoutError:
                    print(f"  - Timeout navigating to or processing: {link}")
                except Exception as e:
                    print(f"  - Error processing {link}: {e}")
                await asyncio.sleep(0.5) # Changed to asyncio.sleep, added await

            await browser.close() # Added await

        except PlaywrightTimeoutError:
            print(f"Timeout error during scraping process.")
        except Exception as e:
            print(f"An error occurred during scraping: {e}")
            import traceback
            traceback.print_exc() # Print detailed traceback for debugging
        finally:
            # Ensure browser is closed if an error occurred mid-process
            if browser and browser.is_connected(): # Check if browser exists and is connected
                await browser.close() # Added await

    print(f"\nScraping finished. Found details for {len(results)} places.")
    return results

# --- Example Usage ---
# (Example usage block removed as this script is now intended to be imported as a module)