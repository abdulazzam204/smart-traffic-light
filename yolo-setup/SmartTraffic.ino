#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- CONFIGURATION ---
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
// IP of your computer running the Python script
const char* server_url = "http://192.168.1.15:5000/traffic"; 

// Traffic Light Pins
#define PIN_L1_GREEN  27
#define PIN_L1_RED    25
#define PIN_L2_GREEN  13
#define PIN_L2_RED    14

// Globals
int lane1_count = 0;
int lane2_count = 0;
int lane3_count = 0;
int lane4_count = 0;
int l1_time = 5000; // 5s base 
int l2_time = 5000;
int l3_time = 5000;
int l4_time = 5000;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
    }
    Serial.println(" Connected!");
    
    pinMode(PIN_L1_GREEN, OUTPUT); pinMode(PIN_L1_RED, OUTPUT);
    pinMode(PIN_L2_GREEN, OUTPUT); pinMode(PIN_L2_RED, OUTPUT);
}

// get JSON data
bool fetch_traffic_data() {
    HTTPClient http;
    http.begin(server_url);
    
    int httpCode = http.GET();
    if (httpCode == 200) {
        String payload = http.getString();
        
        // Parse JSON
        StaticJsonDocument<200> doc;
        DeserializationError error = deserializeJson(doc, payload);

        if (!error) {
            lane1_count = doc["lane1_count"];
            lane2_count = doc["lane2_count"];
            lane3_count = doc["lane3_count"];
            lane4_count = doc["lane4_count"];
            Serial.printf("Updated Counts -> L1: %d | L2: %d | L3: %d | L4: %d\n", lane1_count, lane2_count, lane3_count, lane4_count);
            http.end();
            return true;
        } else {
            Serial.println("JSON Error");
        }
    } else {
        Serial.printf("HTTP Error: %d\n", httpCode);
    }
    http.end();
    return false;
}

void calculate_lights() {
    // Calculate Timings based on counts (5s base + 2s per car)
    l1_time = 5000 + (lane1_count * 2000); 
    l2_time = 5000 + (lane2_count * 2000);
    l3_time = 5000 + (lane3_count * 2000);
    l4_time = 5000 + (lane4_count * 2000);

    // Cap max time
    if (l1_time > 30000) l1_time = 30000;
    if (l2_time > 30000) l2_time = 30000;
    if (l3_time > 30000) l3_time = 30000;
    if (l4_time > 30000) l4_time = 30000;
}

void run_lights() {
    // --- PHASE 1: Lane 1 Green ---
    Serial.printf("Phase 1 GO (%d ms)\n", l1_time);
    digitalWrite(PIN_L1_RED, LOW);
    digitalWrite(PIN_L1_GREEN, HIGH);
    digitalWrite(PIN_L2_RED, HIGH);
    digitalWrite(PIN_L2_GREEN, LOW);
    digitalWrite(PIN_L3_GREEN, LOW);
    digitalWrite(PIN_L3_RED, HIGH);
    digitalWrite(PIN_L4_GREEN, LOW);
    digitalWrite(PIN_L4_RED, HIGH);
    
    delay(l1_time); // Wait for calculated time

    // Yellow/Red transition (Simplified)
    digitalWrite(PIN_L1_GREEN, LOW);
    digitalWrite(PIN_L1_RED, HIGH);
    delay(1000); // Safety buffer

    // --- PHASE 2: Lane 2 Green ---
    Serial.printf("Phase 2 GO (%d ms)\n", l2_time);
    digitalWrite(PIN_L2_RED, LOW);
    digitalWrite(PIN_L2_GREEN, HIGH);
    
    delay(l2_time); // Wait for calculated time
    
    digitalWrite(PIN_L2_GREEN, LOW);
    digitalWrite(PIN_L2_RED, HIGH);
    delay(1000); // Safety buffer

    // --- PHASE 3: Lane 3 Green ---
    Serial.printf("Phase 3 GO (%d ms)\n", l3_time);
    digitalWrite(PIN_L3_RED, LOW);
    digitalWrite(PIN_L3_GREEN, HIGH);
    
    delay(l3_time); // Wait for calculated time
    
    digitalWrite(PIN_L3_GREEN, LOW);
    digitalWrite(PIN_L3_RED, HIGH);
    delay(1000); // Safety buffer
    
    // --- PHASE 4: Lane 4 Green ---
    Serial.printf("Phase 4 GO (%d ms)\n", l4_time);
    digitalWrite(PIN_L4_RED, LOW);
    digitalWrite(PIN_L4_GREEN, HIGH);
    
    delay(l4_time); // Wait for calculated time
    
    digitalWrite(PIN_L4_GREEN, LOW);
    digitalWrite(PIN_L4_RED, HIGH);
    delay(1000); // Safety buffer
}

void loop() {
    // 1. Get Fresh Data at the start of the cycle
    fetch_traffic_data();

    // 2. Calculate lights
    calculate_lights();

    // TODO
    // 3. Send light timing data to dashboard 

    // Run lights
    run_lights();

}