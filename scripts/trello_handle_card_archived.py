import logging

from trello import TrelloClient

logging.basicConfig(filename='trello_webhook_module.log', level=logging.DEBUG)

NON_CREATOR_STATE = True

class trello_handle_card_archived(NebriOS):
    listens_to = ['card_archived']

    def check(self):
        return self.kind == "trello_card" and self.card_archived == True and not self.card_archived_handled and self.card_archived_by_noncreator == NON_CREATOR_STATE

    def action(self):        
        client = self.get_client()
        user = self.get_me(client)
        member_data = self.get_member_data(user['id'])
        client.fetch_json(
                '/cards',
                http_method='POST',
                post_args={
                    'idList': member_data.backup_list_id,
                    'urlSource': "null",
                    'idCardSource': self.card_id
                }
            )
        self.card_archived_handled = True
    
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
