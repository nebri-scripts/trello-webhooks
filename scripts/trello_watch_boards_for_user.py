import logging
import traceback

from trello import (
    Board,
    TrelloClient
)


logging.basicConfig(filename='trello_webhook_module.log', level=logging.DEBUG)


class trello_watch_boards_for_user(NebriOS):
    
    listens_to = ['trello_watch_boards_for_user']
    
    def check(self):
        if self.trello_watch_boards_for_user is True:
            return self.verify_user()
        return False
        
    def action(self):
        logging.debug('Starting trello_watch_boards_for_user action...')
        try:
            client = self.get_client()
            user = self.get_me()
            member_data = self.setup_backup_board_and_list(client, user)
            self.setup_board_tree(client)
            logging.debug('callback id: %s, url: %s', user['id'], self.get_hook_url(shared.TRELLO_WEBHOOK_MEMBER_CALLBACK_URL))
            client.create_hook(self.get_hook_url(shared.TRELLO_WEBHOOK_MEMBER_CALLBACK_URL), user['id'])
        except Exception, err:
            logging.debug('Exception caught: %s', traceback.format_exc())
            raise err
        logging.debug('Done with trello_watch_boards_for_user action...')
    
    def setup_board_tree(self, client):
        board_tree = self.get_board_tree()
        boards = client.list_boards()
        for board in boards:
            local_board, created = Process.objects.get_or_create(kind="trello_board", board_id=board.id, PARENT=board_tree)
            if created:
                local_board.kind = "trello_board"
                local_board.board_name = board.name
                local_board.board_id = board.id
                local_board.save()
            else:
                local_board = Process.objects.get(kind="trello_board", board_id=board.id)
            for board_list in board.all_lists():
                if len(local_board.CHILDREN.filter(kind="trello_list", list_id=board_list.id)) == 0:
                    local_list = Process.objects.create(kind="trello_list", list_id=board_list.id, list_name=board_list.name, PARENT=local_board)
                    local_list.save()
            if created:
                client.create_hook(self.get_hook_url(shared.TRELLO_WEBHOOK_BOARD_CALLBACK_URL), local_board.board_id)
        
    def get_board_tree(self):
        board_tree, _ = Process.objects.get_or_create(kind="trello_board_tree")
        return board_tree
    
    def get_hook_url(self, base_url):
        return '%s?trello_api_key=%s&trello_token=%s' % (base_url, shared.TRELLO_API_KEY, self.trello_token)
        
    def setup_backup_board_and_list(self, client, user):
        member_data = self.get_member_data(user['id'])
        board_created = self.create_backup_board(client, member_data)
        self.create_backup_list(client, member_data, board_created)
        return member_data
    
    def create_backup_list(self, client, member_data, board_created):
        create_backup_list = False
        backup_board = client.get_board(member_data.backup_board_id)
        if member_data.backup_list_id is None:
            create_backup_list = True
        else:
            try:
                backup_list = backup_board.get_list(member_data.backup_list_id)
                if backup_list.board.id != backup_board.id or backup_list.closed:
                    create_backup_list = True
            except Exception, e:
                create_backup_list = True
        if create_backup_list:
            if board_created:
                for list in backup_board.all_lists():
                    list.close()
            backup_list = backup_board.add_list('Backup List')
            member_data.backup_list_id = backup_list.id
            member_data.backup_list_name = backup_list.name
            member_data.save()
    
    def create_backup_board(self, client, member_data):
        create_backup_board = False
        if member_data.backup_board_id is None:
            create_backup_board = True
        else:
            try:
                backup_board = client.get_board(backup_board_id)
                if backup_board.closed:
                    create_backup_board = True
            except Exception, e:
                create_backup_board = True
        if create_backup_board:
            backup_board_json = client.fetch_json('/boards', http_method='POST', post_args={'name': 'Backup Board'})
            backup_board = Board.from_json(trello_client=client, json_obj=backup_board_json)
            member_data.backup_board_id = backup_board.id
            member_data.backup_board_name = backup_board.name
            member_data.save()
        return create_backup_board
    
    def get_member_data(self, member_id):
        member_data, _ = Process.objects.get_or_create(kind="trello_member_data", member_id=member_id)
        return member_data
    
    def get_trello_token(self):
        if self.trello_token is None:
            try:
                self.trello_token = Process.objects.get(kind="trello_oauth_token").token
            except:
                load_card('trello-token-save')
                raise Exception('Token does not exist. Please supply one on the Trello OAuth Token Creation card or run trello_webhook_setup.')
        return self.trello_token
    
    def get_client(self):
        self.get_trello_token()
        return TrelloClient(api_key=shared.TRELLO_API_KEY, api_secret=shared.TRELLO_API_SECRET, token=self.trello_token)
    
    def get_me(self):
        client = self.get_client()
        return client.fetch_json('/members/me')
    
    def verify_user(self):
        # Try authenticating with the credentials provided
        # We should not get an authorization error
        try:
            self.get_me()
            return True
        except Exception as e:
            # We failed to authenticate with the provided credentials
            raise Exception(str(e))
        return False
