import asyncio
import websockets
import os
import json
import httpx # Kütüphane yerine bunu kullanıyoruz

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
    async with httpx.AsyncClient() as client:
        # Kullanıcı listesini kütüphanesiz çekiyoruz
        res = await client.get(f"{URL}users?select=id,display_name,is_admin", headers=HEADERS)
        all_users = res.json()
        data = json.dumps({
            "type": "users",
            "all_users": all_users,
            "online_users": list(clients.values())
        })
        await asyncio.gather(*[ws.send(data) for ws in clients.keys()], return_exceptions=True)

async def handle(websocket):
    clients[websocket] = "Bilinmeyen"
    try:
        async for message in websocket:
            data = json.loads(message); m_type = data.get("type"); u_id = data.get("u")
            if m_type == "hello":
                clients[websocket] = u_id
                await broadcast_user_list()
            elif m_type == "msg":
                to = data.get("to", "all")
                # Mesajı kaydet
                async with httpx.AsyncClient() as client:
                    await client.post(f"{URL}messages", headers=HEADERS, json={
                        "sender": u_id, "receiver": to, "content": data.get("m")
                    })
                # Mesajı ilet
                if to == "all":
                    await asyncio.gather(*[ws.send(message) for ws in clients.keys()], return_exceptions=True)
                else:
                    for ws, name in clients.items():
                        if name == to or name == u_id: await ws.send(message)
            elif m_type == "register":
                # Admin kontrolü ve kayıt
                async with httpx.AsyncClient() as client:
                    check = await client.get(f"{URL}users?id=eq.{u_id}&is_admin=eq.true", headers=HEADERS)
                    if check.json():
                        await client.post(f"{URL}users", headers=HEADERS, json=data.get("new_user"))
                        await broadcast_user_list()
    except: pass
    finally:
        if websocket in clients: del clients[websocket]; await broadcast_user_list()

async def main():
    port = int(os.environ.get("PORT", 10000))
    async with websockets.serve(handle, "0.0.0.0", port): await asyncio.Future()

if __name__ == "__main__": asyncio.run(main())
