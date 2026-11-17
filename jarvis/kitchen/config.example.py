# Copy this file to config.py on the board and fill it in.
# The board only joins 2.4 GHz Wi-Fi.
WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"

# The server's fixed IP address and its MQTT password (on the server: grep MQTT_PASSWORD ~/jarvis/core/.env).
MQTT_HOST = "192.168.1.120"
MQTT_PORT = 1883
MQTT_USER = "jarvis"
MQTT_PASSWORD = "the long password from the server"

# Optional camera and microphone settings. Leave them out to use these defaults.
CAMERA_NAME = "Kitchen camera"   # the name on the dashboard
CAMERA_FPS = 8                   # pictures per second: lower runs cooler, higher is smoother
CAMERA_SIZE = "VGA"              # "QVGA" (320x240), "VGA" (640x480) or "SVGA" (800x600)
CAMERA_QUALITY = 80              # 0-100: higher is sharper but uses more Wi-Fi
CAMERA_FLIP = False              # True if the picture is upside down
MIC_GAIN = 16                    # 1-64: raise if the kitchen sounds too quiet
