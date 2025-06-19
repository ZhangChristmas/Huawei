# app/mqtt/mqtt_client.py
import asyncio
import json
import paho.mqtt.client as paho_mqtt
import ssl
import time
import uuid # 用于生成唯一的客户端ID
from typing import Optional, Any, Dict,List,Union

from app.core.config import settings
from app.services import device_service, notification_service, third_party_services # 导入需要的服务
from app.models.device_models import DeviceStatusUpdate, DeviceLocation # 用于解析设备上报状态
from app.models.notification_models import NotificationCreate, SosAlertCreate # 用于创建通知和SOS记录
from app.models.common_models import PyObjectId # 用于ID类型

# --- MQTT Client Singleton ---
class MQTTClientSingleton:
    _instance: Optional[paho_mqtt.Client] = None
    _is_connected: bool = False
    _loop_task: Optional[asyncio.Task] = None

    def __init__(self):
        raise RuntimeError('Call instance() instead')

    @classmethod
    def instance(cls) -> paho_mqtt.Client:
        if cls._instance is None:
            print("Creating new MQTT client instance...")
            client_id = f"{settings.MQTT_CLIENT_ID_PREFIX}{str(uuid.uuid4())}"
            # Paho MQTT v1.x.x
            # cls._instance = paho_mqtt.Client(client_id=client_id, protocol=paho_mqtt.MQTTv311)
            # Paho MQTT v2.x.x
            mqtt_transport = "tcp" # 默认
            if settings.MQTT_TLS_ENABLED:
                mqtt_transport = "websockets" if settings.MQTT_BROKER_PORT in [8084, 8083] else "tcp"

            callback_api_version = paho_mqtt.CallbackAPIVersion.VERSION2 if hasattr(paho_mqtt, 'CallbackAPIVersion') else paho_mqtt.CallbackAPIVersion.VERSION1

            if callback_api_version == paho_mqtt.CallbackAPIVersion.VERSION2:
                 cls._instance = paho_mqtt.Client(callback_api_version, client_id=client_id, transport=mqtt_transport)
            else: # Fallback for Paho MQTT v1.x or if CallbackAPIVersion is not defined as expected
                 cls._instance = paho_mqtt.Client(client_id=client_id, transport=mqtt_transport)


            cls._instance.on_connect = cls._on_connect
            cls._instance.on_disconnect = cls._on_disconnect
            cls._instance.on_message = cls._on_message # 通用消息处理器
            cls._instance.on_publish = cls._on_publish
            cls._instance.on_subscribe = cls._on_subscribe
            cls._instance.on_log = cls_on_log # 日志回调

            if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
                cls._instance.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

            if settings.MQTT_TLS_ENABLED:
                try:
                    # 根据实际情况配置TLS上下文
                    # context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    # context.load_verify_locations(cafile=settings.MQTT_CA_CERTS) # 如果需要验证服务器证书
                    # if settings.MQTT_CERTFILE and settings.MQTT_KEYFILE:
                    #     context.load_cert_chain(certfile=settings.MQTT_CERTFILE, keyfile=settings.MQTT_KEYFILE)
                    # cls._instance.tls_set_context(context)
                    # 简化版tls_set, Paho会自动处理大部分情况
                    cls._instance.tls_set(
                        ca_certs=settings.MQTT_CA_CERTS,
                        certfile=settings.MQTT_CERTFILE,
                        keyfile=settings.MQTT_KEYFILE,
                        cert_reqs=ssl.CERT_REQUIRED if settings.MQTT_CA_CERTS else ssl.CERT_NONE,
                        tls_version=ssl.PROTOCOL_TLS_CLIENT if hasattr(ssl, 'PROTOCOL_TLS_CLIENT') else ssl.PROTOCOL_TLSv1_2
                    )
                    cls._instance.tls_insecure_set(False) # 如果自签名证书且没有CA，可能需要设为True (不推荐生产)
                    print("MQTT TLS configured.")
                except Exception as e:
                    print(f"Error configuring MQTT TLS: {e}")
        return cls._instance

    @staticmethod
    def _on_connect(client: paho_mqtt.Client, userdata: Any, flags: Dict, rc: int, properties: Optional[Any] = None): # properties for v2
        # Paho MQTT v1.x rc is int, Paho MQTT v2.x rc might be an object or int
        reason_code = rc
        if hasattr(rc, 'is_failure'): # Check if rc is a ReasonCode object (Paho MQTT v2.x)
            if rc.is_failure:
                print(f"MQTT connection failed with reason: {rc.getName()}")
                MQTTClientSingleton._is_connected = False
                return
            else: # Success
                reason_code = 0 # Treat as success for the logic below

        if reason_code == 0:
            print(f"Successfully connected to MQTT Broker: {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}")
            MQTTClientSingleton._is_connected = True
            # --- 订阅设备上报的主题 ---
            # 假设所有设备都上报到 "devices/+/event/+"
            # '+' 是单层通配符, '#' 是多层通配符
            # 示例主题结构:
            # - 设备状态上报: devices/{device_imei}/event/status
            # - SOS报警:      devices/{device_imei}/event/sos_alert
            # - 话费求助:    devices/{device_imei}/event/bill_request
            # - 提醒确认:    devices/{device_imei}/event/reminder_ack
            # - 设备日志:    devices/{device_imei}/log (如果需要)
            # 更通用的订阅:
            client.subscribe("devices/+/event/#", qos=1) # 订阅所有设备的所有事件
            client.subscribe("devices/+/status", qos=1) # 也可以分开订阅
            client.subscribe("devices/+/log", qos=0)     # 日志可以用qos 0
            print("Subscribed to device topics.")
        else:
            print(f"MQTT connection failed with code {reason_code}. Check Paho MQTT return codes.")
            MQTTClientSingleton._is_connected = False

    @staticmethod
    def _on_disconnect(client: paho_mqtt.Client, userdata: Any, rc: int, properties: Optional[Any] = None): # properties for v2 (Paho v1 rc is just int)
        # Paho MQTT v2.x disconnect might also pass a DisconnectPacket or ReasonCode as rc
        reason = rc
        if hasattr(rc, 'getName'): # If it's a ReasonCode object
            reason = rc.getName()

        print(f"Disconnected from MQTT Broker with reason: {reason}. Will attempt to reconnect...")
        MQTTClientSingleton._is_connected = False
        # Paho MQTT的 loop_start() 会自动处理重连，但我们也可以在这里添加一些逻辑
        # 例如，如果是因为认证失败等永久性错误，可能不需要无限重试

    @staticmethod
    async def _handle_device_status_update(device_imei: str, payload_data: dict):
        print(f"Received status update from device {device_imei}: {payload_data}")
        try:
            status_update = DeviceStatusUpdate(**payload_data)
            updated_device = await device_service.update_device_status_by_imei(device_imei, status_update)
            if updated_device:
                print(f"Device {device_imei} status updated in DB. Online: {updated_device.isOnline}, Batt: {updated_device.battery}")
                # 如果设备从离线变在线，或状态有重要变化，可以考虑发通知给子女 (按需)
            else:
                print(f"Could not update status for device {device_imei}, device not found or no changes.")
        except Exception as e: # Catch Pydantic validation errors or other issues
            print(f"Error processing status update for {device_imei}: {e}. Payload: {payload_data}")

    @staticmethod
    async def _handle_sos_alert(device_imei: str, payload_data: dict):
        print(f"Received SOS alert from device {device_imei}: {payload_data}")
        device = await device_service.get_device_by_imei(device_imei)
        if not device:
            print(f"SOS alert from unknown device IMEI: {device_imei}")
            return

        # 1. 创建SOS报警记录 (SosAlertInDB)
        location_data = payload_data.get("location")
        sos_location = None
        if location_data and isinstance(location_data, dict):
            try:
                # 确保location数据包含必要字段
                sos_location = DeviceLocation(
                    latitude=float(location_data.get("latitude", 0.0)), # 提供默认值或更好错误处理
                    longitude=float(location_data.get("longitude", 0.0)),
                    address=location_data.get("address"),
                    timestamp=datetime.fromisoformat(location_data.get("timestamp")) if location_data.get("timestamp") else datetime.now(timezone.utc)
                )
            except (ValueError, TypeError) as e:
                print(f"Invalid location data in SOS payload for {device_imei}: {e}")

        sos_alert_create = SosAlertCreate(
            deviceId=device.id,
            userId=device.userId, # 记录下设备所属的用户
            timestamp=datetime.now(timezone.utc), # 以服务器接收时间为准，或用设备上报时间
            location=sos_location,
            # 其他 payload_data 中的信息可以存入 SosAlert 的扩展字段
        )
        # sos_alert_db = await sos_alert_service.create_sos_alert(sos_alert_create) # 假设有这个服务
        # 简化：直接存入数据库
        sos_alert_collection = get_sos_alert_collection()
        sos_alert_db_obj = SosAlertInDB(**sos_alert_create.model_dump())
        await sos_alert_collection.insert_one(sos_alert_db_obj.model_dump(by_alias=True))
        print(f"SOS alert record created for device {device.name} (User: {device.userId})")


        # 2. 创建通知 (NotificationInDB) 并推送给子女
        notification_content = f"设备“{device.name}”发起了紧急呼叫！"
        if sos_location:
            notification_content += f" 位置: 纬度 {sos_location.latitude}, 经度 {sos_location.longitude}"
        
        notification_create = NotificationCreate(
            userId=device.userId, # 通知发给设备所有者 (子女)
            deviceId=device.id,
            deviceName=device.name,
            type="SOS",
            # title: 在service.create_notification中自动生成
            content=notification_content,
            payload={"latitude": sos_location.latitude, "longitude": sos_location.longitude, "address": sos_location.address, "timestamp": sos_location.timestamp.isoformat() if sos_location and sos_location.timestamp else None} if sos_location else {}
        )
        created_notification = await notification_service.create_notification(notification_create)
        
        if created_notification:
            print(f"SOS Notification created for user {device.userId}. Triggering push...")
            # 实际的微信订阅消息推送逻辑在 notification_service.create_notification 的 TODO 中
            # 这里可以再次确认并调用，或者依赖于create_notification内部的推送
            user_to_notify = await user_service.get_user_by_id(device.userId)
            if user_to_notify and user_to_notify.wxOpenid and settings.globalData.subscribeIds.sos: # 确保配置了模板ID
                push_data = {
                    "thing1": {"value": device.name[:20]}, # 设备名称 (限制长度)
                    "time2": {"value": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}, # 报警时间
                    "thing універсальний3": {"value": "设备发起紧急呼叫，请立即处理！"[:20]} # 备注 (限制长度)
                    # 模板字段需要与您在微信后台申请的一致
                }
                # page_path = f"pages/sosMap/sosMap?lat={sos_location.latitude}&lon={sos_location.longitude}&deviceName={device.name}&time={datetime.now(timezone.utc).isoformat()}&deviceId={device.id}" if sos_location else None
                # 为了简单，先不指定page path
                await third_party_services.send_wechat_subscribe_message(
                    touser_openid=user_to_notify.wxOpenid,
                    template_id=settings.globalData.subscribeIds.sos, # 从配置中获取模板ID
                    # page=page_path,
                    data=push_data
                )


    @staticmethod
    async def _handle_bill_request(device_imei: str, payload_data: dict):
        print(f"Received bill request from device {device_imei}: {payload_data}")
        device = await device_service.get_device_by_imei(device_imei)
        if not device:
            print(f"Bill request from unknown device IMEI: {device_imei}")
            return

        notification_content = f"设备“{device.name}”话费不足，请求充值。"
        notification_create = NotificationCreate(
            userId=device.userId,
            deviceId=device.id,
            deviceName=device.name,
            type="Billing",
            content=notification_content,
            payload=payload_data # 可以包含设备上报的余额等信息
        )
        created_notification = await notification_service.create_notification(notification_create)
        if created_notification:
            print(f"Billing Notification created for user {device.userId}. Triggering push...")
            user_to_notify = await user_service.get_user_by_id(device.userId)
            if user_to_notify and user_to_notify.wxOpenid and settings.globalData.subscribeIds.billing:
                push_data = { # 根据您申请的订阅消息模板字段来填充
                    "thing1": {"value": device.name[:20]},
                    "phrase2": {"value": "话费不足"},
                    "thing3": {"value": "请及时为设备充值话费。"[:20]}
                }
                await third_party_services.send_wechat_subscribe_message(
                    touser_openid=user_to_notify.wxOpenid,
                    template_id=settings.globalData.subscribeIds.billing,
                    data=push_data
                )

    @staticmethod
    async def _handle_reminder_ack(device_imei: str, payload_data: dict):
        print(f"Received reminder acknowledgement from device {device_imei}: {payload_data}")
        reminder_id_str = payload_data.get("reminderId")
        if not reminder_id_str:
            print(f"Reminder ACK from {device_imei} missing reminderId.")
            return
        
        device = await device_service.get_device_by_imei(device_imei)
        if not device:
            print(f"Reminder ACK from unknown device IMEI: {device_imei}")
            return

        # 更新提醒的 lastConfirmedAt 状态 (在reminder_service中实现)
        # reminder = await reminder_service.get_reminder_detail_for_device(device.id, PyObjectId(reminder_id_str), device.userId)
        # if reminder:
        #     await reminder_service.update_reminder_for_device(
        #         device.id,
        #         PyObjectId(reminder_id_str),
        #         device.userId,
        #         ReminderUpdate(lastConfirmedAt=datetime.now(timezone.utc)) # 假设模型支持
        #     )
        #     print(f"Reminder {reminder_id_str} for device {device_imei} acknowledged.")
        # else:
        #     print(f"Reminder {reminder_id_str} not found for device {device_imei} or user.")
        print(f"TODO: Implement reminder acknowledgement logic for reminder {reminder_id_str} of device {device_imei}")


    @staticmethod
    def _on_message(client: paho_mqtt.Client, userdata: Any, msg: paho_mqtt.MQTTMessage):
        """
        通用消息处理器，根据主题分发到不同的异步处理函数。
        由于Paho MQTT回调是同步的，我们需要在这里创建一个新的事件循环来运行异步任务，
        或者使用 asyncio.run_coroutine_threadsafe 将异步任务提交到FastAPI的事件循环。
        更简单的方式是，如果FastAPI应用本身就在一个asyncio事件循环中运行，
        我们可以使用 asyncio.create_task()。
        """
        topic = msg.topic
        try:
            payload_str = msg.payload.decode('utf-8')
            payload_data = json.loads(payload_str)
            print(f"\n--- MQTT Message Received ---")
            print(f"Topic: {topic}")
            print(f"QoS: {msg.qos}")
            print(f"Payload: {payload_data}")
            print(f"-----------------------------")
        except json.JSONDecodeError:
            print(f"Error decoding JSON payload from topic {topic}: {msg.payload.decode('utf-8', errors='ignore')}")
            return
        except UnicodeDecodeError:
            print(f"Error decoding UTF-8 payload from topic {topic}: {msg.payload}")
            return
        except Exception as e:
            print(f"Error processing raw message from topic {topic}: {e}")
            return

        # 主题解析与分发
        # devices/{device_imei}/event/{event_type}
        # devices/{device_imei}/status
        parts = topic.split('/')
        if len(parts) >= 3 and parts[0] == "devices":
            device_imei = parts[1]
            if len(parts) == 4 and parts[2] == "event":
                event_type = parts[3]
                if event_type == "status": # 也可以用 devices/{device_imei}/status
                    asyncio.create_task(MQTTClientSingleton._handle_device_status_update(device_imei, payload_data))
                elif event_type == "sos_alert":
                    asyncio.create_task(MQTTClientSingleton._handle_sos_alert(device_imei, payload_data))
                elif event_type == "bill_request":
                    asyncio.create_task(MQTTClientSingleton._handle_bill_request(device_imei, payload_data))
                elif event_type == "reminder_ack":
                    asyncio.create_task(MQTTClientSingleton._handle_reminder_ack(device_imei, payload_data))
                else:
                    print(f"Unknown event type '{event_type}' from device {device_imei}")
            elif len(parts) == 3 and parts[2] == "status": # 直接用 devices/{device_imei}/status
                 asyncio.create_task(MQTTClientSingleton._handle_device_status_update(device_imei, payload_data))
            elif len(parts) == 3 and parts[2] == "log":
                print(f"Device Log from {device_imei}: {payload_data}") # 简单打印日志
            else:
                print(f"Unhandled device topic structure: {topic}")
        else:
            print(f"Received message on unhandled topic: {topic}")


    @staticmethod
    def _on_publish(client: paho_mqtt.Client, userdata: Any, mid: int, rc: int, properties: Optional[Any] = None): # properties for v2 (v1 rc is just int)
        # Paho MQTT v2.x rc might be a ReasonCode object
        if hasattr(rc, 'is_failure') and rc.is_failure:
             print(f"MQTT Message (MID: {mid}) failed to publish with reason: {rc.getName()}")
        elif not hasattr(rc, 'is_failure') and rc != 0: # Paho MQTT v1.x or non-ReasonCode int
             print(f"MQTT Message (MID: {mid}) failed to publish with code: {rc}")
        else:
            if settings.DEBUG: print(f"MQTT Message (MID: {mid}) published successfully.")
            pass


    @staticmethod
    def _on_subscribe(client: paho_mqtt.Client, userdata: Any, mid: int, granted_qos: List[int], properties: Optional[Any] = None): # properties for v2 (v1 granted_qos is tuple)
        print(f"Subscribed (MID: {mid}) with granted QoS: {granted_qos}")

    @classmethod
    async def connect(cls):
        if not cls._is_connected:
            client = cls.instance()
            try:
                print(f"Attempting to connect to MQTT Broker: {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}...")
                # connect_async 是非阻塞的，loop_start 会处理连接过程
                client.connect_async(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60)
                # client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60) # 阻塞连接
                # loop_start 会在一个新线程中运行网络循环
                if cls._loop_task is None or cls._loop_task.done():
                    client.loop_start() # 启动一个后台线程来处理网络事件和回调
                    # 或者使用 loop_forever() 但它会阻塞，不适合FastAPI主线程
                    # 为了在FastAPI的asyncio事件循环中更好地集成，可以考虑使用 aiomqtt 库，
                    # 但Paho也可以通过loop_start()在后台线程工作。
                    # 或者，我们可以自己创建一个异步任务来运行 client.loop_misc() 和处理网络 I/O
                    # cls._loop_task = asyncio.create_task(cls._async_loop(client))

                print("MQTT client connection process started...")
                # 等待连接成功或失败 (on_connect/on_disconnect 会更新 _is_connected)
                # 这里可以加一个短暂的等待和检查，但loop_start后连接是异步的
                # for _ in range(10): # 等待最多5秒
                #     if cls._is_connected: break
                #     await asyncio.sleep(0.5)
                # if not cls._is_connected:
                #     print("MQTT connection timeout or failed after starting loop.")

            except Exception as e:
                print(f"MQTT connection error: {e}")
                MQTTClientSingleton._is_connected = False
                if client.is_connected(): client.disconnect() # 确保断开
                if cls._loop_task and not cls._loop_task.done():
                    cls._loop_task.cancel()


    # @classmethod
    # async def _async_loop(cls, client: paho_mqtt.Client):
    #     """一个自定义的异步循环，替代loop_start，以便更好地集成到FastAPI的asyncio循环中"""
    #     print("Starting custom async MQTT loop...")
    #     while True:
    #         try:
    #             # client.loop_read()  # 处理读事件
    #             # client.loop_write() # 处理写事件 (如果需要手动管理)
    #             # client.loop_misc()  # 处理其他杂项，如ping
    #             # Paho的loop_forever或loop_start是处理这些的更简单方式
    #             # 如果要手动集成，需要非常小心地处理非阻塞IO和socket
    #             # 对于Paho，更推荐的做法是 loop_start() 让它在自己的线程中处理，
    #             # 然后通过asyncio.to_thread()或者队列来桥接同步回调到异步代码。
    #             # 或者直接使用aiomqtt库。
    #             # 这里我们还是依赖loop_start()，这个_async_loop暂时不用。
    #             await asyncio.sleep(0.1) # 避免CPU空转
    #             if not client.is_connected() and not MQTTClientSingleton._is_connected: # 检查连接状态
    #                 # 尝试重连 (Paho的loop_start会自动处理)
    #                 # print("Async loop: MQTT disconnected, attempting reconnect via loop_start logic...")
    #                 pass
    #         except asyncio.CancelledError:
    #             print("Async MQTT loop cancelled.")
    #             break
    #         except Exception as e:
    #             print(f"Error in async MQTT loop: {e}")
    #             await asyncio.sleep(5) # 发生错误时等待一段时间

    @classmethod
    async def disconnect(cls):
        client = cls.instance()
        if client and MQTTClientSingleton._is_connected: # 只有当实例存在且已连接时才操作
            print("Disconnecting MQTT client...")
            client.loop_stop() # 停止后台网络循环线程
            client.disconnect() # 发送DISCONNECT报文
            print("MQTT client disconnected command sent.")
            # on_disconnect 会被调用并设置 _is_connected = False
        if cls._loop_task and not cls._loop_task.done():
            cls._loop_task.cancel()
            try:
                await cls._loop_task
            except asyncio.CancelledError:
                pass
            print("Async MQTT loop task stopped.")
        MQTTClientSingleton._is_connected = False


    @classmethod
    def publish_message(cls, topic: str, payload: Union[str, dict, list], qos: int = 1, retain: bool = False) -> bool:
        client = cls.instance()
        if not MQTTClientSingleton._is_connected:
            print(f"MQTT client not connected. Cannot publish to {topic}")
            return False
        
        if isinstance(payload, (dict, list)):
            message_str = json.dumps(payload)
        elif isinstance(payload, str):
            message_str = payload
        else:
            print(f"Invalid payload type for MQTT publish: {type(payload)}")
            return False
            
        try:
            msg_info = client.publish(topic, message_str, qos=qos, retain=retain)
            # msg_info.wait_for_publish(timeout=5) # 阻塞等待发布完成 (可选)
            if msg_info.rc == paho_mqtt.MQTT_ERR_SUCCESS:
                if settings.DEBUG: print(f"Successfully published to {topic}: {message_str[:100]}...")
                return True
            else:
                print(f"Failed to publish to {topic} with rc: {msg_info.rc}. Payload: {message_str[:100]}...")
                return False
        except Exception as e:
            print(f"Error publishing message to {topic}: {e}")
            return False

