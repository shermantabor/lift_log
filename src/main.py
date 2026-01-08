"""
Entry point for the Lift Log application.

Initializes the application and runs the main program loop,
handling user interaction and control flow.
"""

from menu_options import (start_new_session, add_set_ui, view_active_session,
                          view_stats, view_sessions, end_active_session, closeout)
from services import get_username, get_or_create_user, get_menu_choice
from db import db_init_db

def main():
    '''
    I: none
    P: execute login, main loop, and close out
    O: none
    '''

    db_init_db()
    active_username = get_username()
    active_user_id = get_or_create_user(active_username)
    print(f'logged in as: {active_username}; user_id: {active_user_id}')

    active_session_id = None
    menu_choice = get_menu_choice()

    while True:
        if menu_choice == 1:
            start_new_session(active_user_id)

        elif menu_choice == 2:
            add_set_ui(active_user_id)

        elif menu_choice == 3:
            view_active_session(active_user_id)

        elif menu_choice == 4:
            view_stats(active_user_id)

        elif menu_choice == 5:
            view_sessions(active_user_id)

        elif menu_choice == 6:
            end_active_session(active_user_id)

        elif menu_choice == 7:
            if closeout(active_user_id):
                break

        menu_choice = get_menu_choice()

if __name__ == "__main__":
    main()
