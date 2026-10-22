from autodownloader.main import Game_data_manager

def test_nearest_game():
    manager = Game_data_manager("basketball",1)
    print(manager.nearest_game)