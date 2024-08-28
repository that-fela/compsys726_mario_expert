"""
This the primary class for the Mario Expert agent. It contains the logic for the Mario Expert agent to play the game and choose actions.

Your goal is to implement the functions and methods required to enable choose_action to select the best action for the agent to take.

Original Mario Manual: https://www.thegameisafootarcade.com/wp-content/uploads/2017/04/Super-Mario-Land-Game-Manual.pdf
"""

import json
import logging
import random
import time
from enum import Enum

import cv2
from mario_environment import MarioEnvironment
from pyboy.utils import WindowEvent
import numpy as np


class MarioController(MarioEnvironment):
    """
    The MarioController class represents a controller for the Mario game environment.

    You can build upon this class all you want to implement your Mario Expert agent.

    Args:
        act_freq (int): The frequency at which actions are performed. Defaults to 10.
        emulation_speed (int): The speed of the game emulation. Defaults to 0.
        headless (bool): Whether to run the game in headless mode. Defaults to False.
    """

    def __init__(
        self,
        act_freq: int = 10,
        emulation_speed: int = 0,
        headless: bool = False,
    ) -> None:
        super().__init__(
            act_freq=act_freq,
            emulation_speed=emulation_speed,
            headless=headless,
        )

        self.act_freq = act_freq

        # Example of valid actions based purely on the buttons you can press
        valid_actions: list[WindowEvent] = [
            WindowEvent.PRESS_ARROW_DOWN,
            WindowEvent.PRESS_ARROW_LEFT,
            WindowEvent.PRESS_ARROW_RIGHT,
            WindowEvent.PRESS_ARROW_UP,
            WindowEvent.PRESS_BUTTON_A,
            WindowEvent.PRESS_BUTTON_B,
        ]

        release_button: list[WindowEvent] = [
            WindowEvent.RELEASE_ARROW_DOWN,
            WindowEvent.RELEASE_ARROW_LEFT,
            WindowEvent.RELEASE_ARROW_RIGHT,
            WindowEvent.RELEASE_ARROW_UP,
            WindowEvent.RELEASE_BUTTON_A,
            WindowEvent.RELEASE_BUTTON_B,
        ]

        self.valid_actions = valid_actions
        self.release_button = release_button

    def run_action(self, actions: list[int], duration: int) -> None:
        """
        This is a very basic example of how this function could be implemented

        As part of this assignment your job is to modify this function to better suit your needs

        You can change the action type to whatever you want or need just remember the base control of the game is pushing buttons
        """

        # Simply toggles the buttons being on or off for a duration of act_freq
        for action in actions:
            self.pyboy.send_input(self.valid_actions[action.value])

        for _ in range(duration):
            self.pyboy.tick()

        for action in actions:
            self.pyboy.send_input(self.release_button[action.value])



class Action(Enum):
    DOWN =      0
    LEFT =      1
    RIGHT =     2
    UP =        3
    A =         4
    B =         5

class Size(Enum):
    ONExONE = 1
    TWOxTWO = 4

# Game Area Objects
class GAO(Enum):
    EMPTY =         (0, Size.ONExONE)
    MARIO =         (1, Size.TWOxTWO)
    MUSHROOM =      (6, Size.ONExONE)
    EMPTY_BLOCK =   (10, Size.ONExONE)
    BLOCK =         (13, Size.ONExONE)
    PIPE =          (14, Size.TWOxTWO)
    E_MUSHY =       (15, Size.ONExONE)
    E_GOOMBA =      (16, Size.ONExONE)
    E_BUZZBEE =     (18, Size.ONExONE)

ACTION_SPEED = 10

