import asyncio
import websockets
import os
import json

# Bağlı kullanıcıları tut: {websocket: username}
clients = {}

async def broadcast_users():
    if clients:
        user_list = list(clients.values())
        data = json.dumps({"type": "users", "list": user_list})
        await asyncio.gather(*[ws.send(data) for ws in clients])

async def handle_connection(websocket):
    clients[websocket] = "Bilinmeyen"
    try:
        async for message in websocket:
            data = json.loads(message)
            user = data.get("u")
            msg_type = data.get("type", "msg")
            
            if msg_type == "hello":
                clients[websocket] = user
                await broadcast_users()
            else:
                to_user = data.get("to", "all")
                if to_user == "all":
                    # Herkese gönder
                    await asyncio.gather(*[ws.send(message) for ws in clients])
                else:
                    # Sadece alıcıya ve gönderene gönder
                    for ws, name in clients.items():
                        if name == to_user or name == user:
                            await ws.send(message)
                            
    except:
        pass
    finally:
        if websocket in clients:
            del clients[websocket]
            await broadcast_users()

async def main():
    port = int(os.environ.get("PORT", 10000))
    async with websockets.serve(handle_connection, "0.0.0.0", port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main()) 
