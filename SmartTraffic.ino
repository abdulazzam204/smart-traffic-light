#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- CONFIGURATION ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server_url = "http://192.168.1.15:5000/traffic"; 

// Traffic Light Pins
#define PIN_L1_GREEN  27
#define PIN_L1_RED    25
#define PIN_L2_GREEN  13
#define PIN_L2_RED    14
#define PIN_L3_GREEN  32 
#define PIN_L3_RED    33 
#define PIN_L4_GREEN  18 
#define PIN_L4_RED    19 

// --- LOGIC SETTINGS ---
// Max cars visible in each lane, for saturation calc
const int LANE_CAPACITIES[4] = {5, 20, 10, 15}; 

const unsigned long MIN_GREEN = 5000;   // Minimum time light MUST stay green
const unsigned long MAX_GREEN = 15000;  // Maximum time before force switch
const unsigned long YELLOW_TIME = 2000; 
const int BLINK_INTERVAL = 500;
const float SAT_THRESHOLD = 0.15;       // If saturation < 15%, cut the light (Gap Out)
const float SKIP_THRESHOLD = 0.05;      // If saturation < 5%, skip the lane entirely

// --- GLOBALS ---
int counts[4] = {0, 0, 0, 0}; 

// State Machine
enum State { SEARCH_NEXT, MIN_GREEN_PHASE, ADAPTIVE_PHASE, YELLOW_PHASE };
State currentState = SEARCH_NEXT;

int currentLane = 0;       // The lane currently green
int searchIndex = 0;       // Used to cycle through lanes
unsigned long phaseStart = 0; // Phase start tim
unsigned long lastTrafficCheck = 0; // Last traffic check time

void setup() {
    Serial.begin(115200);
    
    // Pin Setup
    pinMode(PIN_L1_GREEN, OUTPUT); pinMode(PIN_L1_RED, OUTPUT);
    pinMode(PIN_L2_GREEN, OUTPUT); pinMode(PIN_L2_RED, OUTPUT);
    pinMode(PIN_L3_GREEN, OUTPUT); pinMode(PIN_L3_RED, OUTPUT);
    pinMode(PIN_L4_GREEN, OUTPUT); pinMode(PIN_L4_RED, OUTPUT);
    
    turnAllRed();

    // Network Setup
    WiFi.begin(ssid, password);
    Serial.print("Connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
    }
    Serial.println(" Connected!");
    
    // Initial Data Fetch
    fetch_traffic_data();
    
    // Start Logic (Assume we just finished Lane 4, so we start search at Lane 1)
    currentLane = 4; 
}

void loop() {
    unsigned long now = millis();

    // Fetch traffic update
    if (now - lastTrafficCheck >= 500) {
        fetch_traffic_data();
        lastTrafficCheck = now;
    }

    // State machine
    switch (currentState) {

        // State: find next busy lane
        case SEARCH_NEXT: {
            // next lane
            int candidateLane = currentLane + 1;
            if (candidateLane > 4) candidateLane = 1;

            // get saturation
            float saturation = getSaturation(candidateLane);
            Serial.printf("Checking Lane %d... Sat: %.2f\n", candidateLane, saturation);

            // check saturation of next lane against threshold
            if (saturation > SKIP_THRESHOLD) {
                // over threshold, switch to next lane
                switchToGreen(candidateLane);
            } else {
                // under threshold, skip to the lane after the next
                Serial.printf("Skipping Lane %d (Empty)\n", candidateLane);
                currentLane = candidateLane; // fast forward     
                delay(100); 
            }
            break;
        }

        // State: within minimum green time
        case MIN_GREEN_PHASE: {
            // ignore sensor, just check for timer
            if (now - phaseStart >= MIN_GREEN) {
                currentState = ADAPTIVE_PHASE;
                Serial.println(" -> Entering Adaptive Logic");
            }
            break;
        }

        // State: adaptive green phase
        case ADAPTIVE_PHASE: {
            // check if over max green time
            if (now - phaseStart >= MAX_GREEN) {
                Serial.println("Max Green Reached. Forcing Change.");
                switchToYellow();
                return;
            }

            // get current lane saturation
            float currentSat = getSaturation(currentLane);
            
            // check saturation against threshold
            if (currentSat <= SAT_THRESHOLD) {
                // traffic cleared, skip to next lane
                Serial.printf("Lane %d Cleared (Sat: %.2f). Gapping Out.\n", currentLane, currentSat);
                switchToYellow();
            } else {
                // traffic still exists, do nothing, continue loop
            }
            break;
        }

        // State: yellow light
        case YELLOW_PHASE: {
            if (now - phaseStart >= YELLOW_TIME) {
                turnLaneRed(currentLane);
                currentState = SEARCH_NEXT; // look for next lane
            } else {
                // blink green light
                if ((now - phaseStart) / BLINK_INTERVAL % 2 == 0) {
                    turnLaneGreen(currentLane);
                } else {
                    turnLaneOff(currentLane);
                }
            }
            break;
        }
    }

    // TODO: add upload data to dashboard
}

