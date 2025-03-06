import base64
from flask import Flask, request, jsonify
import logging
import sys
from flask_cors import CORS  # Import CORS
import os
import requests
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
app = Flask(__name__)
CORS(app, origins=["https://9000-idx-find-the-bird-1740898861496.cluster-3g4scxt2njdd6uovkqyfcabgo6.cloudworkstations.dev"])
# Configure Google Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')



def encode_image(image_file):
    """Encodes an image to base64."""
    return base64.b64encode(image_file).decode("utf-8")



@app.route('/test',methods=['GET'])
def test():
    return "Hello World"

@app.route('/identify-bird', methods=['POST'])
def identify_bird():
    # Check if image is in the request
    if 'image' not in request.files:
      print('no image')
      return jsonify({'error': 'No image provided', 'message': 'Please select an image of a bird to identify.'}), 400
        
    
    image_file = request.files['image']
    try:
        # Process image with Gemini API
        image_data = image_file.read()
        encoded_image = encode_image(image_data)
        multi_response = multiple_responses(encoded_image)
        species_list = []
        for model, result in multi_response.items():
            print(result)
            if result and 'species' in result:
               species_list.append(result['species'])

        print(multi_response)
        print('image_encoded')
        # Create prompt for Gemini

        prompt = """
             
             Identify the bird species in this image using the this other models responses below and classify with max voting.
             responses :{species_list}
             Provide the following information in your response:
             1. The bird species name
             2. A detailed markdown description of the bird attractive markdown only
             3. A list of variation species or related species

             Format your response as a JSON object with the following keys:
             {
                 "species": "bird species name",
                 "description": "markdown description",
                 "variation_species": ["species1", "species2", "species3", "species3", "species5"]
             }
             """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": encoded_image
                            }
                        }
                    ]
                }
            ]
        }
        # Generate response from Gemini
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(response.json()['candidates'][0]['content']['parts'][0]['text'])
        else:
            print(f"Error: {response.status_code}, {response.text}")
        
        # Parse the response to extract JSON
        response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        # Extract JSON content from response if needed
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_content = response_text[json_start:json_end]
        else:
            # Fallback if JSON format not detected
            return jsonify({'error': 'Failed to parse Gemini response'}), 500
        print(json_content)
        bird_data = json.loads(json_content)
        
        # Fetch images for identified species
        species_images = []
        species_images = get_image_urls(title=bird_data['species'], limit=6)
        print(species_images)
        # if len(species_images) == 0:
        #     species_images = fetch_species_images(bird_data['species'])
        
        # Fetch images for variation species
        variation_images = {}
        for variation in bird_data['variation_species']:
            variation_images[variation] = get_image_urls(variation,1)
        
        # Prepare final response
        result = {
            'responses': multi_response,
            'species': bird_data['species'],
            'description': bird_data['description'],
            'variation_species': bird_data['variation_species'],
            'species_images': species_images,
            'variation_images': variation_images
        }   
        print(result)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def fetch_species_images(species_name, max_images=6):
    """
    Search the web for images of the specified bird species
    Returns a list of image URLs
    """
    try:
        search_term = f"{species_name} bird"
        search_url = f"https://www.bing.com/images/search?q={search_term}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract image URLs from the search results
        # This pattern will need to be adjusted based on the actual structure of the search results
        image_elements = soup.select('.iusc')
        image_urls = []
        
        for element in image_elements[:max_images]:
            if 'data-src' in element.attrs:
                image_urls.append(element['data-src'])
            elif 'm' in element.attrs:
                # Parse JSON data if available
                try:
                    data = json.loads(element['m'])
                    if 'murl' in data:
                        image_urls.append(data['murl'])
                except:
                    pass
                    
        # Return at least a few images or empty list if none found
        return image_urls
    
    except Exception as e:
        print(f"Error fetching images for {species_name}: {str(e)}")
        return []

def fetch_single_image(species_name):
    """
    Search the web for a single image of the specified bird species
    Returns an image URL
    """
    images = fetch_species_images(species_name, max_images=1)
    return images[0] if images else ""

# def get_image_urls(title, limit=5):
#     """
#     Get multiple image URLs for a Wikipedia article by title using a more reliable method.
#     """
#     # Base URL for the Wikipedia API
#     api_url = "https://en.wikipedia.org/w/api.php"
    
