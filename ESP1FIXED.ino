#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <RapidBootWiFi.h>
#include <thingssentralbatch.h>
#include <Preferences.h>
#include <WebServer.h>
#include <time.h>

// ================= THINGSSENTRAL CONFIGURATION =================
const String serverURL = "https://thingssentral.io/postlong?data=";
const String defaultUserID = "Danialzakri";

// Node IDs
const String nodeID_Pump          = "0100201010205";
const String nodeID_LED_L1_Power  = "0100201010206";
const String nodeID_LED_L1_White  = "0100201010214";
const String nodeID_LED_L1_RB     = "0100201010215";
const String nodeID_LED_L2_Power  = "0100201010207";
const String nodeID_LED_L2_White  = "0100201010213";
const String nodeID_LED_L2_RB     = "0100201010212";
const String nodeID_LED_L3_Power  = "0100201010208";
const String nodeID_LED_L3_White  = "0100201010210";
const String nodeID_LED_L3_RB     = "0100201010211";

// ================= PIN MAPPING =================
#define PUMP_PIN         15
#define LED_LVL1_POWER   33
#define LED_LVL1_WHITE   32
#define LED_LVL1_RB      23
#define LED_LVL2_POWER   27
#define LED_LVL2_WHITE   25
#define LED_LVL2_RB      26
#define LED_LVL3_POWER   13
#define LED_LVL3_WHITE   21
#define LED_LVL3_RB      14
#define MANUAL_SETUP_PIN  0

ThingsSentralBatch* tsBatch = nullptr;
WiFiManagerParameter* uidParam = nullptr;
Preferences prefs;
bool cloudEnabled = true;
WebServer server(80);

// ================= TIMER STRUCTURE =================
struct TimerConfig {
  String onTime;
  String offTime;
  bool active;
};
TimerConfig timers[3];

// ================= FUNCTION DECLARATIONS =================
void controlRelay(String nodeId, int pin, String label);
void sendStatusToThingsSentral();
void handleStatus();
void handleCommand();
void handleTimer();
void handleNotFound();
void checkTimers();
void turnOnLevel(int level);
void turnOffLevel(int level);
String parseJsonString(String json, String key);
int parseJsonInt(String json, String key);
bool parseJsonBool(String json, String key);
bool waitForSync(int timeoutSec = 15);

// ================= WEB SERVER HANDLERS =================
void handleStatus() {
  String json = "{";
  json += "\"pump\":" + String(digitalRead(PUMP_PIN) == LOW ? 1 : 0) + ",";
  json += "\"l1_pwr\":" + String(digitalRead(LED_LVL1_POWER) == LOW ? 1 : 0) + ",";
  json += "\"l2_pwr\":" + String(digitalRead(LED_LVL2_POWER) == LOW ? 1 : 0) + ",";
  json += "\"l3_pwr\":" + String(digitalRead(LED_LVL3_POWER) == LOW ? 1 : 0);
  json += "}";
  server.send(200, "application/json", json);
}

