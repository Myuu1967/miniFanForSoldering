# Pico W (MicroPython): 距離センサで10cm未満→Pico LED ON + XIAO LED ON
# 10cm以上→Pico LED OFF + XIAO LED OFF

# MicroPython for Raspberry Pi Pico
# HC-SR04 ultrasonic distance sensor
# trig: 出力, echo: 入力（※5V→3.3Vに分圧/レベル変換が必須）

import network, socket, time
from machine import ADC, Pin
import utime


# ==== Wi-Fi ====
WIFI_SSID = "YOUR SSID"
WIFI_PASS = "YUOR PASSWORD"

# ==== XIAO ESP32-C3 のHTTPサーバ先 ====
ESP_HOST = "192.168.0.32"   # ← XIAOのIPに置き換え
ESP_PORT = 80

# ==== センサ/LED ====
led = Pin(16, Pin.OUT)        # Pico側LED（GP16）
THRESHOLD = 10.0              # しきい値(cm)
HYST = 0.8                    # ヒステリシスでチャタリング防止（任意）

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        t0 = time.ticks_ms()
        while (not wlan.isconnected()) and time.ticks_diff(time.ticks_ms(), t0) < 15000:
            time.sleep_ms(200)
    print("Wi-Fi:", "OK" if wlan.isconnected() else "NG", wlan.ifconfig())
    return wlan.isconnected()

def http_get(path="/state"):
    # 依存パッケージ不要の素朴なHTTP GET（平文）
    try:
        addr = socket.getaddrinfo(ESP_HOST, ESP_PORT)[0][-1]
        s = socket.socket()
        s.settimeout(1500)  # msではなく秒扱いの実装もあるので注意（環境により調整）
        s.connect(addr)
        req = "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n".format(path, ESP_HOST)
        s.send(req.encode())
        # レスポンスは読み流し
        while True:
            data = s.recv(1024)
            if not data:
                break
        s.close()
        return True
    except Exception as e:
        # print("HTTP error:", e)
        return False

# def read_distance():
#     val = adc.read_u16()
#     buf.append(val)
#     if len(buf) > N:
#         buf.pop(0)
#     avg = sum(buf) / len(buf)
#     voltage = avg * value2volt
#     distance = voltage * a + b
#     return avg, voltage, distance

# === 配線に合わせて変更（例: TRIG=GP3, ECHO=GP2） ===
TRIG_PIN = 3   # GP3
ECHO_PIN = 2   # GP2

trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)

# 音速[m/s]（約20℃で343m/s）。温度補正したい場合は後述のv_soundを変更してください。
def distance_cm(timeout_us=30000, v_sound=343.0):
    """
    HC-SR04で距離[cm]を1回測定して返す。
    timeout_us: タイムアウト（μs）。デフォルト30ms ≒ 5m往復
    v_sound: 音速[m/s]（温度補正したい場合に上書き）

    戻り値: 距離[cm]（測定失敗時はNone）
    """
    # 1) トリガパルス（10μs以上のH）
    trig.value(0)
    utime.sleep_us(3)
    trig.value(1)
    utime.sleep_us(10)
    trig.value(0)

    # 2) Echo立ち上がり待ち（タイムアウト付き）
    start = utime.ticks_us()
    while echo.value() == 0:
        if utime.ticks_diff(utime.ticks_us(), start) > timeout_us:
            return None
    t0 = utime.ticks_us()

    # 3) Echo立ち下がり待ち（タイムアウト付き）
    while echo.value() == 1:
        if utime.ticks_diff(utime.ticks_us(), t0) > timeout_us:
            return None
    t1 = utime.ticks_us()

    # 往復時間Δt[μs] → 片道の距離 = (音速 * Δt) / 2
    # Δt[μs] = Δt * 1e-6 [s]
    dt_us = utime.ticks_diff(t1, t0)
    distance_m = (v_sound * (dt_us / 1_000_000.0)) / 2.0
    return distance_m * 100.0  # [cm]

def distance_cm_avg(n=5, gap_ms=30, **kw):
    """複数回測定して中央値（ノイズに強い）を返す。失敗が多い場合はNone。"""
    vals = []
    for _ in range(n):
        d = distance_cm(**kw)
        if d is not None:
            vals.append(d)
        utime.sleep_ms(gap_ms)
    if not vals:
        return None
    vals.sort()
    return vals[len(vals)//2]

def main():
    if not connect_wifi():
        print("Wi-Fi接続失敗。SSID/PASSとAPを確認してください。")
        return

    # 状態遷移で無駄なHTTP連打を防ぐ
    near = None  # 直近の状態（True=近い/False=遠い）

    while True:
        d = distance_cm_avg()
        # ヒステリシス：前状態に応じて境界をずらす
        if near is True:
            is_near = (d < THRESHOLD + HYST/2)
        elif near is False:
            is_near = (d < THRESHOLD - HYST/2)
        else:
            is_near = (d < THRESHOLD)

        # Pico側LED制御
        led.value(1 if is_near else 0)

        # 遷移したときだけXIAOに通知
        if is_near != near:
            path = "/on" if is_near else "/off"
            ok = http_get(path)
            # print("Notify", path, "->", "OK" if ok else "NG")
            near = is_near

        # デバッグ出力（任意）
        print("D:{:5.2f}cm  {}".format(d, "NEAR" if is_near else "FAR"))

        time.sleep_ms(100)

main()
