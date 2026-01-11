import os
import time
from typing import Generator

import cv2
from flask import Flask, Response

from server import (
    CONF_THRESHOLD,
    IOU_THRESHOLD,
    MODEL_NAME,
    X_MIDPOINT,
    Y_MIDPOINT,
    YOLO_TFLite,
)

app = Flask(__name__)

STREAM_PORT = 5001
STREAM_BUFFER = 3
DROP_FRAMES = 0
FRAME_SKIP = 1
JPEG_QUALITY = 80
RESIZE_TO = (960, 540)
SPEED_MULTIPLIER = 1.25
VIDEO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "intersection.mp4")
)


def draw_overlay(frame, results):
    l1 = l2 = l3 = l4 = 0

    for res in results:
        x1, y1, x2, y2 = map(int, res["box"])
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        label = f"{int(res['conf'] * 100)}%"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 230, 140), 2)
        cv2.putText(
            frame,
            label,
            (x1, max(10, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 230, 140),
            2,
        )

        if cy < Y_MIDPOINT:
            if cx < X_MIDPOINT:
                l1 += 1
            else:
                l2 += 1
        else:
            if cx < X_MIDPOINT:
                l3 += 1
            else:
                l4 += 1

    cv2.putText(
        frame,
        f"L1:{l1} L2:{l2} L3:{l3} L4:{l4}",
        (24, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 180),
        2,
    )
    return frame


def frame_generator() -> Generator[bytes, None, None]:
    model_path = os.path.join(os.path.dirname(__file__), MODEL_NAME)
    model = YOLO_TFLite(model_path, conf_thres=CONF_THRESHOLD, iou_thres=IOU_THRESHOLD)
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {VIDEO_PATH}")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, STREAM_BUFFER)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 60:
        fps = 30
    frame_interval = 1 / (fps * SPEED_MULTIPLIER)
    last_results = []
    frame_index = 0

    while True:
        for _ in range(DROP_FRAMES):
            cap.grab()

        loop_start = time.time()
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_index = 0
            continue

        if RESIZE_TO:
            frame = cv2.resize(frame, RESIZE_TO)

        frame_index += 1
        if FRAME_SKIP > 0 and frame_index % (FRAME_SKIP + 1) != 0:
            results = last_results
        else:
            results = model.detect(frame)
            last_results = results

        annotated = draw_overlay(frame, results)
        ok, buffer = cv2.imencode(
            ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        )
        if not ok:
            continue

        processing_time = time.time() - loop_start
        sleep_time = frame_interval - processing_time
        if sleep_time > 0:
            time.sleep(sleep_time)

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(frame_bytes)}\r\n\r\n".encode()
            + frame_bytes
            + b"\r\n"
        )


@app.route("/stream.mjpg")
def stream():
    return Response(frame_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=STREAM_PORT, debug=False, use_reloader=False)