void handleCommand() {
  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing cmd");
    return;
  }
  String cmd = server.arg("cmd");
  cmd.toUpperCase();

  if (cmd == "MANUAL") {
    cloudEnabled = false;
    prefs.putBool("cloud", false);
    server.send(200, "text/plain", "OK: MANUAL");
    return;
  }
  if (cmd == "CLOUD") {
    cloudEnabled = true;
    prefs.putBool("cloud", true);
    server.send(200, "text/plain", "OK: CLOUD");
    return;
  }

  if (cmd == "PUMP_ON") {
    digitalWrite(PUMP_PIN, LOW); prefs.putBool("pump", true);
  } else if (cmd == "PUMP_OFF") {
    digitalWrite(PUMP_PIN, HIGH); prefs.putBool("pump", false);
  }
  else if (cmd == "L1_PWR_ON") {
    digitalWrite(LED_LVL1_POWER, LOW); prefs.putBool("l1pwr", true);
    digitalWrite(LED_LVL1_WHITE, LOW); prefs.putBool("l1wht", true);
    digitalWrite(LED_LVL1_RB, LOW);    prefs.putBool("l1rb", true);
  } else if (cmd == "L1_PWR_OFF") {
    digitalWrite(LED_LVL1_POWER, HIGH); prefs.putBool("l1pwr", false);
    digitalWrite(LED_LVL1_WHITE, HIGH); prefs.putBool("l1wht", false);
    digitalWrite(LED_LVL1_RB, HIGH);  prefs.putBool("l1rb", false);
  }
  else if (cmd == "L2_PWR_ON") {
    digitalWrite(LED_LVL2_POWER, LOW); prefs.putBool("l2pwr", true);
    digitalWrite(LED_LVL2_WHITE, LOW); prefs.putBool("l2wht", true);
    digitalWrite(LED_LVL2_RB, LOW);    prefs.putBool("l2rb", true);
  } else if (cmd == "L2_PWR_OFF") {
    digitalWrite(LED_LVL2_POWER, HIGH); prefs.putBool("l2pwr", false);
    digitalWrite(LED_LVL2_WHITE, HIGH); prefs.putBool("l2wht", false);
    digitalWrite(LED_LVL2_RB, HIGH);  prefs.putBool("l2rb", false);
  }
  else if (cmd == "L3_PWR_ON") {
    digitalWrite(LED_LVL3_POWER, LOW); prefs.putBool("l3pwr", true);
    digitalWrite(LED_LVL3_WHITE, LOW); prefs.putBool("l3wht", true);
    digitalWrite(LED_LVL3_RB, LOW);    prefs.putBool("l3rb", true);
  } else if (cmd == "L3_PWR_OFF") {
    digitalWrite(LED_LVL3_POWER, HIGH); prefs.putBool("l3pwr", false);
    digitalWrite(LED_LVL3_WHITE, HIGH); prefs.putBool("l3wht", false);
    digitalWrite(LED_LVL3_RB, HIGH);  prefs.putBool("l3rb", false);
  } else {
    server.send(400, "text/plain", "Unknown cmd");
    return;
  }
  server.send(200, "text/plain", "OK: " + cmd);
}

// ================= JSON PARSER (kept for backward compatibility) =================
String parseJsonString(String json, String key) {
  String search = "\"" + key + "\":\"";
  int start = json.indexOf(search);
  if (start == -1) return "";
  start += search.length();
  int end = json.indexOf("\"", start);
  if (end == -1) return "";
  return json.substring(start, end);
}

int parseJsonInt(String json, String key) {
  String search = "\"" + key + "\":";
  int start = json.indexOf(search);
  if (start == -1) return -1;
  start += search.length();
  int end = json.indexOf(",", start);
  if (end == -1) end = json.indexOf("}", start);
  return json.substring(start, end).toInt();
}

bool parseJsonBool(String json, String key) {
  String search = "\"" + key + "\":";
  int start = json.indexOf(search);
  if (start == -1) return false;
  start += search.length();
  String val = json.substring(start, start + 6);
  return val.indexOf("true") >= 0;
}

void turnOnLevel(int level) {
  char key[16];
  if (level == 1) {
    digitalWrite(LED_LVL1_POWER, LOW);  sprintf(key, "l1pwr"); prefs.putBool(key, true);
    digitalWrite(LED_LVL1_WHITE, LOW);  sprintf(key, "l1wht"); prefs.putBool(key, true);
    digitalWrite(LED_LVL1_RB, LOW);     sprintf(key, "l1rb");  prefs.putBool(key, true);
    Serial.println("[TIMER] >>> Level 1 ON");
  } else if (level == 2) {
    digitalWrite(LED_LVL2_POWER, LOW);  sprintf(key, "l2pwr"); prefs.putBool(key, true);
    digitalWrite(LED_LVL2_WHITE, LOW);  sprintf(key, "l2wht"); prefs.putBool(key, true);
    digitalWrite(LED_LVL2_RB, LOW);     sprintf(key, "l2rb");  prefs.putBool(key, true);
    Serial.println("[TIMER] >>> Level 2 ON");
  } else if (level == 3) {
    digitalWrite(LED_LVL3_POWER, LOW);  sprintf(key, "l3pwr"); prefs.putBool(key, true);
    digitalWrite(LED_LVL3_WHITE, LOW);  sprintf(key, "l3wht"); prefs.putBool(key, true);
    digitalWrite(LED_LVL3_RB, LOW);     sprintf(key, "l3rb");  prefs.putBool(key, true);
    Serial.println("[TIMER] >>> Level 3 ON");
  }
}

