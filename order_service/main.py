import json
import threading
import time
import uuid
from datetime import datetime

import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/orders_db"
BROKER_URL = "amqp://guest:guest@rabbitmq:5672/"

# Database setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    items = Column(String)
    total_amount = Column(Float)
    status = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()


class Order(BaseModel):
    customer_id: str
    items: list
    total_amount: float


def publish_to_queue(queue_name, message):
    """Publishes messages to RabbitMQ"""
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
            break
        except pika.exceptions.AMQPConnectionError:
            print("Failed to connect to RabbitMQ, retrying...")
            time.sleep(2)
            retries -= 1


@app.post("/create_order")
def create_order(order: Order):
    """Creates an order and sends messages to queues"""
    order_id = str(uuid.uuid4())
    db = SessionLocal()
    new_order = OrderModel(
        id=order_id,
        customer_id=order.customer_id,
        items=json.dumps(order.items),
        total_amount=order.total_amount,
        status="Created",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_order)
    db.commit()
    db.close()

    # Send events to RabbitMQ
    publish_to_queue(
        "notification_queue",
        {"order_id": order_id, "message": "Order created successfully"},
    )
    publish_to_queue(
        "payment_queue", {"order_id": order_id, "amount": order.total_amount}
    )

    return {"order_id": order_id, "status": "Created"}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    db = SessionLocal()
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    db.close()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def update_order_status(order_id, status):
    """Updates order status in the database"""
    db = SessionLocal()
    order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if order:
        order.status = status
        db.commit()
    db.close()


def payment_callback(ch, method, properties, body):
    """Callback to update orders after payment"""
    data = json.loads(body)
    print(f"Received payment for order {data['order_id']}, status: {data['status']}")
    update_order_status(data["order_id"], data["status"])
    ch.basic_ack(delivery_tag=method.delivery_tag)  # Acknowledge message


def start_consumer():
    """Starts RabbitMQ consumer in a separate thread"""
    retries = 5
    while retries > 0:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
            channel = connection.channel()
            channel.queue_declare(queue="payment_processed", durable=True)
            channel.basic_consume(
                queue="payment_processed", on_message_callback=payment_callback
            )
            print("Payment consumer started...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            print("Failed to connect to RabbitMQ, retrying...")
            time.sleep(2)
            retries -= 1


@app.on_event("startup")
def startup_event():
    """Starts RabbitMQ consumer in a separate thread"""
    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()
