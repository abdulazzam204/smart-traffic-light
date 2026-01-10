# AI-Powered Smart Traffic Light System

An adaptive, real-time traffic control system that uses Computer Vision (YOLOv11) to optimize traffic flow. Instead of fixed timers, this system analyzes lane saturation from live city camera feeds and dynamically adjusts signal timings using an ESP32 microcontroller.

## Project Overview

Traditional traffic lights use fixed timers, leading to unnecessary waiting times at empty intersections. This project solves that by creating a **Bi-Directional IoT System**:

1.  **The "Eye" (Python Server):** Use live cctv stream, processes frames using a custom-trained **YOLOv11 (TFLite)** model, and calculates lane saturation.
2.  **The "Brain" (ESP32):** Fetches traffic data via Wi-Fi, executes an **Adaptive Round Robin** algorithm with "Gap-Out" logic, and controls the physical traffic lights.

### Key Features
* **Real-Time Detection:** Uses TensorFlow Lite for fast vehicle detection, can be run on Raspberry Pi.
* **Adaptive Logic:**
    * **Skip Logic:** Completely skips phases for empty lanes.
    * **Gap-Out:** Cuts a green light early if traffic clears up.
    * **Max-Out:** Forces a switch if a lane waits too long.
* **Bi-Directional Comms:** The ESP32 pulls data (GET) and pushes its current status (POST) back to the dashboard.

## Hardware Requirements

| Component | Quantity | Description |
| :--- | :---: | :--- |
| **ESP32 Dev Kit V1** | 1 | Main microcontroller for logic and Wi-Fi connectivity. |
| **LEDs (Red)** | 4 | Traffic light indicators for Stop. |
| **LEDs (Green)** | 4 | Traffic light indicators for Go. |
| **Resistors (220Ω)** | 8 | Current limiting for LEDs. |
| **Breadboard & Wires** | 1 | For circuit assembly. |
| **Host Computer** | 1 | Laptop, PC, or Raspberry Pi 4 to run the Python CV server. |

## Software Setup

### Prerequisites
* **Python 3.9-3.12**
* **Arduino IDE** (with ESP32 Board Manager installed)

### 1. Python Server Setup (The "Eye")

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/abdulazzam204/comp413-g6-smart-traffic-light.git](https://github.com/abdulazzam204/comp413-g6-smart-traffic-light.git)
    cd comp413-g6-smart-traffic-light
    ```

2.  **Create python venv:**
    ```bash
    python -m venv venv
    
    ```

3.  **Install Python Dependencies:**
    ```bash
    pip install flask opencv-python tensorflow numpy playwright
    ```
    or
    ```bash
    pip install -r requirements.txt
    ```
    
4.  **Install Playwright Browsers:**
    This is required to fetch the live stream tokens.
    ```bash
    playwright install chromium
    ```

5.  **Run the Server:**
    ```bash
    cd yolo-tflite-detection
    python server2.py
    ```
    *The server will start on port 5000. Note your PC's local IP address*

### 2. ESP32 Setup (The "Brain")

1.  Open `smartTraffic.ino` in the **Arduino IDE**.
2.  Install the required library:
    * Go to **Sketch > Include Library > Manage Libraries**.
    * Search for and install **ArduinoJson** (by Benoit Blanchon).
3.  **Configuration:**
    Edit the top of the `smartTraffic.ino` file with your details:
    ```cpp
    const char* ssid = "YOUR_WIFI_NAME";
    const char* password = "YOUR_WIFI_PASSWORD";
    // IMPORTANT: Replace with your PC's IP address (e.g. http://192.168.1.15:5000)
    const char* server_base = "SERVER_BASE_URL"; 
    ```
4.  **Upload:** Connect your ESP32 via USB and upload the code.

## Circuit Diagram (Pin Mapping)

Connect your LEDs to the ESP32 pins as defined in the code:

| Lane | Green LED Pin | Red LED Pin |
| :--- | :---: | :---: |
| **Lane 1** | GPIO 27 | GPIO 19 |
| **Lane 2** | GPIO 25 | GPIO 32 |
| **Lane 3** | GPIO 13 | GPIO 33 |
| **Lane 4** | GPIO 26 | GPIO 18 |

*(Note: Ensure common ground between LEDs and ESP32).*

## Usage

1.  **Start the Python Server:** It will open a window showing the live stream with bounding boxes.
2.  **Power the ESP32:** Open the Serial Monitor (115200 baud) to debug.
3.  **Observe:**
    * The ESP32 will connect to Wi-Fi.
    * It will fetch traffic data from the Python server.
    * It will continuously post its status (Active Lane, Phase) back to the server.
    * The Python window will display the overlay: `ESP: Lane X | ADAPTIVE`.

## System Architecture

![System Architecture Diagram](docs/pictures/system-architecture-diagram.png)

## Project Structure

* `server.py` : Main backend script. Runs Flask, YOLO Inference on CCTV feed, and API for intersection info.
* `smartTraffic.ino` : Code for ESP32. Handles state machine, communication with server, and LED control.
* `detect_traffic.tflite` : The quantized custom-trained YOLOv11 model.

## Group Members

* Abdullah Azzam Amrullah
* Enes Yaviç
* Ertuğrul Sarıtekin
* Mert Atalay Aktürk