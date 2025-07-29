import network
import socket
import time
import gc
import ntptime
import machine
from machine import Pin
from nec_ir_remote import NECIRRemote
import _thread
import webinterface
import config

conf = config.load_config()
SSID = conf["SSID"]
PASSWORD = conf["PASSWORD"]
GIRA_IP = str(conf["GIRA_IP"])
GIRA_PORT = int(conf["GIRA_PORT"])
MARANTZ_IP = str(conf["MARANTZ_IP"])
MARANTZ_PORT = int(conf["MARANTZ_PORT"])
VOLUME_TARGET = conf.get("VOLUME_TARGET", "GIRA").upper()

NTP_TIME_STATUS = conf.get("NTP_TIME_STATUS", False)
if isinstance(NTP_TIME_STATUS, str):
    NTP_TIME_STATUS = NTP_TIME_STATUS.lower() == "true"

RESET_HOUR = conf.get("RESET_HOUR", 5)
MUTE_HOLD_TRIGGER = conf.get("MUTE_HOLD_TRIGGER", 3)

MARANTZ_COMMAND_VOL_UP = conf["MARANTZ_COMMAND_VOL_UP"]
MARANTZ_COMMAND_VOL_DOWN = conf["MARANTZ_COMMAND_VOL_DOWN"]
GIRA_COMMAND_VOL_UP = conf["GIRA_COMMAND_VOL_UP"]
GIRA_COMMAND_VOL_DOWN = conf["GIRA_COMMAND_VOL_DOWN"]
COMMAND_PWR_ON = conf["COMMAND_PWR_ON"]
COMMAND_PWR_OFF = conf["COMMAND_PWR_OFF"]

IR_CODE_VOL_UP = int(conf["IR_CODE_VOL_UP"], 16)
IR_CODE_VOL_DOWN = int(conf["IR_CODE_VOL_DOWN"], 16)
IR_CODE_MUTE = int(conf["IR_CODE_MUTE"], 16)

TIMEZONE_OFFSET_HOURS = 2
IR_REPEAT_IGNORE_MS = 100
MUTE_IGNORE_AFTER_POWEROFF_MS = 10000
ENOMEM_THRESHOLD = 3

status_led = Pin(12, Pin.OUT)
power_on_led = Pin(14, Pin.OUT)
power_off_led = Pin(13, Pin.OUT)

sock = None
enomem_count = 0

def flash_led(duration=0.3):
    status_led.on()
    time.sleep(duration)
    status_led.off()

def update_power_leds(power_on):
    power_on_led.value(1 if power_on else 0)
    power_off_led.value(0 if power_on else 1)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    for _ in range(10):
        if wlan.isconnected():
            webinterface.log(f"✅ Verbonden met WiFi: {wlan.ifconfig()}")
            webinterface.log(f"🌐 Pico IP-adres: {wlan.ifconfig()[0]}")
            return True
        webinterface.log("🔌 Verbinden met WiFi...")
        time.sleep(1)
    return False

def get_localtime():
    return time.localtime(time.time() + TIMEZONE_OFFSET_HOURS * 3600)

def sync_time():
    if not NTP_TIME_STATUS:
        webinterface.log("⏭️ NTP Tijd synchronisatie overgeslagen (uitgeschakeld)")
        return
    for attempt in range(1, 4):
        try:
            ntptime.settime()
            webinterface.log(f"✅ Tijd gesynchroniseerd")
            local = get_localtime()
            webinterface.log(f"🕒 Tijd ingesteld op: {local[0]:04d}-{local[1]:02d}-{local[2]:02d} {local[3]:02d}:{local[4]:02d}:{local[5]:02d}")
            return
        except Exception as e:
            webinterface.log(f"🔄 NTP poging {attempt} mislukt: {e}")
    webinterface.log("❌ NTP Tijd synchronisatie mislukt na 3 pogingen")

def send_command_udp(command):
    global sock, enomem_count
    try:
        if not isinstance(command, str):
            command = str(command)
        encoded = command.encode("utf-8")
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
        addr = (GIRA_IP, GIRA_PORT)
        sock.sendto(encoded, addr)
        webinterface.log(f"📤 Verzend → {command} (UDP naar GIRA)")
        flash_led()
        return True
    except Exception as e:
        exc_type = type(e).__name__
        webinterface.log(f"❌ Verzendfout bij command '{command}': {e} ({exc_type})")
        if "ENOMEM" in str(e):
            enomem_count += 1
            webinterface.log(f"⚠️ ENOMEM teller: {enomem_count}")
            if enomem_count >= ENOMEM_THRESHOLD:
                webinterface.log("🔁 Te veel ENOMEM → reboot")
                machine.reset()
        try:
            if sock:
                sock.close()
        except:
            pass
        sock = None
        gc.collect()
        return False

