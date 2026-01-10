#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- CONFIGURATION ---
const char* ssid = "WIFI_SSID";
const char* password = "WIFI_PASSWORD";
const char* server_base = "http://SERVER_IP:5000";

// Traffic Light Pins
#define PIN_L1_GREEN  27
#define PIN_L1_RED    19
#define PIN_L2_GREEN  25
#define PIN_L2_RED    32
#define PIN_L3_GREEN  13
#define PIN_L3_RED    33
#define PIN_L4_GREEN  26
#define PIN_L4_RED    18

// --- LOGIC SETTINGS ---
// Max cars visible in each lane, for saturation calculation
const int LANE_CAPACITIES[4] = {5, 20, 10, 15};

const unsigned long MIN_GREEN = 5000;   // Minimum time light MUST stay green
const unsigned long MAX_GREEN = 30000;  // Maximum time before force switch
const unsigned long YELLOW_TIME = 2000;
const int BLINK_INTERVAL = 500;
const float SAT_THRESHOLD = 0.15;       // If saturation < 15%, cut the light (Gap Out)
const float SKIP_THRESHOLD = 0.05;      // If saturation < 5%, skip the lane entirely

// --- GLOBALS ---
int counts[4] = {0, 0, 0, 0};

// State Machine
enum State { SEARCH_NEXT, MIN_GREEN_PHASE, ADAPTIVE_PHASE, YELLOW_PHASE };
State currentState = SEARCH_NEXT;

int currentLane = 0;                // The lane currently green
int searchIndex = 0;                // Used to cycle through lanes
unsigned long phaseStart = 0;       // Phase start time
unsigned long lastTrafficCheck = 0; // Last traffic check time
unsigned long lastStatusPost = 0;   // Last status post time

void setup() {
    Serial.begin(115200);

    pinMode(PIN_L1_GREEN, OUTPUT);
    pinMode(PIN_L1_RED, OUTPUT);
    pinMode(PIN_L2_GREEN, OUTPUT);
    pinMode(PIN_L2_RED, OUTPUT);
    pinMode(PIN_L3_GREEN, OUTPUT);
    pinMode(PIN_L3_RED, OUTPUT);
    pinMode(PIN_L4_GREEN, OUTPUT);
    pinMode(PIN_L4_RED, OUTPUT);

    turnAllRed();

    WiFi.begin(ssid, password);
    Serial.print("Connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" Connected!");
    fetch_traffic_data();
    // Start Logic (Assume we just finished Lane 4, so we start search at Lane 1)
    currentLane = 4;
}

void loop() {
    unsigned long now = millis();

    if (now - lastTrafficCheck >= 500) {
        fetch_traffic_data();
        lastTrafficCheck = now;
    }

    if (now - lastStatusPost >= 1000) {
        post_device_status();
        lastStatusPost = now;
    }

    switch (currentState) {
        // State: find next busy lane
        case SEARCH_NEXT: {
            int candidateLane = currentLane + 1;
            if (candidateLane > 4) candidateLane = 1;
        
            float saturation = getSaturation(candidateLane);
            Serial.printf("Checking Lane %d... Sat: %.2f\n", candidateLane, saturation);

            if (saturation > SKIP_THRESHOLD) {
                switchToGreen(candidateLane);
            } else {
                Serial.printf("Skipping Lane %d (Empty)\n", candidateLane);
                currentLane = candidateLane; // Fast forward
                delay(100);
            }
            break;
        }

        // State: within minimum green time
        case MIN_GREEN_PHASE: {
            if (now - phaseStart >= MIN_GREEN) {
                currentState = ADAPTIVE_PHASE;
                Serial.println(" -> Entering Adaptive Logic");
            }
            break;
        }

        // State: adaptive green phase
        case ADAPTIVE_PHASE: {
            if (now - phaseStart >= MAX_GREEN) {
                Serial.println("Max Green Reached. Forcing Change.");
                switchToYellow();
                return;
            }

            float currentSat = getSaturation(currentLane);

            if (currentSat <= SAT_THRESHOLD) {
                Serial.printf("Lane %d Cleared (Sat: %.2f). Gapping Out.\n", currentLane, currentSat);
                switchToYellow();
            }
            break;
        }

        // State: yellow light
        case YELLOW_PHASE: {
            if (now - phaseStart >= YELLOW_TIME) {
                turnLaneRed(currentLane);
                currentState = SEARCH_NEXT;
            }
            break;
        }
    }
}

// --- Helper Functions ---

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
    turnAllRed();
    turnLaneGreen(lane);
    Serial.printf("Lane %d GREEN (Sat: %.2f)\n", lane, getSaturation(lane));
}

void switchToYellow() {
    currentState = YELLOW_PHASE;
    phaseStart = millis();
    Serial.printf("Lane %d YELLOW\n", currentLane);
}

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
    turnLaneRed(1);
    turnLaneRed(2);
    turnLaneRed(3);
    turnLaneRed(4);
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
    http.setTimeout(200);
    String url = String(server_base) + "/traffic";
    http.begin(url);
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

void post_device_status() {
    if (WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    String url = String(server_base) + "/esp_update";
    http.begin(url);
    http.addHeader("Content-Type", "application/json");

    String phaseStr = "UNKNOWN";
    if (currentState == SEARCH_NEXT) phaseStr = "SEARCHING";
    else if (currentState == MIN_GREEN_PHASE) phaseStr = "MIN_GREEN";
    else if (currentState == ADAPTIVE_PHASE) phaseStr = "ADAPTIVE_GREEN";
    else if (currentState == YELLOW_PHASE) phaseStr = "YELLOW";

    StaticJsonDocument<200> doc;
    doc["active_lane"] = currentLane;
    doc["current_phase"] = phaseStr;
    doc["phase_duration_ms"] = millis() - phaseStart;
    doc["current_saturation"] = getSaturation(currentLane);

    String requestBody;
    serializeJson(doc, requestBody);

    http.POST(requestBody);
    http.end();
}