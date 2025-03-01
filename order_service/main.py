from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime
import pika
import json

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
    connection = pika.BlockingConnection(pika.URLParameters(BROKER_URL))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(message))
    connection.close()

@app.post("/create_order")
def create_order(order: Order):
    order_id = str(uuid.uuid4())
    db = SessionLocal()
    new_order = OrderModel(
        id=order_id,
        customer_id=order.customer_id,
        items=json.dumps(order.items),
        total_amount=order.total_amount,
        status="Created",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_order)
    db.commit()
    db.close()

    # Publish notification and payment messages
    publish_to_queue("notification_queue", {"order_id": order_id, "message": "Order created successfully"})
    publish_to_queue("payment_queue", {"order_id": order_id, "amount": order.total_amount})

    return {"order_id": order_id, "status": "Created"}
