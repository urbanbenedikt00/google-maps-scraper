import json
import re

def safe_get(data, *keys):
    """
    Safely retrieves nested data from a dictionary or list using a sequence of keys/indices.
    Returns None if any key/index is not found or if the data structure is invalid.
    """
    current = data
    for key in keys:
        try:
            if isinstance(current, list):
                if isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    # print(f"Index {key} out of bounds or invalid for list.")
                    return None
            elif isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    # print(f"Key {key} not found in dict.")
                    return None
            else:
                # print(f"Cannot access key {key} on non-dict/list item: {type(current)}")
                return None
        except (IndexError, TypeError, KeyError) as e:
            # print(f"Error accessing key {key}: {e}")
            return None
    return current

def extract_initial_json(html_content):
    """
    Extracts the JSON string assigned to window.APP_INITIALIZATION_STATE from HTML content.
    """
    try:
        match = re.search(r';window\.APP_INITIALIZATION_STATE\s*=\s*(.*?);window\.APP_FLAGS', html_content, re.DOTALL)
        if match:
            json_str = match.group(1)
            if json_str.strip().startswith(('[', '{')):
                return json_str
            else:
                print("Extracted content doesn't look like valid JSON start.")
                return None
        else:
            print("APP_INITIALIZATION_STATE pattern not found.")
            return None
    except Exception as e:
        print(f"Error extracting JSON string: {e}")
        return None

def parse_json_data(json_str):
    """
    Parses the extracted JSON string, handling the nested JSON string if present.
    Returns the main data blob (list) or None if parsing fails or structure is unexpected.
    
    CHANGE: Made more tolerant to string payloads in various formats.
    Now handles:
    - Direct list structure at [3][6]
    - Prefixed JSON strings with ")]}'\n"
    - Plain JSON strings starting with [ or {
    - Fallback scanning for data blob when [6] doesn't work
    """
    if not json_str:
        return None
    try:
        initial_data = json.loads(json_str)

        # Check the initial heuristic path [3][6]
        if isinstance(initial_data, list) and len(initial_data) > 3 and isinstance(initial_data[3], list) and len(initial_data[3]) > 6:
             data_blob_or_str = initial_data[3][6]

             # Case 1: It's already the list we expect (older format?)
             if isinstance(data_blob_or_str, list):
                 print("PARSE: Found expected list structure directly at initial_data[3][6].")
                 return data_blob_or_str

             # Case 2: It's a string - handle various string formats
             elif isinstance(data_blob_or_str, str):
                 stripped_data = data_blob_or_str.strip()
                 
                 # Case 2a: Prefixed JSON string with ")]}'\n"
                 if data_blob_or_str.startswith(")]}'\n"):
                     print("PARSE: Found prefixed string (\\)]}'\n) at initial_data[3][6], attempting to parse inner JSON.")
                     try:
                         json_str_inner = data_blob_or_str.split(")]}'\n", 1)[1]
                         actual_data = json.loads(json_str_inner)

                         # Check if the parsed inner data is a list and has the expected sub-structure at index 6
                         if isinstance(actual_data, list) and len(actual_data) > 6:
                              potential_data_blob = safe_get(actual_data, 6)
                              if isinstance(potential_data_blob, list):
                                  print("PARSE: Returning data blob found at actual_data[6].")
                                  return potential_data_blob # This is the main data structure
                              else:
                                  print(f"PARSE: Data at actual_data[6] is not a list, but {type(potential_data_blob)}. Trying fallback scan.")
                                  # Fallback: scan for first nested list that looks like data blob
                                  return _scan_for_data_blob(actual_data)
                         else:
                             print(f"PARSE: Parsed inner JSON is not a list or too short (len <= 6), type: {type(actual_data)}. Trying fallback scan.")
                             return _scan_for_data_blob(actual_data) if isinstance(actual_data, list) else None

                     except json.JSONDecodeError as e_inner:
                         print(f"PARSE ERROR: Failed to decode prefixed JSON string: {e_inner}")
                         return None
                     except Exception as e_inner_general:
                         print(f"PARSE ERROR: Unexpected error processing prefixed JSON string: {e_inner_general}")
                         return None
                 
                 # Case 2b: Plain JSON string starting with [ or {
                 elif stripped_data.startswith('[') or stripped_data.startswith('{'):
                     print("PARSE: Found plain JSON string at initial_data[3][6], attempting direct parse.")
                     try:
                         parsed_data = json.loads(stripped_data)
                         
                         # If it's a list, try to find the data blob
                         if isinstance(parsed_data, list):
                             if len(parsed_data) > 6 and isinstance(parsed_data[6], list):
                                 print("PARSE: Found data blob at parsed_data[6].")
                                 return parsed_data[6]
                             else:
                                 print("PARSE: parsed_data[6] not valid, trying fallback scan.")
                                 return _scan_for_data_blob(parsed_data)
                         else:
                             print(f"PARSE: Plain JSON string parsed to {type(parsed_data)}, not a list. Cannot extract data blob.")
                             return None
                             
                     except json.JSONDecodeError as e_direct:
                         print(f"PARSE ERROR: Failed to decode plain JSON string: {e_direct}")
                         return None
                     except Exception as e_direct_general:
                         print(f"PARSE ERROR: Unexpected error processing plain JSON string: {e_direct_general}")
                         return None
                 
                 # Case 2c: String but not recognizable JSON format
                 else:
                     print(f"PARSE: String at [3][6] doesn't start with expected JSON markers. First 50 chars: {stripped_data[:50]}")
                     return None

             # Case 3: Data at [3][6] is neither a list nor a string
             else:
                 print(f"PARSE: Unexpected type at [3][6]: {type(data_blob_or_str)}.")
                 return None

        # Case 4: Initial path [3][6] itself wasn't valid
        else:
            print(f"PARSE: Initial JSON structure not as expected (list[3][6] path not valid). Type: {type(initial_data)}")
            return None

    except json.JSONDecodeError as e:
        print(f"PARSE ERROR: Failed to decode initial JSON: {e}")
        return None
    except Exception as e:
        print(f"PARSE ERROR: Unexpected error parsing JSON data: {e}")
        return None


