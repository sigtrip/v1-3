from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

class ArgosInterface(App):
    def build(self):
        layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        # Заголовок с кодом 1991
        self.status = Label(text="🔱 ARGOS v1.3 [OFFLINE MODE]\nSTATUS: AWAITING KEY 1991", 
                            halign='center', font_size='20sp')
        
        self.key_input = TextInput(hint_text="Paste Quantum Key here...", 
                                   multiline=False, size_hint=(1, 0.2))
        
        btn = Button(text="ACTIVATE OVERRIDE", size_hint=(1, 0.3),
                     background_color=(0, 0.7, 1, 1))
        btn.bind(on_press=self.activate)
        
        layout.add_widget(self.status)
        layout.add_widget(self.key_input)
        layout.add_widget(btn)
        return layout

    def activate(self, instance):
        key = self.key_input.text.strip()
        if len(key) == 64:  # Длина SHA-256 ключа
            self.status.text = f"✅ KEY ACCEPTED\nRESONANCE: 156 QUBITS\nPOWERING UP..."
        else:
            self.status.text = "❌ INVALID KEY STRUCTURE"

if __name__ == '__main__':
    ArgosInterface().run()