#     # First, we need to get the pageId for the article
#     params = {
#         "action": "query",
#         "format": "json",
#         "titles": title,
#     }
    
#     try:
#         # Get page ID
#         response = requests.get(api_url, params=params, timeout=10)
#         data = response.json()
#         print(data)
        
#         # Extract page ID
#         pages = data.get("query", {}).get("pages", {})
#         if not pages:
#             logger.warning("No pages found in API response")
#             return []
            
#         page_id = list(pages.keys())[0]
        
#         if page_id == "-1":
#             logger.warning(f"Page '{title}' not found")
#             return []
            
#         # Now use the more reliable approach: get all images directly from the page content
#         params = {
#             "action": "parse",
#             "format": "json",
#             "pageid": page_id,
#             "prop": "images"  # Get all images from the page
#         }
        
#         response = requests.get(api_url, params=params, timeout=10)
#         data = response.json()
#         print(data)
        
#         if "parse" not in data or "images" not in data["parse"]:
#             logger.warning("No image data found in parse API response")
#             return []
            
#         # Get image file names
#         images = data["parse"]["images"]
#         logger.info(f"Found {len(images)} images for page '{title}'")
        
#         # Filter out non-content images (commons icons, etc.)
#         filtered_images = [img for img in images if not img.lower().startswith(('icon-', 'commons-', 'edit-'))]
        
#         # Apply limit
#         filtered_images = filtered_images[:limit]
        
#         image_urls = []
#         for img_name in filtered_images:
#             # Now get the URL for each image
#             img_params = {
#                 "action": "query",
#                 "format": "json",
#                 "titles": f"File:{img_name}",  # Wikipedia image files are prefixed with "File:"
#                 "prop": "imageinfo",
#                 "iiprop": "url"
#             }
            
#             img_response = requests.get(api_url, params=img_params, timeout=10)
#             img_data = img_response.json()
            
#             img_pages = img_data.get("query", {}).get("pages", {})
#             if not img_pages:
#                 continue
                
#             img_page_id = list(img_pages.keys())[0]
            
#             if "imageinfo" in img_pages[img_page_id]:
#                 image_url = img_pages[img_page_id]["imageinfo"][0]["url"]
#                 image_urls.append(image_url)
#                 logger.info(f"Found image URL: {image_url}")
        
#         logger.info(f"Successfully retrieved {len(image_urls)} image URLs")
#         return image_urls
        
#     except Exception as e:
#         logger.error(f"Error in get_image_urls: {str(e)}")
#         raise Exception(f"Error processing Wikipedia data: {str(e)}")

