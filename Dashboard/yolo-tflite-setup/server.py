import os
import cv2
import threading
import numpy as np
import tensorflow.lite as tflite 
from flask import Flask, jsonify
import time

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
MODEL_NAME = 'detect_traffic_s_float32.tflite'
MODEL_PATH = os.path.join(BASE_DIR, MODEL_NAME)
CONF_THRESHOLD = 0.4               
IOU_THRESHOLD = 0.45                

VIDEO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "intersection.mp4")
)

SKY_LINE = 200
Y_MIDPOINT = 300
X_MIDPOINT = 1105

traffic_state = {
    "lane1_count": 0, "lane2_count": 0, 
    "lane3_count": 0, "lane4_count": 0
}

detection_results = []
detection_frame = None
results_lock = threading.Lock()

class YOLO_TFLite:
    def __init__(self, model_path, conf_thres=0.5, iou_thres=0.45):
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        try:
            delegate = tflite.load_delegate('libmetal_delegate.dylib')
            self.interpreter = tflite.Interpreter(model_path=model_path, experimental_delegates=[delegate])
            print("GPU (Metal) delegate loaded!")
        except:
            self.interpreter = tflite.Interpreter(model_path=model_path, num_threads=4)
            print("Using CPU with 4 threads")
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()[0]
        self.input_shape = self.input_details['shape'] 
        self.input_h = self.input_shape[1]
        self.input_w = self.input_shape[2]
    
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

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
        boxes, confidences, class_ids = [], [], []
        sample_val = np.max(output_data[:, 0])
        is_normalized = sample_val < 2.0
        norm_w = self.input_w if is_normalized else 1
        norm_h = self.input_h if is_normalized else 1

        for row in output_data:
            classes_scores = row[4:] 
            max_raw_score = np.amax(classes_scores)
            score_prob = self.sigmoid(max_raw_score)
            if score_prob > self.conf_thres:
                class_id = np.argmax(classes_scores)
                x1, y1, x2, y2 = row[0] * norm_w, row[1] * norm_h, row[2] * norm_w, row[3] * norm_h
                x1 = (x1 - pad_w) / ratio[0]
                y1 = (y1 - pad_h) / ratio[1]
                x2 = (x2 - pad_w) / ratio[0]
                y2 = (y2 - pad_h) / ratio[1]
                left, top = int(x1), int(y1)
                width, height = int(x2 - x1), int(y2 - y1)
                if top < SKY_LINE:
                    continue
                boxes.append([left, top, width, height])
                confidences.append(float(score_prob))
                class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_thres, self.iou_thres)
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                x, y, w, h = boxes[i]
                results.append({"box": [x, y, x + w, y + h], "conf": confidences[i]})
        return results

inference_frame = None
inference_lock = threading.Lock()

def inference_thread(model):
    global detection_results, detection_frame, inference_frame
    
    while True:
        with inference_lock:
            if inference_frame is None:
                time.sleep(0.05)
                continue
            frame = inference_frame.copy()
            inference_frame = None
        
        results = model.detect(frame)
        
        l1, l2, l3, l4 = 0, 0, 0, 0
        for res in results:
            x1, y1, x2, y2 = res['box']
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            if cy < Y_MIDPOINT: 
                if cx < X_MIDPOINT: l1 += 1
                else: l2 += 1
            else: 
                if cx < X_MIDPOINT: l3 += 1
                else: l4 += 1
        
        traffic_state.update({"lane1_count": l1, "lane2_count": l2, "lane3_count": l3, "lane4_count": l4})
        
        for res in results:
            x1, y1, x2, y2 = map(int, res['box'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{int(res['conf']*100)}%", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        cv2.putText(frame, f"L1:{l1} L2:{l2} L3:{l3} L4:{l4}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        with results_lock:
            detection_results = results
            detection_frame = frame

@app.route('/traffic', methods=['GET'])
def get_traffic_data():
    return jsonify(traffic_state)

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

def main():
    global inference_frame
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("Flask Server on port 5000")

    model = YOLO_TFLite(MODEL_PATH, conf_thres=CONF_THRESHOLD)
    print("Model loaded")
    
    detector = threading.Thread(target=inference_thread, args=(model,), daemon=True)
    detector.start()
    
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Video file not found: {VIDEO_PATH}")
        return
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 60:
        fps = 30
    frame_delay = max(1, int(1000 / fps) - 10)
    
    print(f"Video FPS: {fps}, Frame delay: {frame_delay}ms")
    
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        frame_count += 1
        
        with inference_lock:
            if inference_frame is None:
                inference_frame = frame.copy()
        
        with results_lock:
            results = detection_results.copy()
        
        for res in results:
            x1, y1, x2, y2 = map(int, res['box'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{int(res['conf']*100)}%", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        l1, l2, l3, l4 = traffic_state["lane1_count"], traffic_state["lane2_count"], traffic_state["lane3_count"], traffic_state["lane4_count"]
        cv2.putText(frame, f"L1:{l1} L2:{l2} L3:{l3} L4:{l4}", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Traffic Monitor", frame)
        
        if cv2.waitKey(frame_delay) & 0xFF == ord('q'): 
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
