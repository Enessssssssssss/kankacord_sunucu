import asyncio
import websockets

# Bağlı olan tüm arkadaşların listesi
clients = set()

async def handle_connection(websocket):
    # Yeni biri bağlandığında listeye ekle
    clients.add(websocket)
    print("Yeni bir arkadaş bağlandı!")
    
    try:
        async for message in websocket:
            print(f"Mesaj geldi: {message}")
            # Gelen mesajı, bağlı olan HERKESE gönder (Broadcast)
            if clients:
                # asyncio.wait ile tüm arkadaşlarına aynı anda yolla
                await asyncio.wait([client.send(message) for client in clients])
    except:
        pass
    finally:
        # Bağlantı koptuğunda listeden sil
        clients.remove(websocket)
        print("Bir arkadaş ayrıldı.")

async def main():
    # Render'ın bize verdiği portu kullanacağız (Varsayılan 10000)
    import os
    port = int(os.environ.get("PORT", 10000))
    
    # Sunucuyu tüm iplere (0.0.0.0) açıyoruz
    async with websockets.serve(handle_connection, "0.0.0.0", port):
        print(f"Kankacord Sunucusu {port} portunda çalışıyor...")
        await asyncio.Future()  # Sunucunun sürekli açık kalmasını sağlar

if __name__ == "__main__":
    asyncio.run(main())