void turnOffLevel(int level) {
  char key[16];
  if (level == 1) {
    digitalWrite(LED_LVL1_POWER, HIGH);  sprintf(key, "l1pwr"); prefs.putBool(key, false);
    digitalWrite(LED_LVL1_WHITE, HIGH);  sprintf(key, "l1wht"); prefs.putBool(key, false);
    digitalWrite(LED_LVL1_RB, HIGH);     sprintf(key, "l1rb");  prefs.putBool(key, false);
    Serial.println("[TIMER] >>> Level 1 OFF");
  } else if (level == 2) {
    digitalWrite(LED_LVL2_POWER, HIGH);  sprintf(key, "l2pwr"); prefs.putBool(key, false);
    digitalWrite(LED_LVL2_WHITE, HIGH);  sprintf(key, "l2wht"); prefs.putBool(key, false);
    digitalWrite(LED_LVL2_RB, HIGH);     sprintf(key, "l2rb");  prefs.putBool(key, false);
    Serial.println("[TIMER] >>> Level 2 OFF");
  } else if (level == 3) {
    digitalWrite(LED_LVL3_POWER, HIGH);  sprintf(key, "l3pwr"); prefs.putBool(key, false);
    digitalWrite(LED_LVL3_WHITE, HIGH);  sprintf(key, "l3wht"); prefs.putBool(key, false);
    digitalWrite(LED_LVL3_RB, HIGH);     sprintf(key, "l3rb");  prefs.putBool(key, false);
    Serial.println("[TIMER] >>> Level 3 OFF");
  }
}

// ================= TIMER FIX — Form-encoded + JSON fallback =================
void handleTimer() {
  // Primary: read form-encoded arguments (most reliable with ESP32 WebServer)
  String levelStr = server.arg("level");
  String onTime   = server.arg("on");
  String offTime  = server.arg("off");
  String activeStr = server.arg("active");

  // Fallback: try JSON body if form args not present (backward compat)
  if (levelStr.length() == 0) {
    String body = server.arg("plain");
    if (body.length() == 0 && server.args() > 0) body = server.arg(0);

    if (body.length() > 0) {
      int level = parseJsonInt(body, "level");
      onTime   = parseJsonString(body, "on");
      offTime  = parseJsonString(body, "off");
      bool active = parseJsonBool(body, "active");
      levelStr = String(level);
      activeStr = active ? "1" : "0";
      Serial.printf("[TIMER] JSON fallback body: %s\\n", body.c_str());
    }
  }

  int level = levelStr.toInt();
  bool active = (activeStr == "1" || activeStr == "true" || activeStr == "TRUE");

  // FIX: Pastikan format HH:MM (leading zero)
  if (onTime.length() == 4 && onTime.indexOf(':') == 1) onTime = "0" + onTime;
  if (offTime.length() == 4 && offTime.indexOf(':') == 1) offTime = "0" + offTime;

  Serial.printf("[TIMER] Received L%d: ON=%s OFF=%s Active=%d\\n", level, onTime.c_str(), offTime.c_str(), active);

  if (level >= 1 && level <= 3) {
    timers[level-1].onTime = onTime;
    timers[level-1].offTime = offTime;
    timers[level-1].active = active;

    // FIX: Guna local char buffer untuk elak temporary String c_str() dangling pointer
    char keyOn[16], keyOff[16], keyAct[16];
    sprintf(keyOn,  "t%d_on",  level);
    sprintf(keyOff, "t%d_off", level);
    sprintf(keyAct, "t%d_act", level);

    prefs.putString(keyOn, onTime);
    prefs.putString(keyOff, offTime);
    prefs.putBool(keyAct, active);

    Serial.printf("[TIMER] Saved L%d: ON=%s OFF=%s Active=%d\\n", level, onTime.c_str(), offTime.c_str(), active);
    server.send(200, "application/json", "{\"status\":\"ok\"}");
  } else {
    server.send(400, "text/plain", "Invalid level");
  }
}

void handleNotFound() {
  server.send(404, "text/plain", "Not Found");
}

