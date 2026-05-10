import asyncio
import json
import threading
import time
from collections import defaultdict, deque

import websockets
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.utils import escape_markup

# Klavye ayarı: Yazarken ekran yukarı kaysın
Window.softinput_mode = 'below_target'

# --- AYARLAR ---
WS_URL = "wss://kankacord.onrender.com"
BG = (0.12, 0.13, 0.15, 1)
SIDEBAR = (0.18, 0.19, 0.21, 1)
CHAT_BG = (0.21, 0.22, 0.25, 1)
BLURPLE = (0.35, 0.40, 0.90, 1)
DM_PURPLE = (0.50, 0.20, 0.70, 1)
TEXT = (0.95, 0.95, 0.95, 1)
INPUT_BG = (0.15, 0.16, 0.18, 1)

# --- UI BİLEŞENLERİ ---
class Panel(BoxLayout):
    def __init__(self, bg_color, radius=0, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self.update_rect, size=self.update_rect)
    def update_rect(self, *args): self.rect.pos, self.rect.size = self.pos, self.size

class RoundedButton(Button):
    def __init__(self, bg_color, radius=10, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0,0,0,0)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self.update_rect, size=self.update_rect)
    def update_rect(self, *args): self.rect.pos, self.rect.size = self.pos, self.size

# --- EKRANLAR ---
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = Panel(BG, orientation="vertical", padding=dp(40), spacing=dp(20))
        layout.add_widget(Label(text="KANKACORD", font_size=dp(40), bold=True, color=BLURPLE))
        self.nick = TextInput(hint_text="İsminiz...", multiline=False, size_hint_y=None, height=dp(50), background_color=INPUT_BG, foreground_color=TEXT, padding=dp(12))
        layout.add_widget(self.nick)
        btn = RoundedButton(BLURPLE, text="Giriş", size_hint_y=None, height=dp(55))
        btn.bind(on_release=self.login)
        layout.add_widget(btn)
        self.add_widget(layout)

    def login(self, *args):
        val = self.nick.text.strip()
        if val:
            app = App.get_running_app()
            app.username = val
            app.sm.current = 'main'
            app.send_hello()

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.target = "all"
        self.msg_history = defaultdict(lambda: deque(maxlen=100))
        
        main_layout = BoxLayout(orientation="horizontal")
        
        # Sol Panel
        left_panel = Panel(SIDEBAR, orientation="vertical", size_hint_x=None, width=dp(200), padding=dp(10), spacing=dp(5))
        left_panel.add_widget(Label(text="KANKACORD", bold=True, size_hint_y=None, height=dp(40), color=BLURPLE))
        
        self.btn_genel = RoundedButton(BLURPLE, text="# Sohbet", size_hint_y=None, height=dp(45))
        self.btn_genel.bind(on_release=lambda x: self.switch_chat("all"))
        left_panel.add_widget(self.btn_genel)
        left_panel.add_widget(Widget(size_hint_y=None, height=dp(10)))
        
        self.user_list = BoxLayout(orientation="vertical", spacing=dp(5), size_hint_y=None)
        self.user_list.bind(minimum_height=self.user_list.setter('height'))
        scroll_users = ScrollView()
        scroll_users.add_widget(self.user_list)
        left_panel.add_widget(scroll_users)
        
        # Sağ Panel
        right_panel = Panel(CHAT_BG, orientation="vertical", padding=dp(10), spacing=dp(10))
        header = BoxLayout(size_hint_y=None, height=dp(40))
        self.chat_title = Label(text="# Sohbet", bold=True, halign="left")
        self.chat_title.bind(size=self.chat_title.setter('text_size'))
        self.status = Label(text="...", color=(0.8,0.2,0.2,1), size_hint_x=None, width=dp(100))
        header.add_widget(self.chat_title); header.add_widget(self.status)
        right_panel.add_widget(header)
        
        self.scroll_msg = ScrollView()
        self.box_msg = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10), padding=dp(5))
        self.box_msg.bind(minimum_height=self.box_msg.setter('height'))
        self.scroll_msg.add_widget(self.box_msg)
        right_panel.add_widget(self.scroll_msg)
        
        input_area = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(8))
        self.txt_input = TextInput(hint_text="Mesaj yaz kanka!", multiline=False, background_color=INPUT_BG, foreground_color=TEXT, padding=dp(12))
        self.txt_input.bind(on_text_validate=self.send)
        btn_send = RoundedButton(BLURPLE, text="Gönder", size_hint_x=None, width=dp(90))
        btn_send.bind(on_release=self.send)
        input_area.add_widget(self.txt_input); input_area.add_widget(btn_send)
        right_panel.add_widget(input_area)
        
        main_layout.add_widget(left_panel); main_layout.add_widget(right_panel)
        self.add_widget(main_layout)

    def switch_chat(self, target_name):
        self.target = target_name
        self.chat_title.text = "# Sohbet" if target_name == "all" else f"@{target_name} (Özel)"
        self.box_msg.clear_widgets()
        for u, m, is_dm in self.msg_history[target_name]:
            self.add_message_ui(u, m, is_dm)

    def update_users_ui(self, users):
        self.user_list.clear_widgets()
        for u in users:
            if u and u != self.app.username:
                b = RoundedButton(SIDEBAR, text=f"@{u}", size_hint_y=None, height=dp(40))
                b.bind(on_release=lambda x, name=u: self.switch_chat(name))
                self.user_list.add_widget(b)

    def add_message_ui(self, user, msg, is_dm):
        mine = (user == self.app.username)
        bubble = BoxLayout(orientation="vertical", size_hint=(0.8, None), padding=dp(10))
        bg_col = DM_PURPLE if is_dm else (BLURPLE if mine else SIDEBAR)
        with bubble.canvas.before:
            Color(*bg_col)
            bubble.rect = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[dp(12)])
        bubble.bind(pos=lambda s,p: setattr(s.rect, 'pos', p), size=lambda s,z: setattr(s.rect, 'size', z))
        
        lbl_u = Label(text=f"[b]{user}[/b]", markup=True, size_hint_y=None, height=dp(20), font_size=dp(12), halign="left")
        lbl_u.bind(size=lbl_u.setter('text_size'))
        lbl_m = Label(text=escape_markup(msg), size_hint_y=None, halign="left", valign="top")
        lbl_m.bind(width=lambda s,w: setattr(s, 'text_size', (w, None)), texture_size=lambda s,t: setattr(s, 'height', t[1]))
        
        bubble.add_widget(lbl_u); bubble.add_widget(lbl_m)
        bubble.height = lbl_m.height + dp(45)
        
        row = BoxLayout(size_hint_y=None, height=bubble.height, padding=dp(2))
        if mine:
            row.add_widget(Widget()); row.add_widget(bubble)
        else:
            row.add_widget(bubble); row.add_widget(Widget())
        self.box_msg.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self.scroll_msg, 'scroll_y', 0), 0.1)

    def send(self, *args):
        txt = self.txt_input.text.strip()
        if txt and self.app.connected:
            packet = {"u": self.app.username, "m": txt, "to": self.target}
            asyncio.run_coroutine_threadsafe(self.app.ws_send(packet), self.app.loop)
            self.txt_input.text = ""

