import asyncio
import websockets
import os
import json
from supabase import create_client

# --- SUPABASE BAĞLANTISI ---
SUPABASE_URL = "https://kpspzbtxlefxjfjoihka.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtwc3B6YnR4bGVmeGpmam9paGthIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg0MjY1MTMsImV4cCI6MjA5NDAwMjUxM30.AS-uUbX0FGmNgZS4LmuvXmi_ybntc7_CHPyl0c9OP3w"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

clients = {} # {websocket: user_id}

async def broadcast_user_list():
    if clients:
        try:
            response = supabase.table("users").select("id, display_name, is_admin").execute()
            all_users = response.data
            online_ids = list(clients.values())
            data = json.dumps({
                "type": "users",
                "all_users": all_users,
                "online_users": online_ids
            })
            if clients:
                await asyncio.gather(*[ws.send(data) for ws in clients.keys()], return_exceptions=True)
        except Exception as e:
            print(f"Liste Hatası: {e}")

async def handle(websocket):
    clients[websocket] = "Bilinmeyen"
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            u_id = data.get("u")

            if msg_type == "hello":
                clients[websocket] = u_id
                await broadcast_user_list()
            
            elif msg_type == "msg":
                to = data.get("to", "all")
                # Mesajı Buluta Kaydet
                supabase.table("messages").insert({
                    "sender": u_id,
                    "receiver": to,
                    "content": data.get("m")
                }).execute()
                
                # Mesajı İlet
                if to == "all":
                    await asyncio.gather(*[ws.send(message) for ws in clients.keys()], return_exceptions=True)
                else:
                    for ws, name in clients.items():
                        if name == to or name == u_id:
                            await ws.send(message)
                            
            elif msg_type == "register":
                admin_check = supabase.table("users").select("is_admin").eq("id", u_id).execute()
                if admin_check.data and admin_check.data[0]["is_admin"]:
                    supabase.table("users").insert(data.get("new_user")).execute()
                    await broadcast_user_list()

    except Exception as e: print(f"Hata: {e}")
    finally:
        if websocket in clients:
            del clients[websocket]
            await broadcast_user_list()

async def main():
    port = int(os.environ.get("PORT", 10000))
    async with websockets.serve(handle, "0.0.0.0", port, ping_interval=20, ping_timeout=20):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
