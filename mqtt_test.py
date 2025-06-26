# mqtt_test.py
import paho.mqtt.client as mqtt
import time
import json
import os

# 从环境变量读取配置，如果读取不到就用默认值
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "emqx")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", None)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(">>> [TEST SCRIPT] Connected to MQTT Broker successfully!")
        # 订阅我们关心的主题
        client.subscribe("devices/+/event/#")
        client.subscribe("devices/+/action/#") # 订阅所有action
        print(">>> [TEST SCRIPT] Subscribed to 'devices/+/event/#' and 'devices/+/action/#'")
    else:
        print(f">>> [TEST SCRIPT] Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    print("\n" + "="*40)
    print(f">>> [TEST SCRIPT] MESSAGE RECEIVED!")
    print(f"    Topic: {msg.topic}")
    try:
        payload = msg.payload.decode()
        print(f"    Payload: {payload}")
        # 尝试解析JSON
        data = json.loads(payload)
        print(f"    Payload (JSON Parsed): {data}")
    except Exception as e:
        print(f"    Could not parse payload as JSON: {e}")
    print("="*40 + "\n")

client = mqtt.Client("mqtt_test_script_client")
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.on_connect = on_connect
client.on_message = on_message

print(f">>> [TEST SCRIPT] Attempting to connect to {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
try:
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
except Exception as e:
    print(f">>> [TEST SCRIPT] Connection failed with exception: {e}")
    exit()

# 使用 loop_forever() 阻塞运行，专门用于测试
print(">>> [TEST SCRIPT] Starting network loop...")
client.loop_forever()
