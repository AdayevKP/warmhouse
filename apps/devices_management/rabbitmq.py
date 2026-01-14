import json
import logging
import os

import aio_pika
from aio_pika import DeliveryMode, Message

logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "device-exchange")


class RabbitMQClient:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        """Initialize RabbitMQ connection"""
        try:
            self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
            self.channel = await self.connection.channel()
            self.exchange = await self.channel.declare_exchange(
                RABBITMQ_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def publish_event(self, routing_key: str, message_data: dict):
        """Publish an event to RabbitMQ"""
        if not self.connection or self.connection.is_closed:
            await self.connect()

        try:
            message_body = json.dumps(message_data, default=str).encode()
            message = Message(
                message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )

            await self.exchange.publish(message, routing_key=routing_key)
            logger.info(f"Published event to {routing_key}: {message_data}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Closed RabbitMQ connection")


rabbitmq_client = RabbitMQClient()
__all__ = ["rabbitmq_client"]