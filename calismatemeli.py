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

# Klavye dostu mod
Window.softinput_mode = 'below_target'

# --- RENKLER ---
WS_URL = "wss://kankacord.onrender.com"
BG, SIDEBAR, CHAT_PANEL = (0.21, 0.22, 0.25, 1), (0.18, 0.19, 0.21, 1), (0.23, 0.24, 0.27, 1)
BLURPLE, TEXT, GREEN, RED = (0.45, 0.54, 0.85, 1), (0.92, 0.93, 0.95, 1), (0.27, 0.80, 0.45, 1), (0.92, 0.34, 0.38, 1)
CARD_BG, CARD_ME = (0.18, 0.19, 0.22, 1), (0.23, 0.29, 0.43, 1)
INPUT_BG = (0.16, 0.17, 0.19, 1)

# --- UI ELEMANLARI ---
class Panel(BoxLayout):
    def __init__(self, bg_color, radius=0, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self.update_rect, size=self.update_rect)
    def update_rect(self, *args): self.rect.pos, self.rect.size = self.pos, self.size

class RoundedButton(Button):
    def __init__(self, bg_color, radius=12, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self.update_rect, size=self.update_rect)
    def update_rect(self, *args): self.rect.pos, self.rect.size = self.pos, self.size

class MessageBubble(BoxLayout):
    def __init__(self, username, message, mine=False, is_dm=False, **kwargs):
        super().__init__(orientation="vertical", size_hint=(0.8, None), padding=dp(10), spacing=dp(5), **kwargs)
        bg = (0.4, 0.2, 0.4, 1) if is_dm else (CARD_ME if mine else CARD_BG)
        with self.canvas.before:
            Color(*bg)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self.update_rect, size=self.update_rect)
        tag = "[DM] " if is_dm else ""
        self.add_widget(Label(text=f"{tag}[b]{escape_markup(username)}[/b]", markup=True, color=BLURPLE, font_size=dp(12), size_hint_y=None, height=dp(18), halign="left"))
        self.body = Label(text=escape_markup(message), color=TEXT, font_size=dp(14), halign="left", valign="top", size_hint_y=None)
        self.body.bind(width=lambda s,w: setattr(s, 'text_size', (w, None)), texture_size=lambda s,t: setattr(s, 'height', t[1]))
        self.add_widget(self.body)
        Clock.schedule_once(lambda dt: setattr(self, 'height', self.body.height + dp(45)), 0)
    def update_rect(self, *args): self.rect.pos, self.rect.size = self.pos, self.size

# =========================
# EKRANLAR
# =========================
class LoginScreen(Screen):
    def build(self): # Placeholder for structure
        pass

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.target_user = "all" # Kiminle konuşuyoruz? (all = genel)
        self.history = defaultdict(lambda: deque(maxlen=100))
        self.online_users = set()

        root = BoxLayout(orientation="horizontal")
        
        # 1. SOL BAR: Kullanıcı Listesi
        self.user_panel = Panel(SIDEBAR, orientation="vertical", size_hint_x=None, width=dp(180), padding=dp(10), spacing=dp(5))
        self.user_panel.add_widget(Label(text="[b]Kankalar[/b]", markup=True, size_hint_y=None, height=dp(40)))
        
        # Genel Sohbet Butonu (Sabit)
        self.btn_all = RoundedButton(BLURPLE, text="# sohbet", size_hint_y=None, height=dp(45))
        self.btn_all.bind(on_release=lambda x: self.switch_chat("all"))
        self.user_panel.add_widget(self.btn_all)
        
        self.user_list_box = BoxLayout(orientation="vertical", spacing=dp(5))
        self.user_panel.add_widget(self.user_list_box)
        self.user_panel.add_widget(Widget()) # Aşağı iter
        
        # 2. SAĞ BAR: Sohbet Alanı
        chat = Panel(CHAT_PANEL, orientation="vertical", padding=dp(10), spacing=dp(10))
        
        header = BoxLayout(size_hint_y=None, height=dp(40))
        self.title = Label(text="# sohbet", bold=True, halign="left")
        self.status = Label(text="...", color=RED, size_hint_x=0.3)
        header.add_widget(self.title); header.add_widget(self.status)
        chat.add_widget(header)
        
        self.scroll = ScrollView()
        self.msg_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10))
        self.msg_box.bind(minimum_height=self.msg_box.setter('height'))
        self.scroll.add_widget(self.msg_box)
        chat.add_widget(self.scroll)
        
        inp_layout = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(10))
        self.inp = TextInput(hint_text="Mesaj yaz...", multiline=False, background_color=INPUT_BG, foreground_color=TEXT)
        self.inp.bind(on_text_validate=self.send)
        btn_s = RoundedButton(BLURPLE, text="GÖNDER", size_hint_x=None, width=dp(90))
        btn_s.bind(on_release=self.send)
        inp_layout.add_widget(self.inp); inp_layout.add_widget(btn_s)
        chat.add_widget(inp_layout)
        
        root.add_widget(self.user_panel)
        root.add_widget(chat)
        self.add_widget(root)

    def switch_chat(self, target):
        self.target_user = target
        self.title.text = f"# {target}" if target == "all" else f"@{target} (Özel)"
        self.msg_box.clear_widgets()
        # Geçmişi yükle
        for u, m, is_dm in self.history[target]:
            self.add_ui_msg(u, m, is_dm)

    def update_user_list(self, users):
        self.user_list_box.clear_widgets()
        for u in users:
            if u != self.app.username:
                b = RoundedButton(CARD_BG, text=f"@{u}", size_hint_y=None, height=dp(40))
                b.bind(on_release=lambda x, name=u: self.switch_chat(name))
                self.user_list_box.add_widget(b)

    def add_ui_msg(self, user, msg, is_dm=False):
        mine = (user == self.app.username)
        bubble = MessageBubble(username=user, message=msg, mine=mine, is_dm=is_dm)
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=bubble.height + dp(10))
        if mine: row.add_widget(Widget()); row.add_widget(bubble)
        else: row.add_widget(bubble); row.add_widget(Widget())
        self.msg_box.add_widget(row)
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0), 0.1)

    def send(self, *args):
        txt = self.inp.text.strip()
        if txt and self.app.connected:
            p = {"u": self.app.username, "m": txt, "to": self.target_user}
            asyncio.run_coroutine_threadsafe(self.app.ws_send(p), self.app.loop)
            self.inp.text = ""