// ================= NTP SYNC =================
bool waitForSync(int timeoutSec) {
  Serial.print("[NTP] Syncing time");
  configTime(8 * 3600, 0, "pool.ntp.org", "time.google.com");
  struct tm timeinfo;
  int waited = 0;
  while (!getLocalTime(&timeinfo) && waited < timeoutSec) {
    Serial.print(".");
    delay(1000);
    waited++;
  }
  Serial.println();
  if (waited >= timeoutSec) {
    Serial.println("[NTP] FAILED to sync!");
    return false;
  }
  Serial.printf("[NTP] Synced: %02d:%02d:%02d\\n", timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
  return true;
}

// ================= CHECK TIMER (FIXED) =================
void checkTimers() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return;
  }

  char currentTime[6];
  sprintf(currentTime, "%02d:%02d", timeinfo.tm_hour, timeinfo.tm_min);

  // FIX: Guna static char array instead of String untuk elak memory fragmentation
  static char lastChecked[6] = "";
  if (strcmp(lastChecked, currentTime) == 0) return;

  strncpy(lastChecked, currentTime, sizeof(lastChecked));
  lastChecked[sizeof(lastChecked) - 1] = '\\0';

  Serial.printf("[TIMER] Check at %s\\n", currentTime);

  for (int i = 0; i < 3; i++) {
    if (!timers[i].active) continue;

    Serial.printf("[TIMER] L%d ON=%s OFF=%s\\n", i+1, timers[i].onTime.c_str(), timers[i].offTime.c_str());

    if (timers[i].onTime == currentTime) {
      turnOnLevel(i+1);
    }
    if (timers[i].offTime == currentTime) {
      turnOffLevel(i+1);
    }
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  // Reset all OFF
  int pins[] = {
    PUMP_PIN, LED_LVL1_POWER, LED_LVL1_WHITE, LED_LVL1_RB,
    LED_LVL2_POWER, LED_LVL2_WHITE, LED_LVL2_RB,
    LED_LVL3_POWER, LED_LVL3_WHITE, LED_LVL3_RB
  };
  for (int p : pins) {
    pinMode(p, OUTPUT);
    digitalWrite(p, HIGH);
  }
  delay(500);

  pinMode(MANUAL_SETUP_PIN, INPUT_PULLUP);

  prefs.begin("vf_control", false);
  cloudEnabled = prefs.getBool("cloud", true);

  if (!cloudEnabled) {
    digitalWrite(PUMP_PIN,       prefs.getBool("pump",  false) ? LOW : HIGH);
    digitalWrite(LED_LVL1_POWER, prefs.getBool("l1pwr", false) ? LOW : HIGH);
    digitalWrite(LED_LVL1_WHITE, prefs.getBool("l1wht", false) ? LOW : HIGH);
    digitalWrite(LED_LVL1_RB,    prefs.getBool("l1rb",  false) ? LOW : HIGH);
    digitalWrite(LED_LVL2_POWER, prefs.getBool("l2pwr", false) ? LOW : HIGH);
    digitalWrite(LED_LVL2_WHITE, prefs.getBool("l2wht", false) ? LOW : HIGH);
    digitalWrite(LED_LVL2_RB,    prefs.getBool("l2rb",  false) ? LOW : HIGH);
    digitalWrite(LED_LVL3_POWER, prefs.getBool("l3pwr", false) ? LOW : HIGH);
    digitalWrite(LED_LVL3_WHITE, prefs.getBool("l3wht", false) ? LOW : HIGH);
    digitalWrite(LED_LVL3_RB,    prefs.getBool("l3rb",  false) ? LOW : HIGH);
  }

  // Load timer dari NVS + fix format (gunakan char buffer)
  for (int i = 1; i <= 3; i++) {
    char keyOn[16], keyOff[16], keyAct[16];
    sprintf(keyOn,  "t%d_on",  i);
    sprintf(keyOff, "t%d_off", i);
    sprintf(keyAct, "t%d_act", i);

    timers[i-1].onTime  = prefs.getString(keyOn,  "08:00");
    timers[i-1].offTime = prefs.getString(keyOff, "20:00");
    timers[i-1].active  = prefs.getBool(keyAct, false);

    if (timers[i-1].onTime.length() == 4 && timers[i-1].onTime.indexOf(':') == 1) 
      timers[i-1].onTime = "0" + timers[i-1].onTime;
    if (timers[i-1].offTime.length() == 4 && timers[i-1].offTime.indexOf(':') == 1) 
      timers[i-1].offTime = "0" + timers[i-1].offTime;
  }

  myWiFi.setAPName("ESP32_1_KAWALAN");
  uidParam = new WiFiManagerParameter("userID", "ThingsSentral User ID", defaultUserID.c_str(), 20);
  myWiFi.addParameter(uidParam);

  myWiFi.begin();
  if (digitalRead(MANUAL_SETUP_PIN) == LOW) {
    myWiFi.openPortal();
  } else {
    myWiFi.connect();
  }

  delay(1000);
  String configuredUID = (String(uidParam->getValue()).length() > 0) ? String(uidParam->getValue()) : defaultUserID;
  tsBatch = new ThingsSentralBatch(serverURL, configuredUID);

  // NTP sync — FIX
  waitForSync(15);

  // WebServer
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/command", HTTP_GET, handleCommand);
  server.on("/timer", HTTP_POST, handleTimer);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.println("\\n==============================================");
  Serial.println("System Ready. UID: " + configuredUID);
  Serial.println("WebServer: port 80");
  Serial.println("Timer: active (NTP synced)");
  Serial.println("==============================================");
}

