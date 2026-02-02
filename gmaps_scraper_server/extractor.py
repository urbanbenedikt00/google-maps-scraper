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

async def extract_place_data_dom(page):
    """
    Extracts place data directly from the rendered DOM using Playwright.
    This is a fallback strategy when JSON extraction fails.
    
    CHANGE: New function to provide robust DOM-based extraction.
    Uses Playwright locators to extract data from visible elements.
    
    Args:
        page: Playwright page object (already navigated to place page)
        
    Returns:
        dict: Place details with keys: name, address, website, phone, rating, reviews_count
              Missing fields are omitted (no None values included)
    """
    place_details = {}
    
    try:
        # Extract name from h1
        try:
            name_element = page.locator('h1').first
            if await name_element.count() > 0:
                name = await name_element.inner_text()
                if name and name.strip():
                    place_details['name'] = name.strip()
                    print(f"DOM: Extracted name: {name.strip()}")
        except Exception as e:
            print(f"DOM: Failed to extract name: {e}")
        
        # Extract address
        try:
            # Try button with data-item-id="address"
            address_element = page.locator('button[data-item-id="address"]').first
            if await address_element.count() == 0:
                # Fallback to div
                address_element = page.locator('div[data-item-id="address"]').first
            
            if await address_element.count() > 0:
                address = await address_element.inner_text()
                if address and address.strip():
                    place_details['address'] = address.strip()
                    print(f"DOM: Extracted address: {address.strip()}")
        except Exception as e:
            print(f"DOM: Failed to extract address: {e}")
        
        # Extract website
        try:
            # Try a[data-item-id="authority"]
            website_element = page.locator('a[data-item-id="authority"]').first
            if await website_element.count() > 0:
                website = await website_element.get_attribute('href')
                if website and website.strip():
                    place_details['website'] = website.strip()
                    print(f"DOM: Extracted website: {website.strip()}")
            else:
                # Fallback: search for any <a> that looks like a website in visible area
                # Look for links that don't contain google.com or maps
                all_links = await page.locator('a[href^="http"]').all()
                for link in all_links[:20]:  # Check first 20 links only
                    href = await link.get_attribute('href')
                    if href and 'google.com' not in href and 'maps' not in href:
                        place_details['website'] = href.strip()
                        print(f"DOM: Extracted website (fallback): {href.strip()}")
                        break
        except Exception as e:
            print(f"DOM: Failed to extract website: {e}")
        
        # Extract phone
        try:
            phone_element = page.locator('button[data-item-id="phone"]').first
            if await phone_element.count() > 0:
                phone_text = await phone_element.inner_text()
                if phone_text and phone_text.strip():
                    # Clean phone number (remove non-digits for standardization)
                    phone_clean = re.sub(r'\D', '', phone_text)
                    if phone_clean:
                        place_details['phone'] = phone_clean
                        print(f"DOM: Extracted phone: {phone_clean}")
        except Exception as e:
            print(f"DOM: Failed to extract phone: {e}")
        
        # Extract rating and reviews_count from aria-label
        try:
            # Look for elements with aria-label containing "stars" or "star"
            rating_elements = await page.locator('[aria-label*="star"]').all()
            for element in rating_elements:
                aria_label = await element.get_attribute('aria-label')
                if aria_label and 'star' in aria_label.lower():
                    # Try to parse rating (e.g., "4.5 stars", "4,5 Sterne")
                    rating_match = re.search(r'(\d+[.,]\d+|\d+)', aria_label)
                    if rating_match:
                        rating_str = rating_match.group(1).replace(',', '.')
                        try:
                            rating = float(rating_str)
                            place_details['rating'] = rating
                            print(f"DOM: Extracted rating: {rating}")
                            break
                        except ValueError:
                            pass
        except Exception as e:
            print(f"DOM: Failed to extract rating: {e}")
        
        try:
            # Look for elements with aria-label containing "review"
            review_elements = await page.locator('[aria-label*="review"]').all()
            for element in review_elements:
                aria_label = await element.get_attribute('aria-label')
                if aria_label and 'review' in aria_label.lower():
                    # Try to parse review count (e.g., "1,234 reviews", "1.234 Bewertungen")
                    # Remove commas and dots used as thousands separators
                    review_match = re.search(r'([\d.,]+)\s*review', aria_label, re.IGNORECASE)
                    if review_match:
                        reviews_str = review_match.group(1).replace(',', '').replace('.', '')
                        try:
                            reviews_count = int(reviews_str)
                            place_details['reviews_count'] = reviews_count
                            print(f"DOM: Extracted reviews_count: {reviews_count}")
                            break
                        except ValueError:
                            pass
        except Exception as e:
            print(f"DOM: Failed to extract reviews_count: {e}")
        
        # Log what was extracted
        if place_details:
            print(f"DOM: Successfully extracted {len(place_details)} fields")
        else:
            print("DOM: No fields could be extracted")
        
        return place_details if place_details else None
        
    except Exception as e:
        print(f"DOM: Unexpected error during extraction: {e}")
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