def get_image_urls(title, limit=5):
    """
    Get multiple image URLs for a Wikipedia article by title using multiple methods.
    Falls back to more generic searches for birds when direct page images aren't available.
    """
    # Base URL for the Wikipedia API
    api_url = "https://en.wikipedia.org/w/api.php"
    
    image_urls = []
    
    try:
        # Method 1: Try using parse API first
        logger.info(f"Attempting to get images for '{title}' using parse API")
        
        # First, we need to get the pageId for the article
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        data = response.json()
        
        # Extract page ID
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            logger.warning("No pages found in API response")
        else:
            page_id = list(pages.keys())[0]
            
            if page_id != "-1":
                # Get images with parse API
                params = {
                    "action": "parse",
                    "format": "json",
                    "pageid": page_id,
                    "prop": "images"
                }
                
                response = requests.get(api_url, params=params, timeout=10)
                data = response.json()
                
                if "parse" in data and "images" in data["parse"] and data["parse"]["images"]:
                    # Get image file names
                    images = data["parse"]["images"]
                    logger.info(f"Found {len(images)} images with parse API")
                    
                    # Filter out non-content images (commons icons, etc.)
                    filtered_images = [img for img in images if not img.lower().startswith(('icon-', 'commons-', 'edit-'))]
                    
                    # Apply limit
                    filtered_images = filtered_images[:limit]
                    
                    # Get URLs for images
                    for img_name in filtered_images:
                        img_params = {
                            "action": "query",
                            "format": "json",
                            "titles": f"File:{img_name}",
                            "prop": "imageinfo",
                            "iiprop": "url"
                        }
                        
                        img_response = requests.get(api_url, params=img_params, timeout=10)
                        img_data = img_response.json()
                        
                        img_pages = img_data.get("query", {}).get("pages", {})
                        if img_pages:
                            img_page_id = list(img_pages.keys())[0]
                            
                            if "imageinfo" in img_pages[img_page_id]:
                                image_url = img_pages[img_page_id]["imageinfo"][0]["url"]
                                image_urls.append(image_url)
                else:
                    logger.warning(f"No images found with parse API for '{title}'")
        
        # Method 2: If no images found, try with fileusage query
        if not image_urls:
            logger.info(f"Trying fileusage query for '{title}'")
            
            # Search for files that are used on pages with this title
            search_title = title.replace(" ", "_")
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": f"File:{search_title}",
                "srnamespace": "6",  # File namespace
                "srlimit": limit
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            data = response.json()
            
            if "query" in data and "search" in data["query"]:
                search_results = data["query"]["search"]
                logger.info(f"Found {len(search_results)} files with title search")
                
                for result in search_results[:limit]:
                    file_title = result["title"]
                    
                    img_params = {
                        "action": "query",
                        "format": "json",
                        "titles": file_title,
                        "prop": "imageinfo",
                        "iiprop": "url"
                    }
                    
                    img_response = requests.get(api_url, params=img_params, timeout=10)
                    img_data = img_response.json()
                    
                    img_pages = img_data.get("query", {}).get("pages", {})
                    if img_pages:
                        img_page_id = list(img_pages.keys())[0]
                        
                        if "imageinfo" in img_pages[img_page_id]:
                            image_url = img_pages[img_page_id]["imageinfo"][0]["url"]
                            image_urls.append(image_url)
        
        # Method 3: If still no images, try searching more generically
        if not image_urls:
            logger.info(f"Trying commons category search for '{title}'")
            
            # Try searching commons for this bird species
            commons_search = f"{title} bird"
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": commons_search,
                "srnamespace": "6",  # File namespace
                "srlimit": limit
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            data = response.json()
            
            if "query" in data and "search" in data["query"]:
                search_results = data["query"]["search"]
                logger.info(f"Found {len(search_results)} files with generic search")
                
                for result in search_results[:limit]:
                    file_title = result["title"]
                    
                    img_params = {
                        "action": "query",
                        "format": "json",
                        "titles": file_title,
                        "prop": "imageinfo",
                        "iiprop": "url"
                    }
                    
                    img_response = requests.get(api_url, params=img_params, timeout=10)
                    img_data = img_response.json()
                    
                    img_pages = img_data.get("query", {}).get("pages", {})
                    if img_pages:
                        img_page_id = list(img_pages.keys())[0]
                        
                        if "imageinfo" in img_pages[img_page_id]:
                            image_url = img_pages[img_page_id]["imageinfo"][0]["url"]
                            image_urls.append(image_url)
        
        # Method 4: If all else fails, try with the generic "bird" category
        if not image_urls:
            logger.info(f"Falling back to Wikimedia Commons search for '{title}'")
            
            # Search directly in commons
            commons_api_url = "https://commons.wikimedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": f"\"{title}\" bird",
                "srnamespace": "6",  # File namespace
                "srlimit": limit
            }
            
            response = requests.get(commons_api_url, params=params, timeout=10)
            data = response.json()
            
            if "query" in data and "search" in data["query"]:
                search_results = data["query"]["search"]
                logger.info(f"Found {len(search_results)} files in Commons")
                
                for result in search_results[:limit]:
                    file_title = result["title"]
                    
                    img_params = {
                        "action": "query",
                        "format": "json",
                        "titles": file_title,
                        "prop": "imageinfo",
                        "iiprop": "url"
                    }
                    
                    img_response = requests.get(commons_api_url, params=img_params, timeout=10)
                    img_data = img_response.json()
                    
                    img_pages = img_data.get("query", {}).get("pages", {})
                    if img_pages:
                        img_page_id = list(img_pages.keys())[0]
                        
                        if "imageinfo" in img_pages[img_page_id]:
                            image_url = img_pages[img_page_id]["imageinfo"][0]["url"]
                            image_urls.append(image_url)
        
        # Final fallback - if we still don't have images and you have your fetch_species_images function
        if not image_urls and 'fetch_species_images' in globals():
            logger.info(f"Final fallback to web search for '{title}'")
            return fetch_species_images(f"{title} bird", max_images=limit)
        
        logger.info(f"Successfully retrieved {len(image_urls)} image URLs")
        return image_urls
        
    except Exception as e:
        logger.error(f"Error in get_image_urls: {str(e)}")
        # If we encounter an error but have your fetch_species_images function, use it as fallback
        if 'fetch_species_images' in globals():
            logger.info(f"Error encountered, falling back to web search for '{title}'")
            return fetch_species_images(f"{title} bird", max_images=limit)
        raise Exception(f"Error processing Wikipedia data: {str(e)}")

        