def _scan_for_data_blob(data_list):
    """
    Fallback function to scan a list for the first nested list that looks like a data blob.
    The data blob is typically a large list containing place information.
    
    CHANGE: New helper function for tolerant parsing when expected index doesn't work.
    
    Args:
        data_list: A list to scan for data blob structure
        
    Returns:
        The first suitable data blob found, or None
    """
    if not isinstance(data_list, list):
        return None
    
    print("PARSE: Scanning for data blob in list structure...")
    
    # Look for large nested lists (data blobs are typically large, 10+ elements)
    for i, item in enumerate(data_list):
        if isinstance(item, list) and len(item) >= 10:
            # Additional heuristic: data blob usually contains nested structures
            nested_count = sum(1 for x in item if isinstance(x, (list, dict)))
            if nested_count >= 3:  # At least 3 nested structures
                print(f"PARSE: Found potential data blob at index {i} (length: {len(item)}, nested: {nested_count})")
                return item
    
    print("PARSE: No suitable data blob found in fallback scan.")
    return None


# --- Field Extraction Functions (Indices relative to the data_blob returned by parse_json_data) ---

def get_main_name(data):
    """Extracts the main name of the place."""
    # Index relative to the data_blob returned by parse_json_data
    # Confirmed via debug_inner_data.json: data_blob = actual_data[6], name = data_blob[11]
    return safe_get(data, 11)

def get_place_id(data):
    """Extracts the Google Place ID."""
    return safe_get(data, 10) # Updated index

def get_gps_coordinates(data):
    """Extracts latitude and longitude."""
    lat = safe_get(data, 9, 2)
    lon = safe_get(data, 9, 3)
    if lat is not None and lon is not None:
        return {"latitude": lat, "longitude": lon}
    return None

def get_complete_address(data):
    """Extracts structured address components and joins them."""
    address_parts = safe_get(data, 2) # Updated index
    if isinstance(address_parts, list):
        formatted = ", ".join(filter(None, address_parts))
        return formatted if formatted else None
    return None

