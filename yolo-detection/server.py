import cv2
import threading
from flask import Flask, jsonify
from ultralytics import YOLO
from playwright.sync_api import sync_playwright

# configs
app = Flask(__name__)
MODEL_NAME = 'detect_traffic_s.pt' 
PAGE_URL = "https://tv.kayseri.bel.tr/osman-kavuncu-bulvari" 
Y_MIDPOINT = 300
X_MIDPOINT = 1105

# global variable to store latest traffic data
traffic_state = {
    "lane1_count": 0,
    "lane2_count": 0,
    "lane3_count": 0,
    "lane4_count": 0
}

# find stream url using playwright
def get_fresh_stream_url():
    print("Refreshing token... (Opening browser)")
    with sync_playwright() as p: # 
        # Launch hidden browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        found_url = []

        # Listen to network traffic for the .m3u8 file
        def handle_request(request):
            # Filter for the playlist file
            if ".m3u8" in request.url and "playlist" in request.url:
                print(f"Found new URL: {request.url[:50]}...")
                found_url.append(request.url)

        page.on("request", handle_request)

        # Go to the website
        try:
            page.goto(PAGE_URL, timeout=60000)
            # Wait a few seconds for the video to start loading
            page.wait_for_timeout(5000) 
        except Exception as e:
            print(f"Error loading page: {e}")

        browser.close()
        
        if found_url:
            return found_url[0] # Return the first valid link found
        else:
            return None

# flask server
@app.route('/traffic', methods=['GET'])
def get_traffic_data():
    return jsonify(traffic_state)

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    # start the Flask Server in a separate thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True # Kills thread when main program exits
    server_thread.start()

    # load Model & Stream
    model = YOLO(MODEL_NAME)
    current_stream_url = None

    while True:

        # get a valid URL if we don't have one
        if current_stream_url is None:
            current_stream_url = get_fresh_stream_url()
            if current_stream_url is None:
                print("Could not find stream URL. Retrying in 10s...")
                time.sleep(10)
                continue

        # connect OpenCV to that URL
        print(f"Connecting to stream...")
        cap = cv2.VideoCapture(current_stream_url)

        while True:
            ret, frame = cap.read()

            # stops the stream and fetch new one when token expires
            if not ret:
                print("Stream expired or disconnected. Fetching new token...")
                current_stream_url = None # Force a refresh
                break 

            # run inference
            results = model(frame, conf=0.4, verbose=False)
            result = results[0]
            
            # count lanes 
            height, width, _ = frame.shape
            l1 = 0
            l2 = 0
            l3 = 0
            l4 = 0
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                if center_y < Y_MIDPOINT: 
                    if center_x < X_MIDPOINT:
                        l1 += 1
                    else: 
                        l2 += 1
                else: 
                    if center_x < X_MIDPOINT:
                        l3 += 1
                    else: 
                        l4 += 1

            # update global state
            traffic_state["lane1_count"] = l1
            traffic_state["lane2_count"] = l2
            traffic_state["lane3_count"] = l3
            traffic_state["lane4_count"] = l4

            # visualization 
            annotated_frame = result.plot()
            cv2.putText(annotated_frame, f"L1: {l1} | L2: {l2} | L3: {l3} | L4: {l4}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Traffic Server", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'): break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()