def multiple_responses(image_data):
    responses = {}


    try:
        responses['gemini'] = gemini_res(image_data)
    except Exception as e:
        print(f"Error in gemini_res: {str(e)}")

    try:
        responses['mistral'] = mistral_res(image_data)
    except Exception as e:
        print(f"Error in mistral_res: {str(e)}")

    try:
        responses['llama'] = llama_res(image_data)
    except Exception as e:
        print(f"Error in llama_res: {str(e)}")


    print('multi',responses)

    return responses if responses else None


def gemini_res(image_data):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }

    prompt = """ Classify what kind of bird 

    Use this JSON schema:

    {'species': str,'reason':give reason for why you have classified this bird species } only json no headings
    """

    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_data
                        }
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=data, headers=headers)
    except Exception as e:
        print(f"Error in gemini_res: {str(e)}")
    
    # if response.status_code == 200:
    #     print(response.json()['candidates'][0]['content']['parts'][0]['text'])
    # else:
    #     print(f"Error: {response.status_code}, {response.text}")
    #     return

    response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
    # Extract JSON content from response if needed
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1
    if json_start >= 0 and json_end > json_start:
        json_content = response_text[json_start:json_end]
    else:
        # Fallback if JSON format not detected
        return 
    json_content = json_content.replace("'", '"')  
    bird_data = json.loads(json_content)
    print("gemini:",bird_data)
    return bird_data

def mistral_res(image_data):
    MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }

    prompt = """ Classify what kind of bird is in the Image
    Use this JSON schema:

    {'species': str, 'reason':give reason for why you have classified this bird species}
    """

    data = {
        "model": "pixtral-12b-2409",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{image_data}"
                }
                ]
            }
        ],
        "max_tokens": 300
    }
    try:
        response = requests.post(url, json=data, headers=headers)
    except Exception as e:
        print(f"Error in mistral_res: {str(e)}")

    # if response.status_code == 200:
    #     print(response.json()['choices'][0]['message']['content'])
    # else:
        # print(f"Error: {response.status_code}, {response.text}")

    response_text = response.json()['choices'][0]['message']['content']
    # Extract JSON content from response if needed
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1
    if json_start >= 0 and json_end > json_start:
        json_content = response_text[json_start:json_end]
    else:
        # Fallback if JSON format not detected
        return 
    json_content = json_content.replace("'", '"')  
    bird_data = json.loads(json_content)
    print("mistral:",bird_data)
    return bird_data

def llama_res(image_data):
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")  # Ensure your API key is set in environment variables

    url = "https://api.together.xyz/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = """ Classify what kind of bird 

    Use this JSON schema:

    {'species': str,'reason':give reason for why you have classified this bird species}
    """

    data = {
        "model": "meta-llama/Llama-Vision-Free",
        "messages": [
            {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                        },
                    },
                ],}
        ]
    }

    try:
        response = requests.post(url, json=data, headers=headers)
    except Exception as e:
        print(f"Error in llama_res: {str(e)}")

    # if response.status_code == 200:
    #     print(response.json()["choices"][0]["message"]["content"])
    # else:
    #     print(f"Error: {response.status_code}, {response.text}")

    response_text = response.json()["choices"][0]["message"]["content"]
    print(response_text)
    # Extract JSON content from response if needed
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1
    if json_start >= 0 and json_end > json_start:
        json_content = response_text[json_start:json_end]
    else:
        # Fallback if JSON format not detected
        return 
    json_content = json_content.replace("'", '"')  
    
    bird_data = json.loads(json_content)
    print("llama:",bird_data)
    return bird_data



if __name__ == '__main__':
    app.run(debug=True)