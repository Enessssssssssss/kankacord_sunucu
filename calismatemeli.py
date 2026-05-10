import asyncio
import threading
import json
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
import websockets

# --- DISCORD RENK PALETİ ---
DISCORD_DARK = (0.21, 0.22, 0.25, 1)    # #36393f
DISCORD_SIDE = (0.18, 0.19, 0.21, 1)    # #2f3136
DISCORD_BLURPLE = (0.45, 0.54, 0.85, 1) # #7289da
TEXT_COLOR = (0.9, 0.9, 0.9, 1)

class MessageBubble(BoxLayout):
    """Discord stili mesaj balonu"""
    def __init__(self, user, msg, is_me=False, **kwargs):
        super().__init__(orientation='vertical', size_hint_y=None, padding=10, **kwargs)
        self.height = 80
        
        # Kullanıcı Adı (Bold gibi görünsün)
        user_label = Label(text=f"[b]{user}[/b]", markup=True, color=DISCORD_BLURPLE, 
                           size_hint_y=None, height=20, halign="left")
        user_label.bind(size=user_label.setter('text_size'))
        
        # Mesaj İçeriği
        msg_label = Label(text=msg, color=TEXT_COLOR, size_hint_y=None, height=40, halign="left")
        msg_label.bind(size=msg_label.setter('text_size'))
        
        self.add_widget(user_label)
        self.add_widget(msg_label)

class KankacordApp(App):
    def build(self):
        self.username = "Kanka_" + str(hash(Window.width))[:4] # Geçici isim
        Window.clearcolor = DISCORD_DARK
        
        # Ana Düzen
        self.main_layout = BoxLayout(orientation='vertical', padding=5)
        
        # Üst Bilgi Barı
        status_bar = Label(text=f"Kankacord - Giriş Yapıldı: {self.username}", 
                           size_hint_y=0.05, color=DISCORD_BLURPLE)
        self.main_layout.add_widget(status_bar)
        
        # Mesaj Alanı
        self.scroll = ScrollView(size_hint=(1, 0.85))
        self.chat_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=10, padding=10)
        self.chat_box.bind(minimum_height=self.chat_box.setter('height'))
        self.scroll.add_widget(self.chat_box)
        self.main_layout.add_widget(self.scroll)
        
        # Giriş Alanı
        input_layout = BoxLayout(size_hint_y=0.1, spacing=5)
        self.msg_input = TextInput(hint_text="Mesaj gönder...", multiline=False,
                                   background_color=(0.15, 0.16, 0.18, 1),
                                   foreground_color=(1, 1, 1, 1), cursor_color=(1, 1, 1, 1))
        
        send_btn = Button(text="Pusuya At", size_hint_x=0.2, 
                          background_normal='', background_color=DISCORD_BLURPLE)
        send_btn.bind(on_release=self.send_message)
        
        input_layout.add_widget(self.msg_input)
        input_layout.add_widget(send_btn)
        self.main_layout.add_widget(input_layout)
        
        # Network Döngüsü
        self.ws = None
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_async_loop, daemon=True).start()
        
        return self.main_layout

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_to_kankacord())

    async def connect_to_kankacord(self):
        uri = "wss://kankacord.onrender.com"
        try:
            async with websockets.connect(uri) as websocket:
                self.ws = websocket
                Clock.schedule_once(lambda dt: self.ui_add_message("SİSTEM", "Bağlantı başarılı!"))
                async for raw_data in websocket:
                    data = json.loads(raw_data)
                    Clock.schedule_once(lambda dt, d=data: self.ui_add_message(d['u'], d['m']))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.ui_add_message("HATA", str(e)))

    def send_message(self, instance):
        msg = self.msg_input.text
        if msg and self.ws:
            payload = json.dumps({"u": self.username, "m": msg})
            asyncio.run_coroutine_threadsafe(self.ws.send(payload), self.loop)
            self.msg_input.text = ""

    def ui_add_message(self, user, msg):
        bubble = MessageBubble(user=user, msg=msg)
        self.chat_box.add_widget(bubble)
        self.scroll.scroll_y = 0

if __name__ == "__main__":
    KankacordApp().run()