# --- ANA APP ---
class KankacordApp(App):
    username = ""; connected = False; ws = None; loop = asyncio.new_event_loop()

    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(LoginScreen(name='login'))
        self.main_scr = MainScreen(name='main')
        self.sm.add_widget(self.main_scr)
        threading.Thread(target=self.start_networking, daemon=True).start()
        return self.sm

    def start_networking(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect_ws())

    async def connect_ws(self):
        while True:
            try:
                async with websockets.connect(WS_URL) as websocket:
                    self.ws = websocket
                    self.connected = True
                    Clock.schedule_once(lambda dt: self.update_status("Bağlandı", (0.2, 0.8, 0.4, 1)))
                    if self.username:
                        await self.ws_send({"u": self.username, "type": "hello"})
                    
                    async for message in websocket:
                        data = json.loads(message)
                        if data.get("type") == "users":
                            users = data.get("list", [])
                            Clock.schedule_once(lambda dt: self.main_scr.update_users_ui(users))
                        else:
                            u, m, to = data.get("u"), data.get("m"), data.get("to", "all")
                            is_dm = (to != "all")
                            key = "all" if not is_dm else (to if u == self.username else u)
                            self.main_scr.msg_history[key].append((u, m, is_dm))
                            if key == self.main_scr.target:
                                Clock.schedule_once(lambda dt, user=u, msg=m, dm=is_dm: self.main_scr.add_message_ui(user, msg, dm))
            except:
                self.connected = False; self.ws = None
                Clock.schedule_once(lambda dt: self.update_status("Bağlantı Yok", (0.8, 0.2, 0.2, 1)))
                await asyncio.sleep(5)

    def send_hello(self):
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.ws_send({"u": self.username, "type": "hello"}), self.loop)

    def update_status(self, text, color):
        self.main_scr.status.text = text
        self.main_scr.status.color = color

    async def ws_send(self, packet):
        if self.ws: await self.ws.send(json.dumps(packet))

if __name__ == "__main__":
    KankacordApp().run()
