import aiohttp

from io import BytesIO
from PIL import Image


async def fetch_video_thumbnail(thumbnail_url: str) -> bytes | None:
    """Fetches the thumbnail of a video from the provided URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as response:
                response.raise_for_status()
                return await response.read()
    except aiohttp.ClientError as e:
        print(f"Error fetching thumbnail: {e}")
        return None


def convert_image_to_jpeg(image_data: bytes) -> BytesIO | None:
    """Converts an image in bytes to JPEG format."""
    try:
        image = Image.open(BytesIO(image_data))
        image = image.convert("RGB")
        new_image = BytesIO()
        image.save(new_image, format="JPEG")
        new_image.seek(0)
        return new_image
    except Exception as e:
        print(f"Error processing image: {e}")
        return None
