import asyncio
import websockets
import os
import json

# {websocket: username} eşleşmesi
clients = {}

async def broadcast_user_list():
    if clients:
        # Boş olmayan kullanıcı isimlerini topla
        names = [n for n in clients.values() if n and n != "Bilinmeyen"]
        data = json.dumps({"type": "users", "list": names})
        # Bağlı olan herkese güncel listeyi gönder
        await asyncio.gather(*[ws.send(data) for ws in clients])

async def handle(websocket):
    clients[websocket] = "Bilinmeyen"
    try:
        async for message in websocket:
            data = json.loads(message)
            u = data.get("u", "Bilinmeyen")
            
            if data.get("type") == "hello":
                clients[websocket] = u
                await broadcast_user_list()
            else:
                to = data.get("to", "all")
                if to == "all":
                    # Genel Mesaj: Herkese yayınla
                    await asyncio.gather(*[ws.send(message) for ws in clients])
                else:
                    # Özel Mesaj: Sadece gönderene ve alıcıya ilet
                    for ws, name in clients.items():
                        if name == to or name == u:
                            await ws.send(message)
    except:
        pass
    finally:
        if websocket in clients:
            del clients[websocket]
            await broadcast_user_list()

async def main():
    port = int(os.environ.get("PORT", 10000))
    async with websockets.serve(handle, "0.0.0.0", port):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
