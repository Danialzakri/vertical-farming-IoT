#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <DHT.h>
#include <BH1750.h>
#include <RapidBootWiFi.h>
#include <thingssentralbatch.h>
#include <WebServer.h> // TAMBAH

// ============================================================
// PIN DEFINITIONS
// ============================================================
#define DHT22_L1_PIN    4
#define DHT22_L2_PIN   18
#define DHT22_L3_PIN   19

#define SDA_L1L2       32
#define SCL_L1L2       33
#define SDA_L3         25
#define SCL_L3         26

#define DHTTYPE        DHT22
#define BUTTON_PIN      0

// ============================================================
// DEFAULT CONFIGURATION
// ============================================================
const String defaultUserID = "Danialzakri";

// ============================================================
// THINGSSENTRAL CONFIGURATION
// ============================================================
const String serverURL = "https://thingssentral.io/postlong?data=";

const String nodeID_Temp_L1   = "0100201010105";
const String nodeID_Temp_L2   = "0100201010106";
const String nodeID_Temp_L3   = "0100201010107";
const String nodeID_Hum_L1    = "0100201010108";
const String nodeID_Hum_L2    = "0100201010109";
const String nodeID_Hum_L3    = "0100201010110";
const String nodeID_Light_L1  = "0100201010111";
const String nodeID_Light_L2  = "0100201010112";
const String nodeID_Light_L3  = "0100201010113";

// ============================================================
// HARDWARE OBJECTS
// ============================================================
ThingsSentralBatch* tsBatch = nullptr;
WiFiManagerParameter* uidParam = nullptr;

DHT dht_l1(DHT22_L1_PIN, DHTTYPE);
DHT dht_l2(DHT22_L2_PIN, DHTTYPE);
DHT dht_l3(DHT22_L3_PIN, DHTTYPE);

BH1750 bh1750_l1(0x23);
BH1750 bh1750_l2(0x5C);
BH1750 bh1750_l3(0x23);

WebServer server(80); // TAMBAH

// ============================================================
// GLOBAL SENSOR DATA (untuk app polling)
// ============================================================
float g_temp_l1 = 0.0, g_hum_l1 = 0.0, g_lux_l1 = 0.0;
float g_temp_l2 = 0.0, g_hum_l2 = 0.0, g_lux_l2 = 0.0;
float g_temp_l3 = 0.0, g_hum_l3 = 0.0, g_lux_l3 = 0.0;

// ============================================================
// TIMING VARIABLES
// ============================================================
unsigned long lastUploadTime = 0;
const unsigned long uploadInterval = 10000;

// ============================================================
// FUNCTION DECLARATIONS
// ============================================================
void readSensorsAndUpload();
void handleStatus();    // TAMBAH
void handleNotFound();  // TAMBAH

// ============================================================
// WEB SERVER HANDLERS (TAMBAH)
// ============================================================
void handleStatus() {
  String json = "{";
  json += "\"temp_l1\":" + String(g_temp_l1, 1) + ",";
  json += "\"hum_l1\":"  + String(g_hum_l1, 1) + ",";
  json += "\"lux_l1\":"  + String(g_lux_l1, 1) + ",";
  json += "\"temp_l2\":" + String(g_temp_l2, 1) + ",";
  json += "\"hum_l2\":"  + String(g_hum_l2, 1) + ",";
  json += "\"lux_l2\":"  + String(g_lux_l2, 1) + ",";
  json += "\"temp_l3\":" + String(g_temp_l3, 1) + ",";
  json += "\"hum_l3\":"  + String(g_hum_l3, 1) + ",";
  json += "\"lux_l3\":"  + String(g_lux_l3, 1);
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
  Serial.println("  ESP32_2 — Vertical Farm Monitor");
  Serial.println("  DHT22 x3 | BH1750 x3 | ThingsSentral | AppLink");
  Serial.println("========================================");

  // --- Init I2C buses ---
  Wire.begin(SDA_L1L2, SCL_L1L2);
  Wire1.begin(SDA_L3, SCL_L3);

  // --- Init DHT22 ---
  dht_l1.begin();
  dht_l2.begin();
  dht_l3.begin();

  // --- Init BH1750 ---
  if (!bh1750_l1.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x23, &Wire)) {
    Serial.println("[ERROR] BH1750 Level 1 init failed!");
  }
  if (!bh1750_l2.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x5C, &Wire)) {
    Serial.println("[ERROR] BH1750 Level 2 init failed!");
  }
  if (!bh1750_l3.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x23, &Wire1)) {
    Serial.println("[ERROR] BH1750 Level 3 init failed!");
  }

  // --- RapidBootWiFi Config ---
  myWiFi.setAPName("VF_Monitor_Sensors");
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
    Serial.println("Manual Portal Triggered — Connect to AP 'VF_Monitor_Sensors'");
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
      readSensorsAndUpload();
    } else {
      Serial.println("WiFi Offline — Skipping Upload");
    }
  }
}

