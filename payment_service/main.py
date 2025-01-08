from fastapi import FastAPI
import pika
import json

BROKER_URL = "amqp://guest:guest@rabbitmq:5672/"

app = FastAPI()

def publish_to_queue(queue_name, message):
    connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(message))
    connection.close()

def callback(ch, method, properties, body):
    data = json.loads(body)
    order_id = data["order_id"]
    amount = data["amount"]

    if amount > 1000:
        status = "Failed"
        message = f"Payment failed for Order {order_id}: amount exceeds limit."
    else:
        status = "Paid"
        message = f"Payment processed successfully for Order {order_id}."

    # Publish payment status to notification queue
    publish_to_queue("notification_queue", {"order_id": order_id, "message": message, "status": status})
    ch.basic_ack(delivery_tag=method.delivery_tag)

@app.on_event("startup")
def start_consumer():
    connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
    channel = connection.channel()
    channel.queue_declare(queue="payment_queue", durable=True)
    channel.basic_consume(queue="payment_queue", on_message_callback=callback)
    channel.start_consuming()
