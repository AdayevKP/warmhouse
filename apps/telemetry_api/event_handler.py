import asyncio
import json
import logging
import os

import aio_pika
from pydantic import BaseModel
import asyncpg


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "telemetry")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "device-exchange")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "device-events-queue")


pool = None


class Device(BaseModel):
    id: int
    name: str
    type: str
    description: str | None = None
    location: str | None = None
    connection_info: dict | None = None
    tags: list[str] | None = None
    created_at: str | None = None

class DeviceDeleted(BaseModel):
    id: int
    deletedAt: str | None = None

async def get_db_connection():
    """Create and return a database connection pool"""
    return await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        min_size=1,
        max_size=10,
    )

async def save_device_to_db(device_data: Device, event_type: str):
    """Save device information to the database"""
    assert pool is not None
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO devices (
                    id, name, type, description, location, 
                    connection_info, tags, created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, NOW(), NOW()
                )
                ON CONFLICT (id) 
                DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    description = EXCLUDED.description,
                    location = EXCLUDED.location,
                    connection_info = EXCLUDED.connection_info,
                    tags = EXCLUDED.tags,
                    updated_at = NOW()
                """,
                device_data.id,
                device_data.name,
                device_data.type,
                device_data.description,
                device_data.location,
                json.dumps(device_data.connection_info or {}),
                device_data.tags or [],
            )
            logger.info(f"Device {device_data.id} saved to database")
    except Exception as e:
        logger.error(f"Error saving device to database: {e}")
        raise


async def delete_device_from_db(device_id: int):
    """Delete a device from the database"""
    assert pool is not None
    try:
        async with pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM devices WHERE id = $1",
                device_id
            )
            logger.info(f"Device {device_id} deleted from database")
    except Exception as e:
        logger.error(f"Error deleting device from database: {e}")
        raise

async def process_message(message: aio_pika.IncomingMessage):
    """Process incoming RabbitMQ messages"""
    try:
        message_data = json.loads(message.body.decode())
        logger.info(f"Received message: {message_data}")
        
        assert message.routing_key
        logger.info(f"Routing key: {message.routing_key}")
        event_type = message.routing_key.split(".")[-1]
        if event_type == "created":
            event_type = "deviceCreated"
        elif event_type == "updated":
            event_type = "deviceUpdated"
        elif event_type == "deleted":
            event_type = "deviceDeleted"
        
        if event_type in ["deviceCreated", "deviceUpdated"]:
            device = Device(**message_data)
            await save_device_to_db(device, event_type)
        elif event_type == "deviceDeleted":
            device_deleted = DeviceDeleted(**message_data)
            await delete_device_from_db(device_deleted.id)
        
        await message.ack()
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.nack(requeue=False)

async def start_event_consumer():
    """Start the RabbitMQ event consumer"""
    try:
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        channel = await connection.channel()
        
        exchange = await channel.declare_exchange(
            RABBITMQ_EXCHANGE, 
            aio_pika.ExchangeType.TOPIC, 
            durable=True
        )
        
        queue = await channel.declare_queue(RABBITMQ_QUEUE, durable=True)
        await queue.bind(exchange, routing_key="devices.*")
        await queue.consume(process_message)
        logger.info("Event consumer started successfully")
        return connection
        
    except Exception as e:
        logger.error(f"Error starting event consumer: {e}")
        raise

async def main():
    global pool
    pool = await get_db_connection()
    connection = await start_event_consumer()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await pool.close()
        await connection.close()

if __name__ == "__main__":
    asyncio.run(main())