def get_rating(data):
    """Extracts the average star rating."""
    return safe_get(data, 4, 7)

def get_reviews_count(data):
    """Extracts the total number of reviews."""
    return safe_get(data, 4, 8)

def get_website(data):
    """Extracts the primary website link."""
    # Index based on debug_inner_data.json structure relative to data_blob (actual_data[6])
    return safe_get(data, 7, 0)

def _find_phone_recursively(data_structure):
    """
    Recursively searches a nested list/dict structure for a list containing
    the phone icon URL followed by the phone number string.
    """
    if isinstance(data_structure, list):
        # Check if this list matches the pattern [icon_url, phone_string, ...]
        if len(data_structure) >= 2 and \
           isinstance(data_structure[0], str) and "call_googblue" in data_structure[0] and \
           isinstance(data_structure[1], str):
            # Found the pattern, assume data_structure[1] is the phone number
            phone_number_str = data_structure[1]
            standardized_number = re.sub(r'\D', '', phone_number_str)
            if standardized_number:
                # print(f"Debug: Found phone via recursive search: {standardized_number}")
                return standardized_number

        # If not the target list, recurse into list elements
        for item in data_structure:
            found_phone = _find_phone_recursively(item)
            if found_phone:
                return found_phone

    elif isinstance(data_structure, dict):
        # Recurse into dictionary values
        for key, value in data_structure.items():
            found_phone = _find_phone_recursively(value)
            if found_phone:
                return found_phone

    # Base case: not a list/dict or pattern not found in this branch
    return None

def get_phone_number(data_blob):
    """
    Extracts and standardizes the primary phone number by recursively searching
    the data_blob for the phone icon pattern.
    """
    # data_blob is the main list structure (e.g., actual_data[6])
    found_phone = _find_phone_recursively(data_blob)
    if found_phone:
        return found_phone
    else:
        # print("Debug: Phone number pattern not found in data_blob.")
        return None

def get_categories(data):
    """Extracts the list of categories/types."""
    return safe_get(data, 13)

def get_thumbnail(data):
    """Extracts the main thumbnail image URL."""
    # This path might still be relative to the old structure, needs verification
    # If data_blob is the list starting at actual_data[6], this index is likely wrong.
    # We need to find the thumbnail within the new structure from debug_inner_data.json
    # For now, returning None until verified.
    # return safe_get(data, 72, 0, 1, 6, 0) # Placeholder index - LIKELY WRONG
    # Tentative guess based on debug_inner_data structure (might be in a sublist like [14][0][0][6][0]?)
    return safe_get(data, 14, 0, 0, 6, 0) # Tentative guess

# Add more extraction functions here as needed, using the indices
# from omkarcloud/src/extract_data.py as a reference, BUT VERIFYING against debug_inner_data.json

def extract_place_data(html_content):
    """
    High-level function to orchestrate extraction from HTML content.
    """
    json_str = extract_initial_json(html_content)
    if not json_str:
        print("Failed to extract JSON string from HTML.")
        return None

    data_blob = parse_json_data(json_str)
    if not data_blob:
        print("Failed to parse JSON data or find expected structure.")
        return None

    # Now extract individual fields using the helper functions
    place_details = {
        "name": get_main_name(data_blob),
        "place_id": get_place_id(data_blob),
        "coordinates": get_gps_coordinates(data_blob),
        "address": get_complete_address(data_blob),
        "rating": get_rating(data_blob),
        "reviews_count": get_reviews_count(data_blob),
        "categories": get_categories(data_blob),
        "website": get_website(data_blob),
        "phone": get_phone_number(data_blob), # Needs index verification
        "thumbnail": get_thumbnail(data_blob), # Needs index verification
        # Add other fields as needed
    }

    # Filter out None values if desired
    place_details = {k: v for k, v in place_details.items() if v is not None}

    return place_details if place_details else None


# --- DOM-based Extraction (Fallback Strategy) ---

