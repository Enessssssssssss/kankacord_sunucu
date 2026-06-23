import asyncio
import websockets
import os
import json
import httpx

# --- SUPABASE AYARLARI ---
URL = "https://kpspzbtxlefxjfjoihka.supabase.co/rest/v1/"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtwc3B6YnR4bGVmeGpmam9paGthIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg0MjY1MTMsImV4cCI6MjA5NDAwMjUxM30.AS-uUbX0FGmNgZS4LmuvXmi_ybntc7_CHPyl0c9OP3w"

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

clients = {}

async def broadcast_user_list():
    if not clients: return
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{URL}users?select=id,display_name,is_admin", headers=HEADERS, timeout=5.0)
            all_users = res.json()
            data = json.dumps({
                "type": "users",
                "all_users": all_users,
                "online_users": list(clients.values())
            })
            await asyncio.gather(*[ws.send(data) for ws in clients.keys()], return_exceptions=True)
    except Exception as e:
        print(f"[Sistem Hatası] Kullanıcı listesi dağıtılamadı: {e}")

async def save_message_to_db(sender, receiver, content):
    """Mesajı arka planda Supabase'e kaydeder, ana sohbet akışını bloklamaz."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{URL}messages", headers=HEADERS, json={
                "sender": sender, "receiver": receiver, "content": content
            }, timeout=5.0)
    except Exception as e:
        print(f"[DB Hatası] Mesaj veritabanına yazılamadı: {e}")

async def handle(websocket):
    clients[websocket] = "Bilinmeyen"
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
                
            m_type = data.get("type")
            u_id = data.get("u")
            
            # --- 1. PING / PONG ENTEGRASYONU ---
            if m_type == "ping":
                # Arayüzün 5 saniyelik bombasını imha etmek için anında pong dönüyoruz
                await websocket.send(json.dumps({"type": "pong"}))
                continue # DB veya broadcast işlemlerine girmeden döngünün başına dön
            
            # --- 2. YAZIYOR... (TYPING) SİNYAL DAĞITIMI ---
            elif m_type == "typing":
                to = data.get("to", "all")
                # Performans için bu paketi DB'ye asla kaydetmiyoruz!
                # Sadece yazan KİŞİ HARİÇ (ws != websocket) hedefteki kankalara fırlatıyoruz
                if to == "all":
                    await asyncio.gather(*[
                        ws.send(message) for ws in clients.keys() 
                        if ws != websocket
                    ], return_exceptions=True)
                else:
                    await asyncio.gather(*[
                        ws.send(message) for ws, name in clients.items() 
                        if name == to and ws != websocket
                    ], return_exceptions=True)
                continue
                
            elif m_type == "hello":
                clients[websocket] = u_id
                await broadcast_user_list()
                
            elif m_type == "msg":
                to = data.get("to", "all")
                content = data.get("m")
                
                # ÖNCE MESAJI İLET (Sıfır Gecikme / Real-time)
                if to == "all":
                    await asyncio.gather(*[ws.send(message) for ws in clients.keys()], return_exceptions=True)
                else:
                    await asyncio.gather(*[
                        ws.send(message) for ws, name in clients.items() 
                        if name == to or name == u_id
                    ], return_exceptions=True)
                
                # SONRA ARKA PLAN GÖREVİ OLARAK DB'YE YAZ (Asenkron)
                asyncio.create_task(save_message_to_db(u_id, to, content))
                            
            elif m_type == "register":
                try:
                    async with httpx.AsyncClient() as client:
                        check = await client.get(f"{URL}users?id=eq.{u_id}&is_admin=eq.true", headers=HEADERS, timeout=5.0)
                        if check.json():
                            await client.post(f"{URL}users", headers=HEADERS, json=data.get("new_user"), timeout=5.0)
                            await broadcast_user_list()
                except Exception as e:
                    print(f"[Kayıt Hatası] Admin/Kayıt işlemi başarısız: {e}")
                    
    except websockets.exceptions.ConnectionClosed:
        pass 
    except Exception as e:
        print(f"[Bağlantı Hatası] Beklenmedik soket hatası: {e}")
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