def send_command_tcp(command):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect((MARANTZ_IP, MARANTZ_PORT))
        s.send(command.encode())
        s.close()
        webinterface.log(f"📤 Verzend → {command.strip()} (TCP naar MARANTZ)")
        flash_led()
        return True
    except Exception as e:
        webinterface.log(f"❌ TCP Verzendfout: {e}")
        gc.collect()
        return False

class IRHandler:
    def __init__(self):
        self.last_code = None
        self.last_time = time.ticks_ms()
        self.mute_counter = 0
        self.last_reset_date = None
        self.last_poweroff_time = 0

    def handle(self, code, *args, **kwargs):
        now = time.ticks_ms()
        if isinstance(code, str):
            webinterface.log(f"📥 Simulatiecommando ontvangen: {code}")
            self._dispatch_volume_by_button(code)
            return
        if code not in [IR_CODE_VOL_UP, IR_CODE_VOL_DOWN, IR_CODE_MUTE]:
            return
        if code == self.last_code and time.ticks_diff(now, self.last_time) < IR_REPEAT_IGNORE_MS:
            return
        self.last_code = code
        self.last_time = now
        timestamp = "{:02d}:{:02d}:{:02d}".format(*get_localtime()[3:6])
        webinterface.log(f"[{timestamp}] IR-code: {hex(code)}")
        if code == IR_CODE_VOL_UP:
            self._dispatch_volume_auto("UP")
        elif code == IR_CODE_VOL_DOWN:
            self._dispatch_volume_auto("DOWN")
        elif code == IR_CODE_MUTE:
            self.process_mute()

    def _dispatch_volume_auto(self, direction):
        # Automatisch kiezen op basis van config target
        cfg = config.load_config()
        target = cfg.get("VOLUME_TARGET", "GIRA").upper()
        if target == "MARANTZ":
            if direction == "UP":
                send_command_tcp(cfg.get("MARANTZ_COMMAND_VOL_UP"))
            else:
                send_command_tcp(cfg.get("MARANTZ_COMMAND_VOL_DOWN"))
        else:
            if direction == "UP":
                send_command_udp(cfg.get("GIRA_COMMAND_VOL_UP"))
            else:
                send_command_udp(cfg.get("GIRA_COMMAND_VOL_DOWN"))

    def _dispatch_volume_by_button(self, key):
        # Specifiek voor de webinterface-knoppen
        cfg = config.load_config()
        if key == "MARANTZ_COMMAND_VOL_UP":
            send_command_tcp(cfg.get("MARANTZ_COMMAND_VOL_UP"))
        elif key == "MARANTZ_COMMAND_VOL_DOWN":
            send_command_tcp(cfg.get("MARANTZ_COMMAND_VOL_DOWN"))
        elif key == "GIRA_COMMAND_VOL_UP":
            send_command_udp(cfg.get("GIRA_COMMAND_VOL_UP"))
        elif key == "GIRA_COMMAND_VOL_DOWN":
            send_command_udp(cfg.get("GIRA_COMMAND_VOL_DOWN"))
        elif key == "COMMAND_PWR_ON":
            send_command_udp(cfg.get("COMMAND_PWR_ON"))
        elif key == "COMMAND_PWR_OFF":
            send_command_udp(cfg.get("COMMAND_PWR_OFF"))
        else:
            webinterface.log(f"⚠️ Onbekende knopactie: {key}")

    def process_mute(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_poweroff_time) < MUTE_IGNORE_AFTER_POWEROFF_MS:
            webinterface.log("🛑 Mute genegeerd wegens recente power off")
            return
        if NTP_TIME_STATUS:
            local = get_localtime()
            today = (local[0], local[1], local[2])
            if self.last_reset_date != today and local[3] >= RESET_HOUR:
                webinterface.log("🔁 Reset mute teller na 5u")
                self.mute_counter = 0
                self.last_reset_date = today
        if self.mute_counter == 0:
            send_command_udp(COMMAND_PWR_ON)
        self.mute_counter += 1
        webinterface.log(f"🔇 Mute-teller: {self.mute_counter}")
        if self.mute_counter >= MUTE_HOLD_TRIGGER:
            send_command_udp(COMMAND_PWR_OFF)
            self.mute_counter = 0
            self.last_poweroff_time = now

webinterface.set_config_module(config)
webinterface.set_power_led_control(update_power_leds)
webinterface.log("🚀 Start")
update_power_leds(False)

if connect_wifi():
    handler = IRHandler()
    webinterface.set_ir_simulation_callback(handler.handle)
    _thread.start_new_thread(webinterface.start_web_server, ())
    sync_time()
    gc.collect()
    ir = NECIRRemote(pin_num=15, callback=handler.handle)
    webinterface.log("🎯 Pico luistert naar IR...")
    ir.listen()
else:
    webinterface.log("❌ Geen WiFi verbinding")