class MarioExpert:
    """
    The MarioExpert class represents an expert agent for playing the Mario game.

    Edit this class to implement the logic for the Mario Expert agent to play the game.

    Do NOT edit the input parameters for the __init__ method.

    Args:
        results_path (str): The path to save the results and video of the gameplay.
        headless (bool, optional): Whether to run the game in headless mode. Defaults to False.
    """

    def __init__(self, results_path: str, headless=False):
        self.results_path = results_path

        self.environment = MarioController(headless=headless)

        self.video = None

        self.previous_mario_pos = (0, 0)
        self.previous_actions = None
        self.previous_state = None
        self.frame_count = 0
        self.velocity = 0
        self.action_speed = ACTION_SPEED
        self.velocities = []
        self.serial_actions = []


    @staticmethod
    def get_position(game_area, id: GAO) -> list[(int, int)]:
        id = id.value if isinstance(id, GAO) else id
        size = id[1]
        id = id[0]
        entities = np.where(game_area == id)
        entities = list(zip(entities[1], entities[0]))
        
        cleaned_entities = []
        for i in range(0, len(entities), size.value):
            cleaned_entities.append(entities[i])

        if cleaned_entities:
            return cleaned_entities
        return None

    @staticmethod
    def get_area(game_area, mario_pos, x, y) -> list:
        return game_area[mario_pos[1] - y: mario_pos[1] + 2, mario_pos[0]: mario_pos[0] + x]

    @staticmethod
    def clamp(n, smallest, largest): 
        return max(smallest, min(n, largest))

    def actionier(self):
        state = self.environment.game_state()
        frame = self.environment.grab_frame()
        game_area = self.environment.game_area()
        self.action_speed = ACTION_SPEED

        mario_pos = self.get_position(game_area, GAO.MARIO)
        mario_pos = mario_pos[0] if mario_pos else self.previous_mario_pos

        pipes_pos = self.get_position(game_area, GAO.PIPE)
        closest_pipe_greater_than_mario = lambda pipe_pos: pipe_pos[0] > mario_pos[0]
        closest_pipe = list(filter(closest_pipe_greater_than_mario, pipes_pos)) if pipes_pos else None
        closest_pipe = closest_pipe[0] if closest_pipe else None

        actions = []

        if self.previous_actions is None:
            return mario_pos, actions
        
        self.velocity = np.subtract(state["x_position"], self.previous_state["x_position"])
        self.velocities.append(self.velocity)
        print(f"Velocity: {self.velocity}")

        enemy_area =            self.get_area(game_area, mario_pos, 9, 3)
        very_close_enemy_area = self.get_area(game_area, mario_pos, 4, 3)
        loot_area =             self.get_area(game_area, mario_pos, 2, 4)
        obstacle_area =         self.get_area(game_area, mario_pos, 9, 3)
        multi_area =            self.get_area(game_area, mario_pos, 11, 4)
        floor_area =            game_area[mario_pos[1] - 2: mario_pos[1] + 3, mario_pos[0]: mario_pos[0] + 4]
        below_area =            game_area[mario_pos[1] - 2: mario_pos[1] + 4, mario_pos[0]: mario_pos[0] + 5]

        oia = lambda area, id: id.value[0] in area
        coia = lambda area, id: len(np.where(area == id.value[0])[0])

        if len(self.velocities) > 5:
            c = [-1, 1, -1, 1, -1, 1, -1, 1, -1, 1]
            if c == self.velocities[-len(c):]:
                actions.append(Action.RIGHT)
                return mario_pos, actions
            c = [0, 0, 0, 0, 0]
            if c == self.velocities[-len(c):]:
                self.serial_actions.append(Action.LEFT)
                self.serial_actions.append(Action.LEFT)
                self.serial_actions.append(Action.LEFT)
                self.serial_actions.append(Action.LEFT)
                self.serial_actions.append(Action.LEFT)
            if state["stage"] != 1:
                self.serial_actions = []
            
        print(f"Time: {state['time']}")

        # Enemies
        if False:
            pass
        elif oia(enemy_area, GAO.E_MUSHY) and oia(loot_area, GAO.BLOCK):
            if self.velocity != 0:
                actions.append(Action.LEFT)
            if oia(very_close_enemy_area, GAO.E_MUSHY):
                actions.append(Action.A)
            return mario_pos, actions
        elif oia(enemy_area, GAO.E_MUSHY) or oia(enemy_area, GAO.E_GOOMBA) or oia(enemy_area, GAO.E_BUZZBEE):
            actions.append(Action.RIGHT)
            actions.append(Action.A)
            return mario_pos, actions
        elif state["time"] == 312:
            actions.append(Action.LEFT)
        elif len(below_area) == 0:
            actions.append(Action.RIGHT)
            return mario_pos, actions
        if len(below_area) == 6:
            if GAO.E_MUSHY.value[0] == below_area[5][3]:
                actions.append(Action.LEFT)
                return mario_pos, actions

        # Looting
        if False:
            pass
        elif oia(loot_area, GAO.BLOCK) and self.velocity == 0:
            actions.append(Action.A)
            return mario_pos, actions
        elif oia(loot_area, GAO.BLOCK) and self.velocity != 0:
            actions.append(Action.LEFT)
            return mario_pos, actions
        elif oia(loot_area, GAO.MUSHROOM):
            actions.append(Action.LEFT)
            return mario_pos, actions

        # Pipes
        actions.append(Action.RIGHT)
        if len(floor_area) == 0:
            return mario_pos, actions
        elif oia(obstacle_area, GAO.PIPE) and coia(obstacle_area, GAO.PIPE) >= 8:
            actions.append(Action.A)
            self.action_speed = 12
            return mario_pos, actions
        elif oia(obstacle_area, GAO.PIPE):
            actions.append(Action.A)
            return mario_pos, actions
        elif GAO.EMPTY.value[0] in floor_area[4]:
            actions.append(Action.A)
            return mario_pos, actions
        elif oia(obstacle_area, GAO.EMPTY_BLOCK) and GAO.EMPTY_BLOCK.value[0] != obstacle_area[1][0]:
            actions.append(Action.A)

        return mario_pos, actions

    def choose_action(self):
        mario_pos, actions = self.actionier()

        if len(self.serial_actions) > 0:
            actions = [self.serial_actions.pop(0)]
        else:
            # if actions contain the same action as the previous frame, don't do anything
            if self.previous_actions is not None:
                if actions == self.previous_actions:
                    actions = [Action.RIGHT, Action.UP]

        self.previous_mario_pos = mario_pos
        self.previous_actions = actions
        self.previous_state = self.environment.game_state()

        print(f"Frame: {self.frame_count}")
        c = 0
        if self.frame_count > c:
            time.sleep(0.1)

        # return random.randint(0, len(self.environment.valid_actions) - 1)
        return actions

    def step(self):
        """
        Modify this function as required to implement the Mario Expert agent's logic.

        This is just a very basic example
        """
        # Choose an action - button press or other...
        actions = self.choose_action()

        # Run the action on the environment908-
        self.environment.run_action(actions, self.action_speed)

        self.frame_count += 1





    def play(self):
        """
        Do NOT edit this method.
        """
        self.environment.reset()

        frame = self.environment.grab_frame()
        height, width, _ = frame.shape

        self.start_video(f"{self.results_path}/mario_expert.mp4", width, height)

        while not self.environment.get_game_over():
            frame = self.environment.grab_frame()
            self.video.write(frame)

            self.step()

        final_stats = self.environment.game_state()
        logging.info(f"Final Stats: {final_stats}")

        with open(f"{self.results_path}/results.json", "w", encoding="utf-8") as file:
            json.dump(final_stats, file)

        self.stop_video()

    def start_video(self, video_name, width, height, fps=30):
        """
        Do NOT edit this method.
        """
        self.video = cv2.VideoWriter(
            video_name, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

    def stop_video(self) -> None:
        """
        Do NOT edit this method.
        """
        self.video.release()
