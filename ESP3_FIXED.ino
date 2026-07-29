#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include <RapidBootWiFi.h>
#include <thingssentralbatch.h>
#include <WebServer.h> // TAMBAH

// ============================================================
// PIN DEFINITIONS  — Ultrasonic HC-SR04
// ============================================================
#define TRIG_TANK   32
#define ECHO_TANK   33
#define TRIG_L1     18
#define ECHO_L1     19
#define TRIG_L2     17
#define ECHO_L2      5
#define TRIG_L3      4
#define ECHO_L3     16
#define BUTTON_PIN   0

// ============================================================
// TELEGRAM CONFIG
// ============================================================
#define BOT_TOKEN   "YOUR-BOT-TOKEN"
#define CHAT_ID     "YOURS"

// ============================================================
// SENSOR CALIBRATION
// ============================================================
#define TANK_EMPTY 32.0
#define TANK_FULL  2.0

#define L1_EMPTY 10.5
#define L1_FULL  4.5

#define L2_EMPTY 10.5
#define L2_FULL  4.5

#define L3_EMPTY 10.5
#define L3_FULL  4.5

// ============================================================
// DEFAULT CONFIGURATION
// ============================================================
const String defaultUserID = "Danialzakri";

// ============================================================
// THINGSSENTRAL CONFIGURATION
// ============================================================
const String serverURL = "https://thingssentral.io/postlong?data=";

const String nodeID_Tank = "0100201010305";
const String nodeID_L1   = "0100201010306";
const String nodeID_L2   = "0100201010307";
const String nodeID_L3   = "0100201010308";

// ============================================================
// HARDWARE OBJECTS
// ============================================================
ThingsSentralBatch* tsBatch = nullptr;
WiFiManagerParameter* uidParam = nullptr;

WiFiClientSecure securedClient;
UniversalTelegramBot bot(BOT_TOKEN, securedClient);

WebServer server(80); // TAMBAH

// ============================================================
// GLOBAL SENSOR DATA (untuk app polling)
// ============================================================
float g_pTank = 0.0;
float g_pL1   = 0.0;
float g_pL2   = 0.0;
float g_pL3   = 0.0;

// ============================================================
// TIMING & ALERT STATE
// ============================================================
unsigned long lastUploadTime = 0;
const unsigned long uploadInterval = 10000;

unsigned long lastTelegramAlert = 0;
const unsigned long telegramCooldown = 300000;

bool alertTank = false;
bool alertL1   = false;
bool alertL2   = false;
bool alertL3   = false;

// ============================================================
// FUNCTION DECLARATIONS
// ============================================================
float readUltrasonic(int trigPin, int echoPin);
float distanceToPercent(float distance, float maxHeight, float minHeight);
void checkAndAlert(float percent, String label, bool &alertFlag);
void readLevelsAndUpload();
void handleStatus();      // TAMBAH
void handleNotFound();    // TAMBAH

// ============================================================
// WEB SERVER HANDLERS (TAMBAH)
// ============================================================
void handleStatus() {
  String json = "{";
  json += "\"tank_pct\":" + String(g_pTank, 1) + ",";
  json += "\"l1_pct\":"   + String(g_pL1, 1) + ",";
  json += "\"l2_pct\":"   + String(g_pL2, 1) + ",";
  json += "\"l3_pct\":"   + String(g_pL3, 1);
  json += "}";
  server.send(200, "application/json", json);
}

void handleNotFound() {
  server.send(404, "text/plain", "Not Found");
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("========================================");
  Serial.println("  ESP32_3 — Vertical Farm Water Monitor");
  Serial.println("  Ultrasonic x4 | Telegram | ThingsSentral | AppLink");
  Serial.println("========================================");

  int trigPins[] = {TRIG_TANK, TRIG_L1, TRIG_L2, TRIG_L3};
  int echoPins[] = {ECHO_TANK, ECHO_L1, ECHO_L2, ECHO_L3};
  for (int i = 0; i < 4; i++) {
    pinMode(trigPins[i], OUTPUT);
    pinMode(echoPins[i], INPUT);
    digitalWrite(trigPins[i], LOW);
  }

  securedClient.setInsecure();

  myWiFi.setAPName("VF_Monitor_Water");
  uidParam = new WiFiManagerParameter("uid", "ThingsSentral UID", defaultUserID.c_str(), 20);
  myWiFi.addParameter(uidParam);
  myWiFi.setBootThresholds(3, 5);
  myWiFi.setTimeout(3000);

  myWiFi.begin();
  int bootCount = myWiFi.getCurrentBootCount();
  Serial.print("Boot Count: ");
  Serial.println(bootCount);
  delay(1000);

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  if (digitalRead(BUTTON_PIN) == LOW) {
    Serial.println("Manual Portal Triggered — Connect to AP 'VF_Monitor_Water'");
    myWiFi.openPortal();
  } else {
    Serial.println("Connecting WiFi...");
    myWiFi.connect();
  }

  if (myWiFi.wasWiFiReset()) {
    Serial.println("WiFi Credentials Reset!");
    delay(1500);
  }

  Serial.println("\n=== WiFi Status ===");
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[OK] WiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.print("[ERROR] WiFi NOT connected. Status code: ");
    Serial.println(WiFi.status());
  }
  Serial.println("===================\n");

  String configuredUID = String(uidParam->getValue());
  if (configuredUID.length() == 0) configuredUID = defaultUserID;
  Serial.print("Using ThingsSentral UID: ");
  Serial.println(configuredUID);

  tsBatch = new ThingsSentralBatch(serverURL, configuredUID);
  delay(1500);

  // TAMBAH: Start WebServer
  server.on("/status", HTTP_GET, handleStatus);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("WebServer started on port 80");

  Serial.println("System Ready.\n");
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  server.handleClient(); // TAMBAH

  myWiFi.loop();

  static unsigned long lastWiFiCheck = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastWiFiCheck >= 5000) {
    lastWiFiCheck = millis();
    Serial.print("[WARN] WiFi disconnected. Status code: ");
    Serial.println(WiFi.status());
  }

  if (millis() - lastUploadTime >= uploadInterval) {
    lastUploadTime = millis();
    if (WiFi.status() == WL_CONNECTED) {
      readLevelsAndUpload();
    } else {
      Serial.println("WiFi Offline — Skipping Upload");
    }
  }
}

