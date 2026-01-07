import cv2
import time
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
# THE WEBPAGE URL (Not the m3u8 link!)
# Replace this with the actual page where the video player is located.
PAGE_URL = "https://tv.kayseri.bel.tr/osman-kavuncu-bulvari" 

BATCH_NUMBER = 4
SAVE_FOLDER = f"dataset/raw_images_batch_{BATCH_NUMBER}"
CAPTURE_INTERVAL = 15
TOTAL_IMAGES_WANTED = 100
CROP_SIZE_Y = 300
CROP_SIZE_X = 1200
# ---------------------

def get_fresh_stream_url():
    print("🔄 Refreshing token... (Opening browser)")
    with sync_playwright() as p:
        # Launch hidden browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Variable to store the found URL
        found_url = []

        # Listen to network traffic for the .m3u8 file
        def handle_request(request):
            if ".m3u8" in request.url and "playlist" in request.url:
                print(f"✅ Found new URL: {request.url[:50]}...")
                found_url.append(request.url)

        page.on("request", handle_request)

        # Go to the website
        try:
            page.goto(PAGE_URL, timeout=60000)
            # Wait a few seconds for the video to start loading
            page.wait_for_timeout(5000) 
        except Exception as e:
            print(f"❌ Error loading page: {e}")

        browser.close()
        
        if found_url:
            return found_url[0] # Return the first valid link found
        else:
            return None

def main():
    import os
    if not os.path.exists(SAVE_FOLDER): os.makedirs(SAVE_FOLDER)
    
    count = 0
    current_stream_url = None
    
    while count < TOTAL_IMAGES_WANTED:
        
        # 1. Get a valid URL if we don't have one
        if current_stream_url is None:
            current_stream_url = get_fresh_stream_url()
            if current_stream_url is None:
                print("⚠️ Could not find stream URL. Retrying in 10s...")
                time.sleep(10)
                continue

        # 2. Connect OpenCV to that URL
        print("🎥 connecting to stream...")
        cap = cv2.VideoCapture(current_stream_url)
        
        last_time = time.time()
        
        while True:
            ret, frame = cap.read()
            
            # If the token expires, the stream will stop sending frames (ret = False)
            if not ret:
                print("❌ Stream expired or disconnected. Fetching new token...")
                current_stream_url = None # Force a refresh
                break 

            # Zoom & Cropping logic
            # height, width, _ = frame.shape
            # center_x, center_y = 1110, 420
            # y1 = max(0, center_y - (CROP_SIZE_Y // 2))
            # y2 = min(height, center_y + (CROP_SIZE_Y // 2))
            # x1 = max(0, center_x - (CROP_SIZE_X // 2))
            # x2 = min(width, center_x + (CROP_SIZE_X // 2))
            # zoomed_frame = frame[y1:y2, x1:x2]
            # final_frame = cv2.resize(zoomed_frame, (96, 96))

            # Display (Optional)
            cv2.imshow("Auto-Refresher Monitor", frame)

            # Auto-Capture Logic
            if time.time() - last_time > CAPTURE_INTERVAL:
                filename = f"{SAVE_FOLDER}/traffic_{BATCH_NUMBER}_{count:03d}.jpg"
                cv2.imwrite(filename, frame)
                print(f"Saved {filename} ({count+1}/{TOTAL_IMAGES_WANTED})")
                count += 1
                last_time = time.time()

            if cv2.waitKey(1) & 0xFF == ord('q'):
                return
            
            if count >= TOTAL_IMAGES_WANTED:
                print("Done!")
                return

        cap.release()

if __name__ == "__main__":
    main()