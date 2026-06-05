import asyncio
import json
import os
import httpx
import websockets

# ═══════════════════════════════════════════════════════════════════
# SUPABASE BAĞLANTI AYARLARI (Client ile Birebir Eşleşmeli)
# ═══════════════════════════════════════════════════════════════════
# Yeni eklediğimiz 'bio' sütununu da select sorgusuna dahil ettik!
SUPABASE_URL = "https://kpspzbtxlefxjfjoihka.supabase.co/rest/v1/users?select=id,display_name,bio,is_admin"
KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
       "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtwc3B6YnR4bGVmeGpmam9paGthIiwi"
       "cm9sZSI6ImFub24iLCJpYXQiOjE3Nzg0MjY1MTMsImV4cCI6MjA5NDAwMjUxM30."
       "AS-uUbX0FGmNgZS4LmuvXmi_ybntc7_CHPyl0c9OP3w")
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}"
}

# ── Global Durum Yönetimi ──
CONNECTED_USERS = {}  # Anlık aktif bağlantılar -> {user_id: websocket_inst}

async def fetch_supabase_users():
    """Supabase'den en güncel kullanıcı verilerini (biyografiler dahil) çeker."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(SUPABASE_URL, headers=HEADERS)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"[-] Supabase verisi çekilirken hata oluştu: {e}")
    return []

async def broadcast_user_list():
    """Aktif olan ve olmayan tüm kullanıcıların durumunu herkese anlık duyurur."""
    if not CONNECTED_USERS:
        return
    
    # Veritabanındaki güncel listeyi (ve yeni Bio'ları) alıyoruz
    all_users = await fetch_supabase_users()
    online_users = list(CONNECTED_USERS.keys())
    
    payload = json.dumps({
        "type": "users",
        "all_users": all_users,
        "online_users": online_users
    })
    
    # Odadaki herkese dağıt (Broadcast)
    clients = list(CONNECTED_USERS.values())
    if clients:
        await asyncio.gather(*[client.send(payload) for client in clients], return_exceptions=True)

async def handle_client(websocket, path):
    """Her bir kankanın sunucuyla olan anlık ilişkisini yöneten ana fonksiyon."""
    user_id = None
    try:
        async for raw_message in websocket:
            data = json.loads(raw_message)
            msg_type = data.get("type")

            # 1. KANCA ATMA (Giriş Bildirimi)
            if msg_type == "hello":
                user_id = data.get("u")
                if user_id:
                    CONNECTED_USERS[user_id] = websocket
                    print(f"[+] {user_id} Kankacord'a bağlandı.")
                    await broadcast_user_list()

            # 2. MESAJ TRAFİĞİ (Genel Sohbet veya DM)
            elif msg_type == "msg":
                sender = data.get("u")
                msg_text = data.get("m")
                target = data.get("to", "all")

                relay_payload = json.dumps({
                    "type": "msg",
                    "u": sender,
                    "m": msg_text,
                    "to": target
                })

                if target == "all":
                    # Genel Sohbet: İstisnasız herkese gönder
                    clients = list(CONNECTED_USERS.values())
                    if clients:
                        await asyncio.gather(*[client.send(relay_payload) for client in clients], return_exceptions=True)
                else:
                    # Özel Mesaj (DM): Sadece hedef kankaya ve mesajı yazan adama gönder
                    targets = []
                    if target in CONNECTED_USERS:
                        targets.append(CONNECTED_USERS[target])
                    if sender in CONNECTED_USERS and sender != target:
                        targets.append(CONNECTED_USERS[sender])
                    
                    if targets:
                        await asyncio.gather(*[t.send(relay_payload) for t in targets], return_exceptions=True)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Kopma durumunda listeden temizle
        if user_id in CONNECTED_USERS:
            del CONNECTED_USERS[user_id]
            print(f"[-] {user_id} Kankacord'dan ayrıldı.")
            await broadcast_user_list()

async def periodic_sync():
    """
    Kankalar uygulamadan çıkmadan ayarlardan Bio veya İsim değiştirdiğinde,
    diğer agaların ekranına otomatik yansıması için 10 saniyede bir tetiklenir.
    """
    while True:
        await asyncio.sleep(10)
        await broadcast_user_list()

async def main():
    # Render, uygulamaları çalıştırırken otomatik port atar. Bunu os.environ ile yakalamak şarttır.
    port = int(os.environ.get("PORT", 8765))
    
    # Arka plan senkronizasyon görevini başlat
    asyncio.create_task(periodic_sync())
    
    print(f"[*] Kankacord Sunucusu 0.0.0.0:{port} üzerinden ayağa kalkıyor...")
    async with websockets.serve(handle_client, "0.0.0.0", port):
        await asyncio.Future()  # Sunucunun sürekli açık kalmasını sağlar

if __name__ == "__main__":
    asyncio.run(main())
