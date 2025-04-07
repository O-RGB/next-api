from flask import Flask, jsonify, request
import requests
import pytrie
import time

app = Flask(__name__)
json_data = {}
trie_search = None
data_loaded = False

def load_json_from_catbox():
    url = "https://files.catbox.moe/cmdl3r.json"
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to load data: HTTP status {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def prepare_trie_search(data):
    trie = pytrie.StringTrie()
    for item in data:
        if "name" in item:
            # Store the name in lowercase for case-insensitive search
            trie[item["name"].lower()] = item
    return trie

def load_data():
    print("Loading data...")
    global json_data, trie_search, data_loaded
    
    # Try up to 3 times with exponential backoff
    for attempt in range(3):
        json_data = load_json_from_catbox()
        if json_data:
            trie_search = prepare_trie_search(json_data)
            print(f"Successfully loaded {len(json_data)} items")
            data_loaded = True
            return
        else:
            wait_time = 2 ** attempt
            print(f"Attempt {attempt+1} failed. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    # If all attempts fail, initialize with empty data
    print("All attempts to load data failed. Starting with empty dataset.")
    json_data = []
    trie_search = pytrie.StringTrie()
    data_loaded = False

# Initialize at import time
try:
    load_data()
except Exception as e:
    print(f"Error during initialization: {e}")
    json_data = []
    trie_search = pytrie.StringTrie()

@app.route('/search', methods=['GET'])
def search_data():
    query = request.args.get('query', '').lower()
    
    # Ensure data is loaded
    global trie_search, data_loaded
    if not data_loaded:
        try:
            load_data()
        except Exception as e:
            return jsonify({"message": f"Failed to load data: {str(e)}"}), 500
    
    # Check if there's an exact match
    if query in trie_search:
        result = trie_search[query]
        return jsonify(result)
    
    # If no exact match, try prefix search
    try:
        # Get items with names that start with the query
        prefix_matches = trie_search.items(prefix=query)
        if prefix_matches:
            # Limit to first 10 matches
            results = [item[1] for item in prefix_matches[:10]]
            return jsonify(results)
    except Exception as e:
        print(f"Error during prefix search: {e}")
    
    # If still no matches, fallback to manual search for partial matches
    if json_data:
        partial_matches = []
        for item in json_data:
            if "name" in item and query in item["name"].lower():
                partial_matches.append(item)
                if len(partial_matches) >= 10:  # Limit to 10 results
                    break
        
        if partial_matches:
            return jsonify(partial_matches)
    
    # No matches found
    return jsonify({"message": "No results found for query"}), 404

@app.route('/list-items', methods=['GET'])
def list_items():
    """Endpoint to list sample items for testing"""
    limit = int(request.args.get('limit', 10))
    
    if not json_data:
        return jsonify({"message": "No data loaded"}), 404
    
    sample_items = []
    for item in json_data[:limit]:
        if "name" in item:
            sample_items.append({"name": item["name"]})
    
    return jsonify({
        "total_items": len(json_data),
        "samples": sample_items
    })

@app.route('/reload', methods=['POST'])
def reload_data():
    """Endpoint to manually reload data"""
    try:
        load_data()
        return jsonify({"message": f"Data reloaded successfully. {len(json_data)} items loaded."}), 200
    except Exception as e:
        return jsonify({"message": f"Failed to reload data: {str(e)}"}), 500

@app.route('/status', methods=['GET'])
def status():
    """Endpoint to check the status of loaded data"""
    return jsonify({
        "data_loaded": data_loaded,
        "item_count": len(json_data) if json_data else 0,
        "trie_initialized": trie_search is not None
    }), 200

if __name__ == "__main__":
    app.run(debug=True)