// ============================================================
// ULTRASONIC READING & UPLOAD
// ============================================================
void readLevelsAndUpload() {
  Serial.println("Reading water levels...");

  float dTank = readUltrasonic(TRIG_TANK, ECHO_TANK);
  float dL1   = readUltrasonic(TRIG_L1,   ECHO_L1);
  float dL2   = readUltrasonic(TRIG_L2,   ECHO_L2);
  float dL3   = readUltrasonic(TRIG_L3,   ECHO_L3);

  float pTank = distanceToPercent(dTank, TANK_EMPTY, TANK_FULL);
  float pL1   = distanceToPercent(dL1,   L1_EMPTY,   L1_FULL);
  float pL2   = distanceToPercent(dL2,   L2_EMPTY,   L2_FULL);
  float pL3   = distanceToPercent(dL3,   L3_EMPTY,   L3_FULL);

  // Simpan ke global untuk app polling
  g_pTank = pTank;
  g_pL1   = pL1;
  g_pL2   = pL2;
  g_pL3   = pL3;

  Serial.println("----- Water Level Data -----");
  Serial.printf("Tank  D:%5.1f cm  P:%5.1f %%\n", dTank, pTank);
  Serial.printf("L1    D:%5.1f cm  P:%5.1f %%\n", dL1,   pL1);
  Serial.printf("L2    D:%5.1f cm  P:%5.1f %%\n", dL2,   pL2);
  Serial.printf("L3    D:%5.1f cm  P:%5.1f %%\n", dL3,   pL3);
  Serial.println("----------------------------");

  if (WiFi.status() == WL_CONNECTED) {
    checkAndAlert(pTank, "Tank", alertTank);
    checkAndAlert(pL1,   "Level 1", alertL1);
    checkAndAlert(pL2,   "Level 2", alertL2);
    checkAndAlert(pL3,   "Level 3", alertL3);
  }

  if (tsBatch == nullptr) {
    Serial.println("[ERROR] tsBatch not initialized!");
    return;
  }

  Serial.println("Building batch...");
  tsBatch->addData(nodeID_Tank, (float)(pTank < 0 ? 0.0f : pTank));
  tsBatch->addData(nodeID_L1,   (float)(pL1   < 0 ? 0.0f : pL1));
  tsBatch->addData(nodeID_L2,   (float)(pL2   < 0 ? 0.0f : pL2));
  tsBatch->addData(nodeID_L3,   (float)(pL3   < 0 ? 0.0f : pL3));

  int error = tsBatch->send();
  if (!error) {
    Serial.println("Batch sent successfully!");
  } else {
    Serial.println("Failed to send batch! error code: " + String(error));
  }
  Serial.println();
}

// ============================================================
// ULTRASONIC HELPER
// ============================================================
float readUltrasonic(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) {
    Serial.printf("[WARN] Ultrasonic timeout on pin %d/%d\n", trigPin, echoPin);
    return -1.0f;
  }
  float distance = duration * 0.034f / 2.0f;
  return distance;
}

// ============================================================
// PERCENTAGE CALCULATOR
// ============================================================
float distanceToPercent(float distance, float emptyDistance, float fullDistance)
{
    if(distance < 0)
        return -1;

    distance = constrain(distance, fullDistance, emptyDistance);

    float percent =
        ((emptyDistance - distance) /
        (emptyDistance - fullDistance)) * 100.0;

    return percent;
}

// ============================================================
// TELEGRAM ALERT HELPER
// ============================================================
void checkAndAlert(float percent, String label, bool &alertFlag) {
  if (percent < 0) return;

  if (percent < 30.0f && !alertFlag) {
    if (millis() - lastTelegramAlert >= telegramCooldown) {
      String msg = "⚠️ ALERT: " + label + " water level is LOW (" + String(percent, 1) + "%)!";
      Serial.println("[Telegram] " + msg);
      bot.sendMessage(CHAT_ID, msg, "");
      alertFlag = true;
      lastTelegramAlert = millis();
    }
  }
  if (percent > 35.0f && alertFlag) {
    alertFlag = false;
    String msg = "✅ " + label + " water level recovered (" + String(percent, 1) + "%).";
    Serial.println("[Telegram] " + msg);
    bot.sendMessage(CHAT_ID, msg, "");
  }
}