# --- Global Functions for FastAPI Lifespan ---
mqtt_singleton = MQTTClientSingleton # 别名

async def start_mqtt_client():
    """在FastAPI应用启动时调用"""
    await mqtt_singleton.connect()

async def stop_mqtt_client():
    """在FastAPI应用关闭时调用"""
    await mqtt_singleton.disconnect()

# --- Utility for logging Paho MQTT internal logs ---
def cls_on_log(client, userdata, level, buf):
    if settings.DEBUG or level in (paho_mqtt.MQTT_LOG_WARNING, paho_mqtt.MQTT_LOG_ERR): # 生产环境只打警告和错误
        log_level_map = {
            paho_mqtt.MQTT_LOG_INFO: "INFO",
            paho_mqtt.MQTT_LOG_NOTICE: "NOTICE",
            paho_mqtt.MQTT_LOG_WARNING: "WARNING",
            paho_mqtt.MQTT_LOG_ERR: "ERROR",
            paho_mqtt.MQTT_LOG_DEBUG: "DEBUG",
        }
        print(f"PAHO-MQTT LOG ({log_level_map.get(level, 'UNKNOWN')}): {buf}")

# --- 添加对小程序 app.js 中 globalData.subscribeIds 的引用 ---
# 这部分是为了在MQTT回调中可以直接使用
# 更好的方式是在 core.config.settings 中也定义这些ID
# 我们假设 settings.globalData 是一个模拟小程序globalData的对象
# 为了简单，直接在 settings 中定义
# 在 config.py 的 Settings 类中添加:
# WX_SUBSCRIBE_IDS: Dict[str, str] = {
#     "sos": os.getenv("WX_SUB_ID_SOS", "YOUR_SOS_TEMPLATE_ID_IN_ENV"),
#     "billing": os.getenv("WX_SUB_ID_BILLING", "YOUR_BILLING_TEMPLATE_ID_IN_ENV"),
#     "lowBattery": os.getenv("WX_SUB_ID_LOW_BATT", "YOUR_LOW_BATTERY_TEMPLATE_ID_IN_ENV"),
# }
# 然后在 .env 中配置:
# WX_SUB_ID_SOS="your_real_sos_template_id"
# WX_SUB_ID_BILLING="your_real_billing_template_id"
# WX_SUB_ID_LOW_BATT="your_real_low_battery_template_id"

