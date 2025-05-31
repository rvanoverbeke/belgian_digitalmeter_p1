import paho.mqtt.client as mqtt
import time
import json
import logging

from read_p1 import P1Reader

class MQTTDevice:

    def __init__(self):
        self.logger = logging.Logger(__name__)
        settings = self.read_settings()
        self.mqtt_broker = settings.get('mqtt_broker')
        self.mqtt_port = settings.get('mqtt_port')
        self.mqtt_username = settings.get('mqtt_username')
        self.mqtt_password = settings.get('mqtt_password')
        self.mqtt_client_id = settings.get('mqtt_client_id')
        self.mqtt_discovery_prefix = settings.get('mqtt_discovery_prefix')

        self.client = self.connect_mqtt()

        self.p1_reader = P1Reader()

    def read_settings(self):
        with open('settings.json', 'r') as fh:
            return json.load(fh)

    def get_readings(self):
        return self.p1_reader.run()

    def connect_mqtt(self):
        def on_connect(client, userdata, flags, rc, properties):
            if rc == 0:
                self.logger("Connected to MQTT Broker!")
            else:
                self.logger("Failed to connect, return code %d\n", rc)

        client = mqtt.Client(self.mqtt_client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(self.mqtt_username, self.mqtt_password)
        client.on_connect = on_connect
        client.connect(self.mqtt_broker, self.mqtt_port, 60)

    def publish_readings(self):
        readings = self.get_readings()
        for sensor_id, data in readings.items():
            state_topic = f"{self.mqtt_client_id}/{sensor_id}/state"
            unique_id = f"{self.mqtt_client_id}_{sensor_id}"
            discovery_topic = f"{self.mqtt_discovery_prefix}/sensor/{unique_id}/config"

            # Publish discovery config
            payload = {
                "name": data["name"],
                "state_topic": state_topic,
                "unit_of_measurement": data["unit"],
                "device_class": data["device_class"],
                "state_class": data["state_class"],
                "unique_id": unique_id,
                "availability_topic": f"{self.mqtt_client_id}/status",
                "device": {
                    "identifiers": [self.mqtt_client_id],
                    "name": "Utility Meter",
                    "manufacturer": "Custom",
                    "model": "v1"
                }
            }

            self.client.publish(discovery_topic, json.dumps(payload), qos=1, retain=True)
            self.logger(f"[DISCOVERY] Published config to {discovery_topic}")

            # Publish actual state
            self.client.publish(state_topic, data["value"], qos=1, retain=True)
            self.logger(f"[STATE] Published {data['value']} to {state_topic}")

        # Set availability
        self.client.publish(f"{self.mqtt_client_id}/status", "online", qos=1, retain=True)
        self.client.disconnect()

    def publish_loop(self):
        msg_count = 1
        while True:
            time.sleep(10)
            self.publish_readings()
            msg_count += 1
            if msg_count > 5:
                break

    def run(self):
        self.client.loop_start()
        self.publish_loop
        self.client.loop_stop()

if __name__ == "__main__":
    mqtt_device = MQTTDevice()
    mqtt_device.run()
