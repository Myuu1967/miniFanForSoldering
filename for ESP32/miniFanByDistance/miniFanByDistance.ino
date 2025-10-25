#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>

#ifndef LED_BUILTIN
#define LED_BUILTIN 10   // XIAO ESP32C3 の内蔵LEDは GPIO10
#endif

// ====== 1) Wi-Fi設定（ご自分のSSID/パスワードに変更） ======
const char* STA_SSID = "YOUR SSID";
const char* STA_PASS = "YOUR PASSWORD";

// ====== 2) AP(アクセスポイント)の予備設定（失敗時に使用） ======
const char* AP_SSID = "XIAO-C3-LED";
const char* AP_PASS = "12345678";   // 8文字以上

WebServer server(80);

String ledStateStr() {
  return digitalRead(LED_BUILTIN) ? "ON" : "OFF";
}

void handleRoot() {
  String html = R"HTML(
<!doctype html>
<html>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32-C3 LED</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:2rem}
  button{font-size:1.2rem;padding:.8rem 1.2rem;margin:.4rem;border-radius:.6rem;border:1px solid #ccc;cursor:pointer}
  #state{font-weight:bold}
</style>
<h1>ESP32-C3 LED Controller</h1>
<p>LED: <span id="state">...</span></p>
<p>
  <button onclick="cmd('on')">ON</button>
  <button onclick="cmd('off')">OFF</button>
  <button onclick="cmd('toggle')">TOGGLE</button>
</p>
<script>
async function refresh(){
  const r = await fetch('/state'); 
  document.getElementById('state').textContent = await r.text();
}
async function cmd(c){
  await fetch('/'+c);
  refresh();
}
refresh();
</script>
</html>
)HTML";
  server.send(200, "text/html", html);
}

void handleOn()     { digitalWrite(LED_BUILTIN, HIGH); server.send(200, "text/plain", ledStateStr()); }
void handleOff()    { digitalWrite(LED_BUILTIN, LOW);  server.send(200, "text/plain", ledStateStr()); }
void handleToggle() { digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN)); server.send(200, "text/plain", ledStateStr()); }
void handleState()  { server.send(200, "text/plain", ledStateStr()); }
void handleNotFound(){ server.send(404, "text/plain", "Not found"); }

void startServer(){
  server.on("/",       handleRoot);
  server.on("/on",     handleOn);
  server.on("/off",    handleOff);
  server.on("/toggle", handleToggle);
  server.on("/state",  handleState);
  server.onNotFound(handleNotFound);
  server.begin();
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // ====== シリアル（任意） ======
  Serial.begin(115200);
  delay(100);

  // ====== ステーション(STA)接続を試す ======
  WiFi.mode(WIFI_STA);
  WiFi.begin(STA_SSID, STA_PASS);

  Serial.print("Connecting to WiFi");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 12000) { // 最大12秒待つ
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi connected! IP: ");
    Serial.println(WiFi.localIP());
    if (MDNS.begin("xiao-c3-led")) { // http://xiao-c3-led.local/
      Serial.println("mDNS responder started: xiao-c3-led.local");
    }
  } else {
    // ====== 失敗したらAPモード ======
    Serial.println("WiFi connect failed. Starting AP mode...");
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
  }

  startServer();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
}
