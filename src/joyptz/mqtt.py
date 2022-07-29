"""
Connect to MQTT for remote control.

In order to control the camera from other systems (e.g homeassistant, 
the internet, etc.) we need a messaging protocol. MQTT is
perfect for this.
"""
import time

import paho.mqtt.client as mqtt


from .controller import Controller


class NetworkController(Controller):
    """MQTT controller"""

    def __init__(self, cam, config, log=None):
        """Construct the MQTT client."""
        super().__init__(cam, config, log)
        self._client = None
        self.start()

    def on_connect(self, client, userdata, flags, rc):
        """Do callback for when MQTT server connects."""
        self.log.info("Connected with result code %d", rc)
        client.subscribe(self.config["mqtt"]["topic"])  # subscribe in case we get disconnected

    def on_message(self, client, userdata, msg):  # pylint: disable=unused-argument
        """Do callback for when MQTT receives a message."""
        self.log.info("%s %s", msg.topic, str(msg.payload))
        key = msg.topic.split("/")[-1]
        cmd = msg.payload.decode()
        if cmd == "ptz left":
            self._move_vector = [-1,0,0]
        elif cmd == "ptz stop":
            self._move_vector = [0,0,0]
        elif cmd.startswith("preset"):
            ps = int(cmd.split()[1])
            self.cam.goto_preset(ps)

        if "ptz" in cmd:
            self._process_move_vector()

    def start(self):
        """Connect to the MQTT server."""
        conf = self.config["mqtt"]
        self.log.info("Connecting to MQTT server at %s", conf["broker"])
        self._client = mqtt.Client(
            conf["client_id"], protocol=int(conf.get("protocol", 4))
        )
        self._client.on_connect = self.on_connect
        self._client.on_message = self.on_message
        if conf.get("username"):
            self._client.username_pw_set(conf["username"], conf["password"])
        if conf.get("certificate"):
            self._client.tls_set(conf["certificate"])
        self._client.connect(
            conf["broker"], conf["port"], int(conf.get("keepalive", 60))
        )

    def loop(self):
        self._client.loop_start()
        while True:
            time.sleep(0.5)

    def stop(self):
        """End the MQTT connection."""
        self._client.loop_stop()
