from fastapi import FastAPI
import pika
import json

BROKER_URL = "amqp://guest:guest@rabbitmq:5672/"

app = FastAPI()

def callback(ch, method, properties, body):
    data = json.loads(body)
    order_id = data["order_id"]
    message = data["message"]
    print(f"Notification for Order {order_id}: {message}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

@app.on_event("startup")
def start_consumer():
    connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
    channel = connection.channel()
    channel.queue_declare(queue="notification_queue", durable=True)
    channel.basic_consume(queue="notification_queue", on_message_callback=callback)
    channel.start_consuming()
