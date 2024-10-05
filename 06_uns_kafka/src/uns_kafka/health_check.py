import logging
import socket
import sys

import psutil

from uns_kafka.uns_kafka_config import KAFKAConfig, MQTTConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_process(name: str) -> bool:
    """Check if the process is running."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        cmdline = proc.info.get("cmdline", [])
        if any(name in " ".join(cmdline) for part in cmdline):
            return True
    return False


def check_existing_connection(host: str, port: int) -> bool:
    """Check if a connection to the specified host and port is already established."""
    try:
        # Resolve the hostname to an IP address
        remote_ip = socket.gethostbyname(host)

        # Get all active network connections
        connections = psutil.net_connections("inet")

        # Check if any connection matches the resolved IP and port
        for conn in connections:
            # cSpell:ignore raddr
            if conn.raddr and conn.raddr.port == port and conn.status == "ESTABLISHED":
                # Handle localhost
                if remote_ip == "127.0.0.1" or remote_ip == "::1":
                    return True
                elif conn.raddr.ip == remote_ip:
                    # Return True if we find a match
                    return True
        # Return False if no matching connection is found
        return False
    except Exception as ex:
        logger.error(ex)
        return False


def main():
    """Main health check function."""
    if not check_process("uns_kafka_mapper"):
        sys.exit(1)

    # Get MQTT configuration
    mqtt_host = MQTTConfig.host
    mqtt_port = MQTTConfig.port

    if not check_existing_connection(mqtt_host, mqtt_port):
        sys.exit(1)

    # Get Kafka configuration
    kafka_url: str = KAFKAConfig.kafka_config_map.get("bootstrap.servers")
    if "://" in kafka_url:
        kafka_url = kafka_url.split("://")[1]  # Remove the protocol
    host_port = kafka_url.split(":")
    kafka_host: str = host_port[0]
    kafka_port: str | None = host_port[1] if len(host_port) > 1 else ""  # Get port if available
    if not check_existing_connection(kafka_host, int(kafka_port)):
        sys.exit(1)
    logger.info("Health check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