async def extract_place_data_dom(page, url):
    """
    Extracts place data directly from the rendered DOM using Playwright.
    This is a robust fallback strategy when JSON extraction fails.
    
    CHANGE: Production-ready DOM extraction optimized for lead generation.
    Uses multiple selector strategies and waits properly for page load.
    Returns None if critical fields (name) cannot be extracted.
    
    Args:
        page: Playwright page object (already navigated to place page)
        url: The URL being scraped (used for maps_url)
        
    Returns:
        dict: Place details with required fields (name, maps_url) and optional fields
              Returns None if name cannot be extracted
    """
    place_details = {}
    
    try:
        # STEP 1: Wait for place page to fully load
        print("DOM: Waiting for place page to load...")
        try:
            # Wait for the main heading to appear (primary indicator page is loaded)
            await page.wait_for_selector('h1', state='visible', timeout=10000)
            print("DOM: Page loaded (h1 found)")
        except Exception as e:
            # Fallback: try role-based selector
            try:
                await page.wait_for_selector('[role="heading"][aria-level="1"]', state='visible', timeout=5000)
                print("DOM: Page loaded (heading role found)")
            except Exception:
                print(f"DOM: Failed to detect page load: {e}")
                return None
        
        # Small pause for dynamic content
        await page.wait_for_load_state('networkidle', timeout=5000)
        
        # STEP 2: Extract NAME (REQUIRED)
        name = None
        try:
            # Strategy 1: Find h1
            h1_elements = await page.locator('h1').all()
            for h1 in h1_elements:
                text = await h1.inner_text()
                if text and text.strip() and len(text.strip()) > 2:
                    name = text.strip()
                    print(f"DOM: Extracted name: '{name}'")
                    break
            
            # Strategy 2: Fallback to role-based heading
            if not name:
                heading_elements = await page.locator('[role="heading"][aria-level="1"]').all()
                for heading in heading_elements:
                    text = await heading.inner_text()
                    if text and text.strip() and len(text.strip()) > 2:
                        name = text.strip()
                        print(f"DOM: Extracted name (fallback): '{name}'")
                        break
        except Exception as e:
            print(f"DOM: Error extracting name: {e}")
        
        # If no name found, this extraction failed
        if not name:
            print("DOM: CRITICAL - No name found, aborting extraction")
            return None
        
        place_details['name'] = name
        place_details['maps_url'] = url  # Store the normalized URL
        
        # STEP 3: Extract RATING and REVIEWS_COUNT
        try:
            # Look for rating patterns in the page
            # Google Maps typically shows: "4.5★ · 1,234 reviews"
            page_text = await page.content()
            
            # Find rating (float pattern near stars)
            rating_patterns = [
                r'(\d+\.\d+)\s*(?:stars?|★|⭐)',
                r'aria-label="([^"]*?)(\d+\.\d+)\s*(?:stars?|out)',
            ]
            
            for pattern in rating_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    try:
                        # Extract first numeric match
                        for match in matches:
                            rating_str = match if isinstance(match, str) else match[-1]
                            rating_str = re.search(r'\d+\.\d+', rating_str)
                            if rating_str:
                                rating = float(rating_str.group())
                                if 0 <= rating <= 5:
                                    place_details['rating'] = rating
                                    print(f"DOM: Extracted rating: {rating}")
                                    break
                        if 'rating' in place_details:
                            break
                    except (ValueError, AttributeError):
                        continue
            
            # Find reviews count (number followed by "reviews" or "review")
            reviews_patterns = [
                r'([\d,\.]+)\s*(?:reviews?|Bewertungen?)',
                r'aria-label="[^"]*?([\d,\.]+)\s*reviews?',
            ]
            
            for pattern in reviews_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    try:
                        for match in matches:
                            # Clean number (remove commas/dots used as thousands separators)
                            reviews_str = str(match).replace(',', '').replace('.', '')
                            # Keep only digits
                            reviews_str = re.sub(r'\D', '', reviews_str)
                            if reviews_str:
                                reviews_count = int(reviews_str)
                                if reviews_count > 0 and reviews_count < 10000000:  # Sanity check
                                    place_details['reviews_count'] = reviews_count
                                    print(f"DOM: Extracted reviews_count: {reviews_count}")
                                    break
                        if 'reviews_count' in place_details:
                            break
                    except (ValueError, AttributeError):
                        continue
        except Exception as e:
            print(f"DOM: Error extracting rating/reviews: {e}")
        
        # STEP 4: Extract ADDRESS
        try:
            # Strategy 1: Button with aria-label containing "Address"
            address_selectors = [
                'button[aria-label*="Address"]',
                'button[data-item-id*="address"]',
                '[data-item-id="address"]',
                'button[aria-label*="address" i]',
            ]
            
            for selector in address_selectors:
                elements = await page.locator(selector).all()
                for element in elements:
                    text = await element.inner_text()
                    if text and len(text.strip()) > 5:  # Address should be reasonably long
                        place_details['address'] = text.strip()
                        print(f"DOM: Extracted address: '{text.strip()[:50]}...'")
                        break
                if 'address' in place_details:
                    break
        except Exception as e:
            print(f"DOM: Error extracting address: {e}")
        
        # STEP 5: Extract WEBSITE
        try:
            # Strategy 1: Link with aria-label containing "Website"
            website_selectors = [
                'a[aria-label*="Website"]',
                'a[data-item-id*="authority"]',
                'a[data-tooltip*="Open website"]',
            ]
            
            for selector in website_selectors:
                elements = await page.locator(selector).all()
                for element in elements:
                    href = await element.get_attribute('href')
                    if href and 'http' in href and 'google.com' not in href and '/maps' not in href:
                        place_details['website'] = href.strip()
                        print(f"DOM: Extracted website: {href.strip()}")
                        break
                if 'website' in place_details:
                    break
            
            # Strategy 2: Fallback - find any external link in the info area
            if 'website' not in place_details:
                all_links = await page.locator('a[href^="http"]').all()
                for link in all_links[:30]:  # Check first 30 links
                    href = await link.get_attribute('href')
                    if href and 'http' in href and 'google.com' not in href and '/maps' not in href and 'gstatic.com' not in href:
                        # Additional check: link should be visible (not hidden)
                        is_visible = await link.is_visible()
                        if is_visible:
                            place_details['website'] = href.strip()
                            print(f"DOM: Extracted website (fallback): {href.strip()}")
                            break
        except Exception as e:
            print(f"DOM: Error extracting website: {e}")
        
        # STEP 6: Extract PHONE
        try:
            # Strategy 1: Button with aria-label containing "Phone"
            phone_selectors = [
                'button[aria-label*="Phone"]',
                'button[data-item-id*="phone"]',
                '[data-item-id="phone"]',
                'button[aria-label*="phone" i]',
            ]
            
            for selector in phone_selectors:
                elements = await page.locator(selector).all()
                for element in elements:
                    text = await element.inner_text()
                    if text:
                        # Normalize: keep only digits and +
                        phone_clean = re.sub(r'[^\d+]', '', text)
                        if phone_clean and len(phone_clean) >= 7:  # Minimum viable phone length
                            place_details['phone'] = phone_clean
                            print(f"DOM: Extracted phone: {phone_clean}")
                            break
                if 'phone' in place_details:
                    break
        except Exception as e:
            print(f"DOM: Error extracting phone: {e}")
        
        # Summary
        extracted_fields = list(place_details.keys())
        print(f"DOM: Extraction complete - {len(extracted_fields)} fields: {extracted_fields}")
        
        return place_details
        
    except Exception as e:
        print(f"DOM: Critical error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return None


# Example usage (for testing):
if __name__ == '__main__':
    # Load sample HTML content from a file (replace 'sample_place.html' with your file)
    try:
        with open('sample_place.html', 'r', encoding='utf-8') as f:
            sample_html = f.read()

        extracted_info = extract_place_data(sample_html)

        if extracted_info:
            print("Extracted Place Data:")
            print(json.dumps(extracted_info, indent=2))
        else:
            print("Could not extract data from the sample HTML.")

    except FileNotFoundError:
        print("Sample HTML file 'sample_place.html' not found. Cannot run example.")
    except Exception as e:
        print(f"An error occurred during example execution: {e}")