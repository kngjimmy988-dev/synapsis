import urllib.request
import urllib.parse
import json

def download_background(place_name):
    print(f"Searching for photos of: {place_name}...")
    
    # 1. Ask Wikimedia for an image
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"File: {place_name}",
        "gsrlimit": "1", # Just get the top result
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": "1080", # Download it at HD size
        "format": "json"
    }
    
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    req = urllib.request.Request(full_url, headers={'User-Agent': 'MyGreenScreenApp/1.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
            # 2. Find the image link
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                print("No images found for that place. Try another search.")
                return False
                
            page_id = list(pages.keys())[0]
            image_url = pages[page_id]["imageinfo"][0]["thumburl"]
            
            print(f"Found image! Downloading...")
            
            # 3. Download and save it
            img_req = urllib.request.Request(image_url, headers={'User-Agent': 'MyGreenScreenApp/1.0'})
            with urllib.request.urlopen(img_req) as img_response:
                with open("background.jpg", "wb") as f:
                    f.write(img_response.read())
            
            print("Success! Saved as background.jpg")
            return True
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    # Let's test it with the Eiffel Tower
    download_background("sunny buach")
