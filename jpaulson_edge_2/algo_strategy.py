import gamelib
import random
import math
import warnings
import sys
from sys import maxsize
import json


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self, params):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

        self.attack_strength = int(params['attack_strength'])
        self.attack_strength_increase = int(params['attack_strength_increase'])

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        self.starter_strategy(game_state)

        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        start_walls = [[27,13],[26,13]]
        start_walls.extend([[x,x-14] for x in range(17, 25)])
        start_walls.extend([[16,3],[15,3]])
        start_walls.extend([x,17-x] for x in range(6,15))
        start_walls.extend([[2,11],[1,12],[0,13]])
        start_turrets = [[3,10],[4,10],[6,10],[4,9],[7,9]
                ,[25,11],[26,12]]
        game_state.attempt_spawn(WALL, start_walls)
        game_state.attempt_spawn(TURRET, start_turrets)

        turrets = [[25,12]] + start_turrets + [[7,9]]
        supports = [[x,16-x] for x in range(8,15)]
        supports.extend([[13,2],[15,2]])
        walls = [[2,11],[3,11],[4,11],[6,11],
                [25,13],[26,13],[27,13],[24,12],[24,13]]
        assert len(turrets) == len(supports) == len(walls) == 9
        for support_loc, turret_loc,wall_loc in zip(supports, turrets, walls):
            game_state.attempt_spawn(SUPPORT, support_loc)
            game_state.attempt_spawn(TURRET, turret_loc)
            game_state.attempt_upgrade(turret_loc)
            game_state.attempt_spawn(WALL, wall_loc)
            game_state.attempt_upgrade(wall_loc)

        more_turrets = [[5,8],[6,7],[7,6]]
        game_state.attempt_spawn(TURRET, more_turrets)
        for support in supports:
            game_state.attempt_upgrade(support)
        for wall in start_walls:
            game_state.attempt_upgrade(wall)

        #spawn_locations = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        #best_location, damage = self.least_damage_spawn_location(game_state, spawn_locations)
        if game_state.get_resource(MP) >= self.attack_strength:
            spawn_location = [14,0]
            game_state.attempt_spawn(SCOUT, spawn_location, 1000)
            #game_state.attempt_spawn(DEMOLISHER, best_location, 1000)
            self.attack_strength += self.attack_strength_increase

    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames 
        as shown in the on_action_frame function
        """
        for location in self.scored_on_locations:
            # Build turret one space above so that it doesn't block our own edge spawn locations
            build_location = [location[0], location[1]+2]
            game_state.attempt_spawn(TURRET, build_location)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        location_options = self.filter_blocked_locations(location_options, game_state)
        damages = []
        end_points = game_state.game_map.get_edge_locations(game_state.game_map.TOP_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.TOP_RIGHT)
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            if path[-1] in end_points:
                damage = 0
                for path_location in path:
                    # Get number of enemy turrets that can attack each location and multiply by turret damage
                    damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
                damages.append(damage)
            else:
                damages.append(1000)

        # Now just return the location that takes the least damage
        if damages:
            best_index = damages.index(min(damages))
            return (location_options[best_index], damages[best_index])
        else:
            return ([14,0], 1000)

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units

    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        pass
    # Let's record at what position we get scored on
        #state = json.loads(turn_string)
        #events = state["events"]
        #breaches = events["breach"]
        #for breach in breaches:
        #    location = breach[0]
        #    unit_owner_self = True if breach[4] == 1 else False
        #    # When parsing the frame data directly, 
        #    # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
        #    if not unit_owner_self:
        #        gamelib.debug_write("Got scored on at: {}".format(location))
        #        self.scored_on_locations.append(location)
        #        gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        params = json.loads(open(sys.argv[1]).read())
    else:
        params = {'attack_strength': 9, 'attack_strength_increase': 3}
    algo = AlgoStrategy(params)
    algo.start()
