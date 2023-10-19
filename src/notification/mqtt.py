class MQTT:
    def __init__(self, topic, msg):
        self.topic = topic
        self.msg = msg
        self.broker_addr = "192.168.1.75"
        self.broker_port = "1883"
        print("MQTT - Foo")

    def send_msg(self):
        print("MQTT - Bar")