# 在 `config.py` 中已经定义了 WX_APPID, WX_SECRET,
# 我们可以在 `third_party_services.py` 或这里引用它们
# 而小程序中的 `subscribeIds` 需要在后端也有对应配置
# 假设 `settings` 对象上会有一个 `WX_SUBSCRIBE_IDS` 字典
# 在 _handle_sos_alert 和 _handle_bill_request 中使用 settings.WX_SUBSCRIBE_IDS.get("sos")
# 这里我们直接修改 _handle_sos_alert 等函数中的模板ID获取方式：

# (在 _handle_sos_alert 中)
# template_id=settings.WX_SUBSCRIBE_IDS.get("sos") # 修改为从settings获取
# if not template_id: print("SOS Template ID not configured in settings.WX_SUBSCRIBE_IDS")

# (在 _handle_bill_request 中)
# template_id=settings.WX_SUBSCRIBE_IDS.get("billing") # 修改为从settings获取
# if not template_id: print("Billing Template ID not configured in settings.WX_SUBSCRIBE_IDS")

# 为了让这个文件更独立，我们假设 settings 中有 WX_SUBSCRIBE_IDS，
# 并且它是一个字典，如: {"sos": "id1", "billing": "id2", "lowBattery": "id3"}
# 请确保在您的 `app/core/config.py` 中也定义和加载了这些订阅模板ID。
# 例如，在 Settings 类中添加:
# WX_SUB_ID_SOS: Optional[str] = os.getenv("WX_SUB_ID_SOS")
# WX_SUB_ID_BILLING: Optional[str] = os.getenv("WX_SUB_ID_BILLING")
# WX_SUB_ID_LOW_BATT: Optional[str] = os.getenv("WX_SUB_ID_LOW_BATT")
# 然后在 _handle_... 函数中使用 settings.WX_SUB_ID_SOS 等。

