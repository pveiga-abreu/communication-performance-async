import json
import threading
import time
import uuid
import queue
from datetime import datetime

import pika
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:postgres@postgres:5432/orders_db"
BROKER_URL = "amqps://aykjquto:UWfBfBZOhl11xc2PpnkNyhk0dcBQ7g0D@leopard.lmq.cloudamqp.com/aykjquto"
POOL_SIZE = 8

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


class Order(BaseModel):
    customer_id: str
    items: list
    total_amount: float


# Connection Pool for Blocking Connections
class BlockingConnectionPool:
    def __init__(self, url: str, pool_size: int = 8):
        self.url = url
        self.pool_size = pool_size
        self.pool = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            connection = pika.BlockingConnection(pika.URLParameters(url))
            self.pool.put(connection)

    def acquire(self):
        return self.pool.get()

    def release(self, connection):
        self.pool.put(connection)


Base.metadata.create_all(bind=engine)

# Create a connection pool for the Message Broker
publisher_pool = BlockingConnectionPool(BROKER_URL, pool_size=POOL_SIZE)

# FastAPI app
app = FastAPI()

Instrumentator().instrument(app).expose(app)


# Health check
@app.get("/health")
async def health_check():
    return {"status": "OK"}


def publish_to_queue(queue_name, message):
    """Publishes messages to Message Broker"""
    retries = 5
    while retries > 0:
        try:
            connection = publisher_pool.acquire()
            channel = connection.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_publish(
                exchange="", routing_key=queue_name, body=json.dumps(message)
            )
            publisher_pool.release(connection)
            print(f"Message published to {queue_name}: {message}")
            break
        except pika.exceptions.AMQPConnectionError:
            print(
                f"[Publish] Failed to connect to Message Broker, retrying... ({retries} attempts left)"
            )
            time.sleep(2)
            retries -= 1


# Order routes
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

    # Send events to Message Broker
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
    """Starts Message Broker consumer in a separate thread"""
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
            print("[Consume] Failed to connect to Message Broker, retrying...")
            time.sleep(2)
            retries -= 1


@app.on_event("startup")
def startup_event():
    """Starts Message Broker consumer in a separate thread"""
    for _ in range(8):
        thread = threading.Thread(target=start_consumer, daemon=True)
        thread.start()
