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


# --- DOM-based Extraction (PRIMARY Strategy) ---

async def extract_place_data_dom(page, lang="en"):
    """
    Extracts place data directly from the rendered DOM using Playwright.
    This is the PRIMARY extraction method for Google Maps place pages.
    
    CHANGE: Complete rewrite using textContent and modern best practices.
    - Uses textContent (not inner_text) to handle hidden elements
    - Waits for h1 text to be populated with wait_for_function
    - Uses stable data-item-id and aria-label selectors
    - Returns empty dict if name cannot be extracted
    
    Args:
        page: Playwright page object (already navigated to place page)
        lang: Language code for localized selectors
        
    Returns:
        dict: Place details with at least name field, or empty dict if extraction fails
    """
    place_details = {}
    
    try:
        # STEP 1: Wait for h1 to be attached
        try:
            await page.wait_for_selector('h1', state='attached', timeout=15000)
        except Exception:
            # Try role-based heading as fallback
            try:
                await page.wait_for_selector('[role="heading"][aria-level="1"]', state='attached', timeout=10000)
            except Exception as e:
                print(f"DOM: No heading element attached: {e}")
                return {}
        
        # STEP 2: Wait for h1 to have non-empty text content
        try:
            await page.wait_for_function(
                "() => { const h1 = document.querySelector('h1'); return h1 && h1.textContent && h1.textContent.trim().length > 0; }",
                timeout=15000
            )
        except Exception:
            # Try role-based heading
            try:
                await page.wait_for_function(
                    "() => { const h = document.querySelector('[role=\"heading\"][aria-level=\"1\"]'); return h && h.textContent && h.textContent.trim().length > 0; }",
                    timeout=10000
                )
            except Exception as e:
                print(f"DOM: Heading text did not populate: {e}")
                return {}
        
        # STEP 3: Extract NAME (REQUIRED) using textContent
        name = None
        try:
            # Strategy 1: h1 textContent
            name = await page.evaluate("() => document.querySelector('h1')?.textContent?.trim()")
            
            # Strategy 2: h1 span textContent (sometimes name is in nested span)
            if not name or len(name) < 2:
                name = await page.evaluate("() => document.querySelector('h1 span')?.textContent?.trim()")
            
            # Strategy 3: role-based heading
            if not name or len(name) < 2:
                name = await page.evaluate("() => document.querySelector('[role=\"heading\"][aria-level=\"1\"]')?.textContent?.trim()")
            
            if name and len(name) > 2:
                place_details['name'] = name
                print(f"DOM: ✓ Name: {name}")
            else:
                print(f"DOM: DIAGNOSTIC - h1 found but textContent empty or too short: '{name}'")
                return {}
        except Exception as e:
            print(f"DOM: Error extracting name: {e}")
            return {}
            if name and len(name) > 2:
                place_details['name'] = name
                print(f"DOM: ✓ Name: {name}")
            else:
                print(f"DOM: DIAGNOSTIC - h1 found but textContent empty or too short: '{name}'")
                return {}
        except Exception as e:
            print(f"DOM: Error extracting name: {e}")
            return {}
        
        # STEP 4: Extract ADDRESS
        try:
            address = None
            # Strategy 1: data-item-id="address"
            address = await page.evaluate("() => document.querySelector('button[data-item-id=\"address\"]')?.textContent?.trim()")
            if not address:
                address = await page.evaluate("() => document.querySelector('div[data-item-id=\"address\"]')?.textContent?.trim()")
            
            # Strategy 2: aria-label contains "Address"
            if not address:
                selectors = ['button[aria-label*="Address"]', 'button[aria-label*="Adresse"]']
                for selector in selectors:
                    try:
                        address = await page.evaluate(f"() => document.querySelector('{selector}')?.textContent?.trim()")
                        if address and len(address) > 5:
                            break
                    except Exception:
                        pass
            
            if address and len(address) > 5:
                place_details['address'] = address
                print(f"DOM: ✓ Address")
        except Exception as e:
            print(f"DOM: Address extraction failed: {e}")
        
        # STEP 5: Extract WEBSITE
        try:
            website = None
            # Strategy 1: data-item-id="authority"
            website = await page.evaluate("() => document.querySelector('a[data-item-id=\"authority\"]')?.href")
            
            # Strategy 2: aria-label contains "Website"
            if not website:
                selectors = ['a[aria-label*="Website"]', 'a[aria-label*="website"]']
                for selector in selectors:
                    try:
                        website = await page.evaluate(f"() => document.querySelector('{selector}')?.href")
                        if website and 'http' in website and 'google.com' not in website:
                            break
                    except Exception:
                        pass
            
            # Strategy 3: Find first external link that's not google/maps
            if not website:
                website = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href^="http"]'));
                        for (const link of links) {
                            const href = link.href;
                            if (href && !href.includes('google.com') && !href.includes('/maps') && !href.includes('gstatic.com')) {
                                return href;
                            }
                        }
                        return null;
                    }
                """)
            
            if website and 'http' in website:
                place_details['website'] = website
                print(f"DOM: ✓ Website")
        except Exception as e:
            print(f"DOM: Website extraction failed: {e}")
        
        # STEP 6: Extract PHONE
        try:
            phone = None
            # Strategy 1: data-item-id="phone"
            phone = await page.evaluate("() => document.querySelector('button[data-item-id=\"phone\"]')?.textContent?.trim()")
            
            # Strategy 2: aria-label contains "Phone"
            if not phone:
                selectors = ['button[aria-label*="Phone"]', 'button[aria-label*="Telefon"]']
                for selector in selectors:
                    try:
                        phone = await page.evaluate(f"() => document.querySelector('{selector}')?.textContent?.trim()")
                        if phone:
                            break
                    except Exception:
                        pass
            
            if phone:
                # Normalize: keep only digits and +
                phone_clean = re.sub(r'[^\d+]', '', phone)
                if phone_clean and len(phone_clean) >= 7:
                    place_details['phone'] = phone_clean
                    print(f"DOM: ✓ Phone")
        except Exception as e:
            print(f"DOM: Phone extraction failed: {e}")
        
        # STEP 7: Extract RATING
        try:
            rating = await page.evaluate("""
                () => {
                    // Find elements with aria-label containing rating info
                    const elements = Array.from(document.querySelectorAll('[aria-label]'));
                    for (const el of elements) {
                        const label = el.getAttribute('aria-label') || '';
                        const match = label.match(/(\\d+[.,]\\d+)\\s*(?:stars?|Sterne)/i);
                        if (match) {
                            const rating = parseFloat(match[1].replace(',', '.'));
                            if (rating >= 0 && rating <= 5) {
                                return rating;
                            }
                        }
                    }
                    return null;
                }
            """)
            if rating is not None:
                place_details['rating'] = rating
                print(f"DOM: ✓ Rating: {rating}")
        except Exception as e:
            print(f"DOM: Rating extraction failed: {e}")
        
        # STEP 8: Extract REVIEWS_COUNT
        try:
            reviews_count = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('[aria-label]'));
                    for (const el of elements) {
                        const label = el.getAttribute('aria-label') || '';
                        const match = label.match(/([\\d.,]+)\\s*(?:reviews?|Bewertungen?)/i);
                        if (match) {
                            const count = parseInt(match[1].replace(/[.,]/g, ''));
                            if (count > 0 && count < 10000000) {
                                return count;
                            }
                        }
                    }
                    return null;
                }
            """)
            if reviews_count is not None:
                place_details['reviews_count'] = reviews_count
                print(f"DOM: ✓ Reviews: {reviews_count}")
        except Exception as e:
            print(f"DOM: Reviews extraction failed: {e}")
        
        print(f"DOM: Extracted {len(place_details)} fields")
        return place_details
        
    except Exception as e:
        print(f"DOM: Critical error: {e}")
        import traceback
        traceback.print_exc()
        return {}


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