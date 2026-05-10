import asyncio
import websockets
import os
import json

# Bağlı olan tüm cihazları tutan küme
clients = set()

async def handle_connection(websocket):
    clients.add(websocket)
    print(f"Yeni cihaz bağlandı. Toplam: {len(clients)}")
    
    try:
        async for message in websocket:
            # Gelen JSON paketini doğrula ve herkese (broadcast) gönder
            # Mesaj zaten JSON formatında geldiği için direkt iletiyoruz
            if clients:
                # Gönderen dahil herkese mesajı fırlat
                await asyncio.gather(*[client.send(message) for client in clients])
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.remove(websocket)
        print(f"Cihaz ayrıldı. Kalan: {len(clients)}")

async def main():
    # Render'ın portunu yakala
    port = int(os.environ.get("PORT", 10000))
    async with websockets.serve(handle_connection, "0.0.0.0", port):
        print(f"Kankacord Merkezi {port} portunda tetikte!")
        await asyncio.Future()  # Sonsuz döngü

if __name__ == "__main__":
    asyncio.run(main())
