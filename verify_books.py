import asyncio
import httpx


BASE_URL = "http://localhost:8000"

async def verify_books():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. List books to get a sample
        print("Fetching books list...")
        response = await client.get("/api/books?limit=5")
        if response.status_code != 200:
            print(f"FAIL: Failed to fetch books. Status: {response.status_code}")
            return
        
        data = response.json()
        items = data.get("items", [])
        if not items:
            print("FAIL: No books found. Did seeding work?")
            return

        sample_book = items[0]
        title = sample_book["title"]
        # Take first word of title for partial search
        search_term = title.split()[0]
        
        print(f"Found book: '{title}'. Searching for: '{search_term}'...")

        book_title = sample_book["title"] # Renamed 'title' to 'book_title' for clarity with new search_term
        
        # Test "contains" match by searching for a substring in the middle of the title
        search_term = book_title[1:5] # Take a substring from the middle
        print(f"Found book: '{book_title}'. Searching for substring: '{search_term}'...")

        # 2. Search for the book using the substring
        # Note: We did NOT configure search_fields in main.py, so this relies on auto-detection!
        search_response = await client.get(f"/api/books?q={search_term}")
        
        if search_response.status_code != 200:
            print(f"FAIL: Search failed. Status: {search_response.status_code}")
            return
        
        search_data = search_response.json()
        search_items = search_data.get("items", [])
        
        # 3. Verify results for substring search
        found = False
        for item in search_items:
            if search_term.lower() in item["title"].lower():
                found = True
                break
        
        if found:
            print(f"PASS: Successfully found book using auto-detected search with substring '{search_term}'! (Found {search_data['total']} results)")
        else:
            print(f"FAIL: Could not find book with title containing '{search_term}'")
            print(f"First 5 results: {[b['title'] for b in search_items[:5]]}")

        # 4. Test Numeric Search (Year)
        book_year = sample_book["year"]
        print(f"Testing numeric search for Year: {book_year}...")
        response = await client.get(f"/api/books?q={book_year}")
        data = response.json()
        
        found_year = False
        for book in data["items"]:
            if book["year"] == book_year:
                found_year = True
                break
                
        if found_year:
            print(f"PASS: Successfully found book using numeric search for Year {book_year}! (Found {data['total']} results)")
        else:
            print(f"FAIL: Could not find book with Year {book_year}")

        # 5. Test Validation (Empty Fields)
        print("Testing validation (creating book with empty fields)...")
        try:
            response = await client.post("/api/books", json={
                "title": "",
                "author": "",
                "year": 0,
                "pages": 0,
                "summary": ""
            })
            if response.status_code == 422:
                print("PASS: Validation correctly returned 422 Unprocessable Entity for empty fields.")
                print(f"Errors: {response.json()}")
            else:
                print(f"FAIL: Expected 422, got {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"FAIL: Exception during validation test: {e}")

if __name__ == "__main__":
    asyncio.run(verify_books())