// Helper funtions

float getSaturation(int lane) {
    if (lane < 1 || lane > 4) return 0.0;
    float cap = LANE_CAPACITIES[lane-1];
    if (cap == 0) cap = 1; // Prevent div by zero
    float sat = counts[lane-1] / cap;
    if (sat > 1.0) sat = 1.0;
    return sat;
}

void switchToGreen(int lane) {
    currentLane = lane;
    currentState = MIN_GREEN_PHASE;
    phaseStart = millis();

    turnAllRed(); // Ensure safety
    turnLaneGreen(lane);
    
    Serial.printf("Lane %d GREEN (Sat: %.2f)\n", lane, getSaturation(lane));
}

void switchToYellow() {
    currentState = YELLOW_PHASE;
    phaseStart = millis();
    Serial.printf("Lane %d YELLOW\n", currentLane);
}

// Control LEDs

void turnLaneGreen(int lane) {
    if (lane == 1) { digitalWrite(PIN_L1_RED, LOW); digitalWrite(PIN_L1_GREEN, HIGH); }
    if (lane == 2) { digitalWrite(PIN_L2_RED, LOW); digitalWrite(PIN_L2_GREEN, HIGH); }
    if (lane == 3) { digitalWrite(PIN_L3_RED, LOW); digitalWrite(PIN_L3_GREEN, HIGH); }
    if (lane == 4) { digitalWrite(PIN_L4_RED, LOW); digitalWrite(PIN_L4_GREEN, HIGH); }
}

void turnLaneRed(int lane) {
    if (lane == 1) { digitalWrite(PIN_L1_GREEN, LOW); digitalWrite(PIN_L1_RED, HIGH); }
    if (lane == 2) { digitalWrite(PIN_L2_GREEN, LOW); digitalWrite(PIN_L2_RED, HIGH); }
    if (lane == 3) { digitalWrite(PIN_L3_GREEN, LOW); digitalWrite(PIN_L3_RED, HIGH); }
    if (lane == 4) { digitalWrite(PIN_L4_GREEN, LOW); digitalWrite(PIN_L4_RED, HIGH); }
}

void turnAllRed() {
    turnLaneRed(1); turnLaneRed(2); turnLaneRed(3); turnLaneRed(4);
}

void turnLaneOff(int lane) {
    if (lane == 1) { digitalWrite(PIN_L1_GREEN, LOW); digitalWrite(PIN_L1_RED, LOW); }
    if (lane == 2) { digitalWrite(PIN_L2_GREEN, LOW); digitalWrite(PIN_L2_RED, LOW); }
    if (lane == 3) { digitalWrite(PIN_L3_GREEN, LOW); digitalWrite(PIN_L3_RED, LOW); }
    if (lane == 4) { digitalWrite(PIN_L4_GREEN, LOW); digitalWrite(PIN_L4_RED, LOW); }
}

// --- NETWORK ---
void fetch_traffic_data() {
    HTTPClient http;
    http.setTimeout(200); // Fast timeout
    http.begin(server_url);
    int httpCode = http.GET();
    
    if (httpCode == 200) {
        String payload = http.getString();
        StaticJsonDocument<200> doc;
        DeserializationError error = deserializeJson(doc, payload);
        if (!error) {
            counts[0] = doc["lane1_count"];
            counts[1] = doc["lane2_count"];
            counts[2] = doc["lane3_count"];
            counts[3] = doc["lane4_count"];
        }
    }
    http.end();
}