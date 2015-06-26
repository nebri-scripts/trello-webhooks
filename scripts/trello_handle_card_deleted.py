import logging

from trello import TrelloClient

logging.basicConfig(filename='trello_webhook_module.log', level=logging.DEBUG)

NON_CREATOR_STATE = True

class trello_handle_card_deleted(NebriOS):
    listens_to = ['card_deleted']

    def check(self):
        return self.kind == "trello_card" and self.card_deleted == True and not self.card_deleted_handled and self.card_deleted_by_noncreator == NON_CREATOR_STATE

    def action(self):        
        client = self.get_client()
        user = self.get_me(client)
        member_data = self.get_member_data(user['id'])
        board = client.get_board(member_data.backup_board_id)
        backup_list = board.get_list(member_data.deleted_list_id)
        for label in self.card_json['labels']:
            board.add_label(label['name'], label['color'])
        add_card_kwargs = {'desc': self.card_json['desc'], 'labels': self.card_json['labels']}
        due_date = self.card_json.get('due', None)
        if due_date:
            add_card_kwargs['due'] = due_date                
        card_backup = backup_list.add_card(self.card_json['name'], **add_card_kwargs)
        for checklist in self.card_json['checklists']:
            card_backup.add_checklist(checklist['name'], [item['name'] for item in checklist['checkItems']], itemstates=[item['state'] == 'complete' for item in checklist['checkItems']])
        for attachment in self.card_json['attachments']:
            card_backup.attach(url=attachment['url'])
        self.card_deleted_handled = True
    
    def get_me(self, client):
        return client.fetch_json('/members/me')
    
    def get_trello_token(self):
        try:
            return Process.objects.get(kind="trello_oauth_token").token
        except:
            load_card('trello-token-save')
            raise Exception('Token does not exist. Please supply one on the Trello OAuth Token Creation card or run trello_webhook_setup.')
    
    def get_client(self):
        return TrelloClient(api_key=shared.TRELLO_API_KEY, api_secret=shared.TRELLO_API_SECRET, token=self.get_trello_token())

    def get_member_data(self, member_id):
        member_data, _ = Process.objects.get_or_create(kind="trello_member_data", member_id=member_id)
        return member_data
