import pynput
from tkinter import Tk

class HotkeyManager:
    def __init__(self, root):
        self.root = root
        self.listener = pynput.keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

    def on_key_press(self, key):
        # Instead of directly triggering Tkinter methods, use root.after()
        self.root.after(0, self.delegate_to_main_thread, key)

    def delegate_to_main_thread(self, key):
        # Delegate the key press handling to the main thread
        self.root.event_generate(f'<<Key_{key.name}>>')