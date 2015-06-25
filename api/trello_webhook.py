import logging
import pytz
import traceback

from trello import TrelloClient


logging.basicConfig(filename='trello_webhook_module.log', level=logging.DEBUG)

ACTIONS_FOR_CACHING = ['addAttachmentToCard', 'addChecklistToCard', 'addLabelToCard', 'convertToCardFromCheckItem',
                       'createCard', 'createCheckItem', 'deleteAttachmentFromCard', 'deleteCheckItem',
                       'removeChecklistFromCard', 'removeLabelFromCard', 'updateCard', 'updateCheckItemStateOnCard',
                       'updateChecklist', 'deleteCard']
DONE_LIST_NAME = "Done"


def oauth_token(request):
    if request.FORM:
        user = request.user
        try:
            p = Process.objects.get(user=request.user, kind="trello_oauth_token")
            p.token = request.FORM.trello_token
            p.save()
        except:
            p = Process.objects.create()
            p.user=request.user
            p.kind="trello_oauth_token"
            p.token=request.FORM.trello_token
            p.trello_watch_boards_for_user = True
            p.save()

def board_callback(request):
    try:
        client = _get_client()
        action = request.BODY['action']
        action_type = action['type']
        if action_type in ACTIONS_FOR_CACHING:
            card_id = action['data']['card']['id']
            if action_type == 'deleteCard':
                try:
                    existing_process = Process.objects.get(kind="trello_card", card_id=card_id)
                    card_json = existing_process.card_json
                except:
                    return
            else:
                card_json = client.fetch_json('/cards/' + card_id, query_params={'actions': 'all', 'checklists': 'all', 'attachments': 'true', 'filter': 'all'})
            _update_card(action, action_type, action['data'], card_json)
    except Exception, err:
        logging.debug('Exception caught: %s', traceback.format_exc())
        raise err

def member_callback(request):
    try:
        client = _get_client()
        action = request.BODY['action']
        action_type = action['type']
        if action_type in ['createBoard', 'addMemberToBoard']:
            client = _get_client(request)
            board_id = action['data']['board']['id']
            board_tree, _ = Process.objects.get_or_create(kind="trello_board_tree")
            local_board, created = Process.objects.get_or_create(kind="trello_board", board_id=board_id, PARENT=board_tree)
            if created:
                local_board.board_name = action['data']['board']['name']
                local_board.save()
                client.create_hook(_get_hook_url(request, shared.TRELLO_WEBHOOK_BOARD_CALLBACK_URL), board_id)
    except Exception, err:
        logging.debug('Exception caught: %s', traceback.format_exc())
        raise err

def _update_card(action, action_type, action_data, card_json):
    first_action = card_json['actions'][-1]
    last_action = card_json['actions'][0]
    closed = False
    deleted = False
    archived = False
    card_data = action_data['card']
    board_data = action_data['board']
    list_data = action_data.get('list', None)
    moved = False
    if list_data is None and 'listAfter' in action_data:
        list_data = action_data['listAfter']
        moved = True
        if list_data['name'] == DONE_LIST_NAME and 'listBefore' in action_data:            
            closed = True
    if list_data is None:
        list_data = last_action['list']
    card_closed = card_data.get('closed', False)
    old_closed = False
    if 'old' in card_data:
        old_closed = card_data['old'].get('closed', False)
    if action_type == "deleteCard":
        deleted = True
    elif card_closed and not old_closed:
        archived = True
    local_board = _get_board(board_data['id'])
    local_list = _get_list(local_board, list_data['id'])
    if local_list.list_name != list_data['name']:
        local_list.list_name = list_data['name']
        local_list.save()
    local_card, created = Process.objects.get_or_create(kind="trello_card", PARENT=local_list, card_id=card_data['id'])
    if created:
        local_card.short_link = card_data['shortLink']
        local_card.card_member_creator = first_action['memberCreator']['id']
        local_card.card_moved = False
    if moved:
        try:
            previous_card = Process.objects.get(kind="trello_card", card_id=card_data['id'])
            if previous_card.PARENT.list_id != local_card.PARENT.list_id:
                previous_card.card_moved = True
                previous_card.save()
        except:
            pass
    if closed:
        local_card.card_closed = True
        local_card.card_closed_datetime = datetime.now()
        local_card.card_closed_date = str(local_card.card_closed_datetime.date())
        local_card.card_closed_by_noncreator = first_action['idMemberCreator'] != action['idMemberCreator']
    if deleted:
        local_card.card_deleted = True
        local_card.card_deleted_datetime = datetime.now()
        local_card.card_deleted_date = str(local_card.card_deleted_datetime.date())
        local_card.card_deleted_by_noncreator = first_action['idMemberCreator'] != action['idMemberCreator']
    if archived:
        local_card.card_archived = True
        local_card.card_archived_datetime = datetime.now()
        local_card.card_archived_date = str(local_card.card_archived_datetime.date())
        local_card.card_archived_by_noncreator = first_action['idMemberCreator'] != action['idMemberCreator']
    if 'due' in card_data:
        try:
            local_card.card_due = parse_datetime(card_data['due'])
        except:
            local_card.card_due = None
    else:
        local_card.card_due = None
    if isinstance(local_card.card_due, datetime):
        local_card.card_due = local_card.card_due.astimezone(pytz.utc)
        local_card.card_due_date = str(local_card.card_due.date())
        local_card.card_is_due = True
    else:
        local_card.card_is_due = False
    if list_data['name'] == DONE_LIST_NAME:
        local_card.card_due = None        
    local_card.card_json = card_json
    local_card.save()

def _get_list(board, list_id):
    board_list, _ = Process.objects.get_or_create(PARENT=board, kind="trello_list", list_id=list_id)
    return board_list

def _get_board(board_id):
    return Process.objects.get(kind="trello_board", board_id=board_id)

def _get_trello_token():
    try:
        return Process.objects.get(kind="trello_oauth_token").token
    except:
        load_card('trello-token-save')
        raise Exception('Token does not exist. Please supply one on the Trello OAuth Token Creation card or run trello_webhook_setup.')
    return ""

def _get_client():
    token = _get_trello_token()
    return TrelloClient(api_key=shared.TRELLO_API_KEY, api_secret=shared.TRELLO_API_SECRET, token=token)

