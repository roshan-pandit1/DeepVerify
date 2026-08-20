import asyncio
from telegram_bot import handle_update

mock_update = {
    "message": {
        "chat": {"id": "8872223173"},
        "text": "https://www.w3schools.com/html/mov_bbb.mp4"
    }
}

asyncio.run(handle_update(mock_update))
