import asyncio
import websockets
import os
import json

# Bağlı kullanıcıları ve soketlerini eşleştir: {websocket: username}
clients = {}

async def broadcast_user_list():
    """Bağlı olan tüm kullanıcılara güncel kullanıcı listesini gönderir."""
    if clients:
        # "Bilinmeyen" olmayan ve boş olmayan kullanıcı isimlerini filtrele
        user_names = [name for name in clients.values() if name and name != "Bilinmeyen"]
        user_list_packet = json.dumps({
            "type": "users",
            "list": user_names
        })
        
        # Listedeki her bir aktif bağlantıya paketi gönder
        if clients:
            await asyncio.gather(
                *[ws.send(user_list_packet) for ws in clients.keys()],
                return_exceptions=True
            )

async def handle_connection(websocket):
    """Her yeni bağlantıyı yöneten ana döngü."""
    # Yeni bağlantıyı geçici olarak "Bilinmeyen" olarak kaydet
    clients[websocket] = "Bilinmeyen"
    print(f" Yeni bir bağlantı sağlandı. Mevcut bağlantı sayısı: {len(clients)}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                user_name = data.get("u", "Bilinmeyen")
                msg_type = data.get("type", "msg")
                
                # 1. KİMLİK BİLDİRİMİ (Hello paketi)
                if msg_type == "hello":
                    clients[websocket] = user_name
                    print(f" Kanka katıldı: {user_name}")
                    await broadcast_user_list()
                
                # 2. MESAJLAŞMA (Genel veya DM)
                else:
                    target = data.get("to", "all")
                    
                    if target == "all":
                        # Genel Sohbet: Herkese yayınla
                        if clients:
                            await asyncio.gather(
                                *[ws.send(message) for ws in clients.keys()],
                                return_exceptions=True
                            )
                    else:
                        # Özel Mesaj (DM): Sadece gönderen ve alıcıya ilet
                        for ws, name in clients.items():
                            if name == target or name == user_name:
                                try:
                                    await ws.send(message)
                                except:
                                    pass
            
            except json.JSONDecodeError:
                print("Hatalı JSON paketi alındı.")
                
    except websockets.exceptions.ConnectionClosed:
        print("Bir bağlantı kapandı.")
    finally:
        # Bağlantı koptuğunda temizlik yap
        if websocket in clients:
            left_user = clients[websocket]
            del clients[websocket]
            print(f" {left_user} ayrıldı. Kalan: {len(clients)}")
            await broadcast_user_list()

async def main():
    # Render'ın atadığı portu kullan, yoksa 10000 portunu aç
    port = int(os.environ.get("PORT", 10000))
    
    # ping_interval: Bağlantının canlı kalması için her 20 saniyede bir kontrol et
    async with websockets.serve(
        handle_connection, 
        "0.0.0.0", 
        port,
        ping_interval=20,
        ping_timeout=20
    ):
        print(f"--- Kankacord Sunucusu {port} Portunda Tetikte ---")
        await asyncio.Future()  # Sunucuyu sonsuz döngüde tut

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Sunucu kapatılıyor...")