# =========================
# APP ALTYAPISI
# =========================
class KankacordApp(App):
    username = ""; connected = False; ws = None; loop = asyncio.new_event_loop()
    
    def build(self):
        Window.clearcolor = BG
        self.sm = ScreenManager()
        
        # Login
        login = Screen(name='login')
        l_lay = Panel(BG, orientation="vertical", padding=dp(50), spacing=dp(20))
        l_lay.add_widget(Label(text="KANKACORD", font_size=dp(35), bold=True, color=BLURPLE))
        self.nick_inp = TextInput(hint_text="Nick seç...", multiline=False, size_hint_y=None, height=dp(50), background_color=INPUT_BG, foreground_color=TEXT)
        l_lay.add_widget(self.nick_inp)
        btn = RoundedButton(BLURPLE, text="GİRİŞ", size_hint_y=None, height=dp(50))
        btn.bind(on_release=self.go_main)
        l_lay.add_widget(btn); login.add_widget(l_lay); self.sm.add_widget(login)
        
        self.main_scr = MainScreen(name='main')
        self.sm.add_widget(self.main_scr)
        
        threading.Thread(target=self.net_work, daemon=True).start()
        return self.sm

    def go_main(self, *args):
        if self.nick_inp.text.strip():
            self.username = self.nick_inp.text.strip()
            self.sm.current = 'main'

    def net_work(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect())

    async def connect(self):
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    self.ws = ws; self.connected = True
                    Clock.schedule_once(lambda dt: self.update_st("ÇEVRİMİÇİ", GREEN))
                    # İlk bağlandığımızda kim olduğumuzu söyleyen bir "merhaba" paketi atalım (Sunucu tarafı için)
                    await self.ws_send({"u": self.username, "type": "hello"})
                    
                    async for r in ws:
                        d = json.loads(r)
                        msg_type = d.get("type", "msg")
                        
                        if msg_type == "users": # Sunucudan gelen kullanıcı listesi
                            Clock.schedule_once(lambda dt, u=d['list']: self.main_scr.update_user_list(u))
                        else:
                            u, m, to = d.get("u"), d.get("m"), d.get("to", "all")
                            is_dm = (to != "all")
                            
                            # Mantık: Mesajı hangi geçmişe kaydedeceğiz?
                            if not is_dm: # Genel mesaj
                                storage_key = "all"
                            else: # Özel mesaj
                                # Eğer ben gönderdiysem alıcıya, başkası gönderdiyse gönderene göre kaydet
                                storage_key = to if u == self.username else u
                            
                            self.main_scr.history[storage_key].append((u, m, is_dm))
                            
                            # Eğer şu an o kişiyle/kanalla konuşuyorsak ekrana bas
                            if storage_key == self.main_scr.target_user:
                                Clock.schedule_once(lambda dt, user=u, msg=m, dm=is_dm: self.main_scr.add_ui_msg(user, msg, dm))
            except:
                self.connected = False; self.update_st("BAĞLANTI YOK", RED); await asyncio.sleep(5)

    def update_st(self, t, c):
        self.main_scr.status.text, self.main_scr.status.color = t, c
    
    async def ws_send(self, p):
        if self.ws: await self.ws.send(json.dumps(p))

if __name__ == "__main__": KankacordApp().run()
