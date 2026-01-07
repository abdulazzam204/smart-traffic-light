import cv2
import threading
import numpy as np
import tensorflow.lite as tflite 
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright
import time

# ================= CONFIGURATION =================
app = Flask(__name__)

# 1. MODEL SETTINGS
MODEL_NAME = 'detect_traffic_s_float32.tflite'
CONF_THRESHOLD = 0.50               
IOU_THRESHOLD = 0.45                

# 2. STREAM SETTINGS
PAGE_URL = "https://tv.kayseri.bel.tr/osman-kavuncu-bulvari" 

# 3. TRAFFIC LOGIC (Lane Dividers)
Y_MIDPOINT = 300   
X_MIDPOINT = 1105  
SKY_LINE = 215

# Global Storage
traffic_state = {
    "lane1_count": 0, "lane2_count": 0, 
    "lane3_count": 0, "lane4_count": 0
}
# =================================================

class YOLO_TFLite:
    def __init__(self, model_path, conf_thres=0.5, iou_thres=0.45):
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres

        try:
            print(f"🧠 Loading TFLite model: {model_path}...")
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()
        except Exception as e:
            print(f"❌ CRITICAL ERROR: Could not load model.\n{e}")
            exit()
        
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()[0]
        self.input_shape = self.input_details['shape'] 
        self.input_h = self.input_shape[1]
        self.input_w = self.input_shape[2]
        print(f"✅ Model Loaded. Input Shape: {self.input_shape}")
    
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def letterbox(self, img, new_shape=(640, 640), color=(114, 114, 114)):
        shape = img.shape[:2] 
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  
        dw /= 2  
        dh /= 2

        if shape[::-1] != new_unpad:  
            img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return img, (r, r), (dw, dh)

    def detect(self, image):
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img_resized, ratio, (pad_w, pad_h) = self.letterbox(img_rgb, (self.input_w, self.input_h))

        input_data = (img_resized / 255.0).astype(np.float32)
        input_data = np.expand_dims(input_data, axis=0)

        self.interpreter.set_tensor(self.input_details['index'], input_data)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(self.output_details['index'])[0]

        if output_data.shape[0] < output_data.shape[1]: 
            output_data = output_data.transpose()
        
        return self.postprocess(output_data, ratio, pad_w, pad_h)

    def postprocess(self, output_data, ratio, pad_w, pad_h):
        boxes = []
        confidences = []
        class_ids = []
        
        # --- AUTO-DETECT NORMALIZATION ---
        # If the first coordinate is small (< 2.0), the model is outputting 0.0-1.0
        # We must scale it up to 0-640 BEFORE doing any other math.
        sample_val = np.max(output_data[:, 0])
        is_normalized = sample_val < 2.0
        
        # Multipliers to convert (0-1) -> (0-640)
        norm_w = self.input_w if is_normalized else 1
        norm_h = self.input_h if is_normalized else 1

        for row in output_data:
            classes_scores = row[4:] 
            max_raw_score = np.amax(classes_scores)
            score_prob = self.sigmoid(max_raw_score)
            
            if score_prob > self.conf_thres:
                class_id = np.argmax(classes_scores)
                
                # 1. Get Coordinates (x1, y1, x2, y2)
                x1, y1, x2, y2 = row[0], row[1], row[2], row[3]
                
                # 2. De-Normalize (0.5 -> 320.0)
                x1 *= norm_w
                y1 *= norm_h
                x2 *= norm_w
                y2 *= norm_h

                # 3. Undo Letterbox Padding & Scaling
                # Formula: (coord - padding) / scale_ratio
                x1 = (x1 - pad_w) / ratio[0]
                y1 = (y1 - pad_h) / ratio[1]
                x2 = (x2 - pad_w) / ratio[0]
                y2 = (y2 - pad_h) / ratio[1]

                if y1 < SKY_LINE:
                    continue

                # 4. Final Box
                left = int(x1)
                top = int(y1)
                width = int(x2 - x1)
                height = int(y2 - y1)
                
                boxes.append([left, top, width, height])
                confidences.append(float(score_prob))
                class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_thres, self.iou_thres)
        
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                x, y, w, h = boxes[i]
                results.append({
                    "box": [x, y, x + w, y + h], 
                    "conf": confidences[i],
                    "class_id": class_ids[i]
                })
        return results

# --- STREAM FETCHING ---
def get_fresh_stream_url():
    print("🔄 Refreshing Stream Token...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        found_url = []
        def handle_request(request):
            if ".m3u8" in request.url and "playlist" in request.url:
                found_url.append(request.url)
        page.on("request", handle_request)
        try:
            page.goto(PAGE_URL, timeout=60000)
            page.wait_for_timeout(5000) 
        except: pass
        browser.close()
        return found_url[0] if found_url else None

@app.route('/traffic', methods=['GET'])
def get_traffic_data():
    return jsonify(traffic_state)

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# --- MAIN LOOP ---
def main():
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True 
    server_thread.start()
    print("🚀 Flask Server running on port 5000")

    model = YOLO_TFLite(MODEL_NAME, conf_thres=CONF_THRESHOLD)
    current_stream_url = None

    while True:
        if current_stream_url is None:
            current_stream_url = get_fresh_stream_url()
            if current_stream_url is None:
                time.sleep(10); continue

        cap = cv2.VideoCapture(current_stream_url)
        print("🎥 Video Capture Started!")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Stream stopped. Fetching new token...")
                current_stream_url = None
                break 

            results = model.detect(frame)
            
            # DEBUG PRINT
            if len(results) > 0:
                b = results[0]['box']
                print(f"👀 Detected {len(results)} objs. First Box: {b} | Conf: {results[0]['conf']:.2f}")

            l1, l2, l3, l4 = 0, 0, 0, 0
            
            for res in results:
                x1, y1, x2, y2 = map(int, res['box'])
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                
                cid = res['class_id']
                label = f"ID:{cid} {int(res['conf']*100)}%"
                color = (0, 255, 0)
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                
                if cy < Y_MIDPOINT: 
                    if cx < X_MIDPOINT: l1 += 1
                    else: l2 += 1
                else: 
                    if cx < X_MIDPOINT: l3 += 1
                    else: l4 += 1

            traffic_state.update({"lane1_count": l1, "lane2_count": l2, "lane3_count": l3, "lane4_count": l4})
            cv2.putText(frame, f"L1:{l1} L2:{l2} L3:{l3} L4:{l4}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Debug Traffic", frame)
            
            if cv2.waitKey(1) == ord('q'): 
                cap.release()
                cv2.destroyAllWindows()
                return

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()