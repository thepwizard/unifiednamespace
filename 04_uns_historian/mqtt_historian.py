import random
import time
import logger 
import paho.mqtt.client as mqtt_client
import datetime



# ToDo  read these values from the configuration file 
broker = ''
port = ''
topic = "#"
qos = 1
keep_alive = 60
# generate client ID with pub prefix randomly 
client_id = f'historian-{random.randint(0, 1000)}'
username = ''
password = ''



def on_connect(client, userdata, flags, rc):
	logger.debug(
			"{"
			f"Client: {client},"
			f"Userdata: {userdata},"
			f"Flags: {flags},"
			f"rc: {rc}"
			"}" 
		)
	#subscribe to the topic only if connection was successful
	historian_client.subscribe(topic, qos)
	# TODO Error handling
	logger.info( f"Successfully connect {historian_client} to MQTT Broker at {broker}:{port}")

def on_subscribe(client: mqtt_client):
	logger.info( f"Successfully connect {historian_client} to Topic {topic} with QOS {qos} ")


def on_message(client, userdata, msg):
	logger.info(
			"{"
			f"Client: {client},"
			f"Userdata: {userdata},"
			f"message: {msg},"
			"}" 
	)
	timestamp = datetime.datetime.now()


# create historian mqtt client
historian_client = mqtt_client.Client()

# Assign event callbacks
historian_client.on_connect = on_connect
historian_client.on_subscribe = on_subscribe
historian_client.on_message = on_message

# Connect
historian_client.connect(broker, int(port), int(keep_alive))

# Continue the network loop
historian_client.loop_forever()