# 当前的实现是直接从 settings.globalData 访问，这需要您在 settings 对象上模拟这个结构。
# 更推荐的方式是在 settings 中明确定义这些ID。
# 为了保持与您提供的小程序代码一致，我们假设 settings.globalData.subscribeIds 存在。
# 让我们在 config.py 中添加这个模拟的 globalData.subscribeIds

# === 在 app/core/config.py 中的 Settings 类添加 ===
# class Settings:
#     # ... 其他配置 ...
#     class GlobalDataSim: # 模拟小程序的globalData结构
#         subscribeIds: Dict[str, Optional[str]] = {
#             "sos": os.getenv("WX_SUB_ID_SOS"),
#             "billing": os.getenv("WX_SUB_ID_BILLING"),
#             "lowBattery": os.getenv("WX_SUB_ID_LOW_BATT")
#         }
#     globalData = GlobalDataSim()
#
#     # 并确保 .env 中有:
#     # WX_SUB_ID_SOS="YOUR_REAL_SOS_TEMPLATE_ID"
#     # WX_SUB_ID_BILLING="YOUR_REAL_BILLING_TEMPLATE_ID"
#     # WX_SUB_ID_LOW_BATT="YOUR_REAL_LOW_BATTERY_TEMPLATE_ID"
# ===============================================

# 导入user_service (之前可能忘记了)
from app.services import user_service