// ============================================================
// SENSOR READING & UPLOAD
// ============================================================
void readSensorsAndUpload() {
  Serial.println("Reading sensors...");

  // --- DHT22 ---
  float t1 = dht_l1.readTemperature();
  float h1 = dht_l1.readHumidity();
  float t2 = dht_l2.readTemperature();
  float h2 = dht_l2.readHumidity();
  float t3 = dht_l3.readTemperature();
  float h3 = dht_l3.readHumidity();

  if (isnan(t1) || isnan(h1)) Serial.println("[WARN] DHT L1 read failed!");
  if (isnan(t2) || isnan(h2)) Serial.println("[WARN] DHT L2 read failed!");
  if (isnan(t3) || isnan(h3)) Serial.println("[WARN] DHT L3 read failed!");

  // --- BH1750 ---
  float lux1 = bh1750_l1.readLightLevel();
  float lux2 = bh1750_l2.readLightLevel();
  float lux3 = bh1750_l3.readLightLevel();

  if (lux1 < 0) Serial.println("[WARN] BH1750 L1 read failed!");
  if (lux2 < 0) Serial.println("[WARN] BH1750 L2 read failed!");
  if (lux3 < 0) Serial.println("[WARN] BH1750 L3 read failed!");

  // Simpan ke global untuk app polling
  g_temp_l1 = isnan(t1) ? 0.0 : t1;
  g_hum_l1  = isnan(h1) ? 0.0 : h1;
  g_lux_l1  = lux1 < 0 ? 0.0 : lux1;
  g_temp_l2 = isnan(t2) ? 0.0 : t2;
  g_hum_l2  = isnan(h2) ? 0.0 : h2;
  g_lux_l2  = lux2 < 0 ? 0.0 : lux2;
  g_temp_l3 = isnan(t3) ? 0.0 : t3;
  g_hum_l3  = isnan(h3) ? 0.0 : h3;
  g_lux_l3  = lux3 < 0 ? 0.0 : lux3;

  Serial.println("----- Sensor Data -----");
  Serial.printf("L1  T:%5.1f C  H:%5.1f %%  L:%7.1f lx\n", g_temp_l1, g_hum_l1, g_lux_l1);
  Serial.printf("L2  T:%5.1f C  H:%5.1f %%  L:%7.1f lx\n", g_temp_l2, g_hum_l2, g_lux_l2);
  Serial.printf("L3  T:%5.1f C  H:%5.1f %%  L:%7.1f lx\n", g_temp_l3, g_hum_l3, g_lux_l3);
  Serial.println("-----------------------");

  if (tsBatch == nullptr) {
    Serial.println("[ERROR] tsBatch not initialized!");
    return;
  }

  Serial.println("Building batch...");

  tsBatch->addData(nodeID_Temp_L1,   g_temp_l1);
  tsBatch->addData(nodeID_Temp_L2,   g_temp_l2);
  tsBatch->addData(nodeID_Temp_L3,   g_temp_l3);
  tsBatch->addData(nodeID_Hum_L1,    g_hum_l1);
  tsBatch->addData(nodeID_Hum_L2,    g_hum_l2);
  tsBatch->addData(nodeID_Hum_L3,    g_hum_l3);
  tsBatch->addData(nodeID_Light_L1,  g_lux_l1);
  tsBatch->addData(nodeID_Light_L2,  g_lux_l2);
  tsBatch->addData(nodeID_Light_L3,  g_lux_l3);

  int error = tsBatch->send();
  if (!error) {
    Serial.println("Batch sent successfully!");
  } else {
    Serial.println("Failed to send batch! error code: " + String(error));
  }
  Serial.println();
}
