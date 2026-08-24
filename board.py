class Board:
    def __init__(self):
        self.note_cards = []

    def add_note_card(self, note_card):
        self.note_cards.append(note_card)

    def delete_note_card(self, note_card):
        self.note_cards.remove(note_card)
        # Explicitly pop the widget reference from self.note_cards
        note_card.widget.destroy()