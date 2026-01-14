import os
import aiohttp


class SmartHomeClient:
    def __init__(self):
        self.base_url = os.getenv("SMART_HOME_URL", "http://localhost:8080")
        self.base_url += '/api/v1'

    async def create_sensor(self, sensor_data: dict) -> dict:
        """Create a new sensor in smart_home service"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/sensors", json=sensor_data
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def delete_sensor(self, sensor_id: int) -> dict:
        """Delete a sensor from smart_home service"""
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.base_url}/sensors/{sensor_id}"
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def update_sensor(self, sensor_id: int, sensor_data: dict) -> dict:
        """Update a sensor in smart_home service"""
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.base_url}/sensors/{sensor_id}", json=sensor_data
            ) as response:
                response.raise_for_status()
                return await response.json()
            

smart_home_client = SmartHomeClient()
__all__ = ["smart_home_client"]