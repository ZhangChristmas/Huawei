# app/mqtt/mqtt_client.py (使用 aiomqtt 重构的最终完整版)

import asyncio
import json
import ssl
import uuid
from typing import Optional, Any, Dict, List, Union

import aiomqtt  # 导入 aiomqtt

from app.core.config import settings
from app.services import (
    device_service, 
    notification_service, 
    third_party_services, 
    user_service, 
    datetime_service
)
from app.models.device_models import DeviceStatusUpdate, DeviceLocation
from app.models.notification_models import NotificationCreate, SosAlertCreate
from app.models.common_models import PyObjectId

class AsyncMQTTClient:
    def __init__(self):
        self.client: Optional[aiomqtt.Client] = None
        self._main_task: Optional[asyncio.Task] = None
        
    async def connect(self):
        """连接到MQTT Broker"""
        if self.client and self.client.is_connected():
            print("==> [MQTT] Client is already connected.")
            return

        print(f"==> [MQTT] Attempting to connect to {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}...")
        
        # aiomqtt.Client 构造函数接受与Paho类似的参数
        self.client = aiomqtt.Client(
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            username=settings.MQTT_USERNAME,
            password=settings.MQTT_PASSWORD,
            client_id=f"{settings.MQTT_CLIENT_ID_PREFIX}{str(uuid.uuid4())}",
            # 如果需要TLS，可以配置tls_params
            # tls_params=aiomqtt.TLSParameters(...)
        )
        try:
            await self.client.connect()
            print("==> [MQTT] Successfully connected to Broker.")
            # 启动主循环任务来监听消息
            self._main_task = asyncio.create_task(self._main_loop())
        except aiomqtt.MqttError as e:
            print(f"[MQTT FATAL] Could not connect to Broker: {e}")
            self.client = None

    async def _main_loop(self):
        """主循环，监听和处理消息"""
        if not self.client: return
        print("==> [MQTT] Starting message listener loop...")
        
        try:
            # 订阅主题
            await self.client.subscribe("devices/+/event/#", qos=1)
            await self.client.subscribe("devices/+/status", qos=1)
            print("==> [MQTT] Subscribed to device topics.")

            async for message in self.client.messages:
                # 这里的循环是异步的，完美集成
                await self._handle_message(message)
        except aiomqtt.MqttError as e:
            print(f"[MQTT ERROR] Message listener loop stopped due to an error: {e}")
        finally:
            print("==> [MQTT] Message listener loop finished.")

    async def _handle_message(self, message: aiomqtt.Message):
        """异步消息处理器"""
        topic = message.topic.value
        try:
            payload_data = json.loads(message.payload.decode())
            print(f"\n--- [MQTT] Message Received ---")
            print(f"  Topic: {topic}")
            print(f"  Payload: {payload_data}")
            print(f"-----------------------------")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[MQTT ERROR] Failed to decode payload from topic {topic}: {e}")
            return

        parts = topic.split('/')
        if len(parts) >= 3 and parts[0] == "devices":
            device_imei = parts[1]
            event_type = parts[3] if len(parts) > 3 and parts[2] == "event" else parts[2]
            
            handler_map = {
                "status": self._handle_device_status_update,
                "sos_alert": self._handle_sos_alert,
                "request_bill_help": self._handle_bill_request_help,
                "request_time": self._handle_request_time,
            }
            handler = handler_map.get(event_type)
            if handler:
                # 使用asyncio.create_task来并发处理，避免一个慢任务阻塞其他消息
                asyncio.create_task(handler(device_imei, payload_data))
            else:
                 print(f"[MQTT WARN] No handler for event type '{event_type}'")

    async def _handle_request_time(self, device_imei: str, payload_data: dict):
        print(f"Handling time request from device {device_imei}")
        request_id = payload_data.get("requestId")
        time_text = datetime_service.get_formatted_time_string()
        audio_url = await third_party_services.text_to_speech(time_text)
        
        response_topic = f"devices/{device_imei}/action/play_audio"
        error_topic = f"devices/{device_imei}/response/error"

        if audio_url:
            response_payload = {"url": audio_url, "requestId": request_id}
            await self.publish_message(response_topic, response_payload, qos=1)
            print(f"Sent 'play_audio' command for time back to device {device_imei}")
        else:
            error_payload = {"error": "Failed to generate voice report.", "requestId": request_id}
            await self.publish_message(error_topic, error_payload)
            print(f"TTS synthesis failed for time request from {device_imei}.")

    async def _handle_device_status_update(self, device_imei: str, payload_data: dict):
        print(f"Handling status update from {device_imei}")
        try:
            status_update = DeviceStatusUpdate(**payload_data)
            await device_service.update_device_status_by_imei(device_imei, status_update)
        except Exception as e:
            print(f"[MQTT ERROR] Error processing status update for {device_imei}: {e}")

    async def _handle_sos_alert(self, device_imei: str, payload_data: dict):
        print(f"Handling SOS alert from device {device_imei}")
        device = await device_service.get_device_by_imei(device_imei)
        if not device:
            print(f"[MQTT ERROR] SOS alert from unknown device IMEI: {device_imei}")
            return

        sos_location = None
        if payload_data.get("location"):
            try:
                sos_location = DeviceLocation(**payload_data["location"])
            except Exception as e:
                print(f"[MQTT ERROR] Invalid location data in SOS payload for {device_imei}: {e}")

        sos_alert_create = SosAlertCreate(
            deviceId=device.id,
            userId=device.userId,
            location=sos_location,
        )
        sos_alert_collection = notification_service.get_sos_alert_collection()
        await sos_alert_collection.insert_one(json.loads(sos_alert_create.model_dump_json()))

        notification_content = f"设备“{device.name}”发起了紧急呼叫！"
        notification_create = NotificationCreate(
            userId=device.userId,
            deviceId=device.id,
            deviceName=device.name,
            type="SOS",
            content=notification_content,
            payload=payload_data.get("location") or {}
        )
        await notification_service.create_notification(notification_create)

    async def _handle_bill_request_help(self, device_imei: str, payload_data: dict):
        print(f"Handling bill help request from device {device_imei}")
        device = await device_service.get_device_by_imei(device_imei)
        if not device:
            print(f"[MQTT ERROR] Bill help request from unknown device IMEI: {device_imei}")
            return
        
        notification_content = f"设备“{device.name}”话费不足，请求充值。"
        notification_create = NotificationCreate(
            userId=device.userId,
            deviceId=device.id,
            deviceName=device.name,
            type="Billing",
            content=notification_content
        )
        await notification_service.create_notification(notification_create)

    async def publish_message(self, topic: str, payload: Union[str, dict, list], qos: int = 1):
        if not self.client or not self.client.is_connected():
            print(f"[MQTT WARN] Client not connected. Cannot publish to {topic}")
            return
        message_str = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
        try:
            await self.client.publish(topic, message_str, qos=qos)
            print(f"Successfully published to {topic}")
        except aiomqtt.MqttError as e:
            print(f"Failed to publish to {topic}: {e}")

    async def disconnect(self):
        """断开连接"""
        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
        if self.client and self.client.is_connected():
            print("==> [MQTT] Disconnecting client...")
            await self.client.disconnect()
            print("==> [MQTT] Client disconnected.")


# --- 单例实例 ---
mqtt_client = AsyncMQTTClient()

# --- 全局函数，供FastAPI lifespan调用 ---
async def start_mqtt_client():
    await mqtt_client.connect()

async def stop_mqtt_client():
    await mqtt_client.disconnect()
