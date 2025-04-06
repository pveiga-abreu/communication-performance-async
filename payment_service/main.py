import json
import threading
from time import sleep

import pika
from fastapi import FastAPI

BROKER_URL = "amqps://aykjquto:UWfBfBZOhl11xc2PpnkNyhk0dcBQ7g0D@leopard.lmq.cloudamqp.com/aykjquto"

app = FastAPI()


def publish_to_queue(queue_name, message):
    """Publishes messages to Message Broker queues."""
    retries = 5
    while retries > 0:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
            channel = connection.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_publish(
                exchange="", routing_key=queue_name, body=json.dumps(message)
            )
            connection.close()
            print(f"Message published to {queue_name}: {message}")
            break
        except pika.exceptions.AMQPConnectionError:
            print(
                f"Failed to connect to Message Broker, retrying... ({retries} attempts left)"
            )
            sleep(2)
            retries -= 1


def process_payment(order_id, amount):
    """Processes the payment and determines the status."""

    # Simulating a processing time
    sleep(0.5)

    if amount > 1000:
        status = "Failed"
        message = f"Payment failed for Order {order_id}: amount exceeds limit."
    else:
        status = "Paid"
        message = f"Payment processed successfully for Order {order_id}."

    print(f"Payment status for Order {order_id}: {status}")

    # Publish the payment status for order service to update the database
    publish_to_queue("payment_processed", {"order_id": order_id, "status": status})

    # Send notification about payment status
    publish_to_queue("notification_queue", {"order_id": order_id, "message": message})


def payment_callback(ch, method, properties, body):
    """Callback function to process payment messages from the queue."""
    data = json.loads(body)
    order_id = data["order_id"]
    amount = data["amount"]

    print(f"Received payment request for Order {order_id} with amount: {amount}")

    process_payment(order_id, amount)

    # Acknowledge message processing
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consumer():
    """Starts the Message Broker consumer to listen for payment requests."""
    retries = 5
    while retries > 0:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
            channel = connection.channel()
            channel.queue_declare(queue="payment_queue", durable=True)
            channel.basic_consume(
                queue="payment_queue", on_message_callback=payment_callback
            )
            print("Payment consumer started and waiting for messages...")
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
