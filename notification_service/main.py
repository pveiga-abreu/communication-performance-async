import json
import threading
from time import sleep

import pika
from fastapi import FastAPI

BROKER_URL = "amqps://aykjquto:UWfBfBZOhl11xc2PpnkNyhk0dcBQ7g0D@leopard.lmq.cloudamqp.com/aykjquto"

app = FastAPI()


def process_notification(order_id, message):
    """Processes and logs the notification message."""
    # Allocate a list (~512 KB) for simulating data processing
    data = [b'x' * 1024 * 512 for _ in range(1)]
    # Simulating a processing time
    sleep(0.5)
    # Clean memory
    del data

    print(f"Notification for Order {order_id}: {message}")


def notification_callback(ch, method, properties, body):
    """Callback function to process notification messages from the queue."""
    data = json.loads(body)
    order_id = data.get("order_id")
    message = data.get("message", "No message provided")

    print(f"Received notification for Order {order_id}")

    process_notification(order_id, message)

    # Acknowledge message processing
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consumer():
    """Starts the Message Broker consumer to listen for notification messages."""
    retries = 5
    while retries > 0:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
            channel = connection.channel()
            channel.queue_declare(queue="notification_queue", durable=True)
            channel.basic_consume(
                queue="notification_queue", on_message_callback=notification_callback
            )
            print("Notification consumer started and waiting for messages...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print(
                f"Failed to connect to Message Broker, retrying... ({retries} attempts left)"
            )
            sleep(2)
            retries -= 1


@app.on_event("startup")
def startup_event():
    """Runs the Message Broker consumer in a separate thread when the application starts."""
    for _ in range(10):
        thread = threading.Thread(target=start_consumer, daemon=True)
        thread.start()
