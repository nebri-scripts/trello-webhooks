import logging

NOTIFICATION_TYPES = {'completed': 'Recently finished tickets',
                      'due': 'Recently past due tickets'}
NON_CREATOR_STATE = False

logging.basicConfig(filename='trello_webhook_module.log', level=logging.DEBUG)

class trello_notify_email(NebriOS):
    listens_to = ['trello_notify_email']

    def check(self):
        return self.trello_notify_email in NOTIFICATION_TYPES

    def action(self):
        address = ""
        if self.trello_notify_email == "due":
            address = shared.PAST_DUE_NOTIFY_ADDRESS
        else:
            address = shared.COMPLETED_NOTIFY_ADDRESS
        cards = []
        today = datetime.now().date()
        yesterday = (datetime.now() - timedelta(days=1)).date()
        time_boundary = datetime.now() - timedelta(hours=24)
        cards = self.get_cards(today, yesterday, time_boundary)
        if len(cards) > 0:
            message = []
            cards_by_board = self.group_cards_by_board(cards)
            message.append("<h2>%s</h2>" % NOTIFICATION_TYPES[self.trello_notify_email])
            for name, cards in cards_by_board.iteritems():
                message.append("<h3>Board: %s</h3><ul>" % name)
                for card in cards:
                    message.append("<li><a href='https://trello.com/c/%s'>%s</a></li>" % (card.short_link, card.card_json['name']))
                message.append("</ul>")
            send_email(address, "".join(message), NOTIFICATION_TYPES[self.trello_notify_email])
    
    def group_cards_by_board(self, cards):
        cards_by_board = {}
        for card in cards:
            board_name = card.card_json['actions'][0]['data']['board']['name']
            if board_name not in cards_by_board:
                cards_by_board[board_name] = [card]
            else:
                cards_by_board[board_name].append(card)
        return cards_by_board
    
    def get_cards(self, today, yesterday, time_boundary):
        cards = []
        if self.trello_notify_email == 'due':
            today_cards = Process.objects.filter(card_is_due=True, card_due_date=str(today))
            yesterday_cards = Process.objects.filter(card_is_due=True, card_due_date=str(yesterday))
            for card in yesterday_cards:
                if card.card_due > time_boundary and not card.card_closed and not card.card_deleted and not card.card_archived:                    
                    cards.append(card)
            for card in today_cards:
                if card.card_due > time_boundary and not card.card_closed and not card.card_deleted and not card.card_archived:
                    cards.append(card)
        elif self.trello_notify_email == 'completed':
            today_cards = Process.objects.filter(card_closed=True, card_closed_date=str(today))
            yesterday_cards = Process.objects.filter(card_closed=True, card_closed_date=str(yesterday))
            for card in yesterday_cards:
                if card.card_closed_datetime > time_boundary and not card.card_deleted and not card.card_archived and self.card_closed_by_noncreator == NON_CREATOR_STATE:
                    cards.append(card)
            for card in today_cards:
                if card.card_closed_datetime > time_boundary and not card.card_deleted and not card.card_archived and self.card_closed_by_noncreator == NON_CREATOR_STATE:
                    cards.append(card)
        return cards