// ================= LOOP =================
void loop() {
  server.handleClient();
  checkTimers(); // FIX: dipanggil setiap loop

  myWiFi.loop();

  if (WiFi.status() == WL_CONNECTED) {
    if (cloudEnabled) {
      controlRelay(nodeID_Pump, PUMP_PIN, "PUMP");
      controlRelay(nodeID_LED_L1_Power, LED_LVL1_POWER, "LED L1 PWR");
      controlRelay(nodeID_LED_L1_White, LED_LVL1_WHITE, "LED L1 WHT");
      controlRelay(nodeID_LED_L1_RB, LED_LVL1_RB, "LED L1 RB");
      controlRelay(nodeID_LED_L2_Power, LED_LVL2_POWER, "LED L2 PWR");
      controlRelay(nodeID_LED_L2_White, LED_LVL2_WHITE, "LED L2 WHT");
      controlRelay(nodeID_LED_L2_RB, LED_LVL2_RB, "LED L2 RB");
      controlRelay(nodeID_LED_L3_Power, LED_LVL3_POWER, "LED L3 PWR");
      controlRelay(nodeID_LED_L3_White, LED_LVL3_WHITE, "LED L3 WHT");
      controlRelay(nodeID_LED_L3_RB, LED_LVL3_RB, "LED L3 RB");
    }

    static unsigned long lastStatus = 0;
    if (millis() - lastStatus >= 30000) {
      sendStatusToThingsSentral();
      lastStatus = millis();
    }
  }
  delay(200);
}

void controlRelay(String nodeId, int pin, String label) {
  HTTPClient http;
  String url = "http://thingssentral.io/ReadNode?Params=tokenid|" + String(tsBatch->get_userID()) + "@NodeId|" + nodeId;
  http.begin(url);
  int httpCode = http.GET();

  if (httpCode > 0) {
    String payload = http.getString();
    if (payload.indexOf("|1") > 0) {
      digitalWrite(pin, LOW);
    } else if (payload.indexOf("|0") > 0) {
      digitalWrite(pin, HIGH);
    }
  }
  http.end();
}

void sendStatusToThingsSentral() {
  if (!tsBatch) return;

  tsBatch->addData(nodeID_Pump, (float)(digitalRead(PUMP_PIN) == LOW));
  tsBatch->addData(nodeID_LED_L1_Power, (float)(digitalRead(LED_LVL1_POWER) == LOW));
  tsBatch->addData(nodeID_LED_L1_White, (float)(digitalRead(LED_LVL1_WHITE) == LOW));
  tsBatch->addData(nodeID_LED_L1_RB, (float)(digitalRead(LED_LVL1_RB) == LOW));
  tsBatch->addData(nodeID_LED_L2_Power, (float)(digitalRead(LED_LVL2_POWER) == LOW));
  tsBatch->addData(nodeID_LED_L2_White, (float)(digitalRead(LED_LVL2_WHITE) == LOW));
  tsBatch->addData(nodeID_LED_L2_RB, (float)(digitalRead(LED_LVL2_RB) == LOW));
  tsBatch->addData(nodeID_LED_L3_Power, (float)(digitalRead(LED_LVL3_POWER) == LOW));
  tsBatch->addData(nodeID_LED_L3_White, (float)(digitalRead(LED_LVL3_WHITE) == LOW));
  tsBatch->addData(nodeID_LED_L3_RB, (float)(digitalRead(LED_LVL3_RB) == LOW));

  if (tsBatch->send() == 0) {
    Serial.println("[CLOUD] Status updated.");
  } else {
    Serial.println("[CLOUD] Failed to send batch.");
  }
}