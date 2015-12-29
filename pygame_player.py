import pygame
import numpy  # import is unused but required or we fail later
from pygame.constants import K_DOWN, KEYDOWN, KEYUP, QUIT
import pygame.surfarray
import pygame.key


def function_intercept(intercepted_func, intercepting_func):
    """
    Intercepts a method call and calls the supplied intercepting_func with the result of it's call and it's arguments

    Example:
        def get_event(result_of_real_event_get, *args, **kwargs):
            # do work
            return result_of_real_event_get

        pygame.event.get = function_intercept(pygame.event.get, get_event)

    :param intercepted_func: The function we are going to intercept
    :param intercepting_func:   The function that will get called after the intercepted func. It is supplied the return
    value of the intercepted_func as the first argument and it's args and kwargs.
    :return: a function that combines the intercepting and intercepted function, should normally be set to the
             intercepted_functions location
    """

    def wrap(*args, **kwargs):
        real_results = intercepted_func(*args, **kwargs)  # call the function we are intercepting and get it's result
        intercepted_results = intercepting_func(real_results, *args, **kwargs)  # call our own function a
        return intercepted_results

    return wrap


class PyGamePlayer(object):
    def __init__(self, desired_fps=10):
        """
        Abstract class for learning agents, such as running reinforcement learning neural nets against PyGame games.

        The get_keys_pressed and get_feedback methods must be overriden by a subclass to use

        Call start method to start playing intercepting PyGame and training our machine
        :param desired_fps: The number of frames per second we want the game running at.
                            Useful if training the ai is too slow.
        """
        self.desired_fps = desired_fps
        self._keys_pressed = []
        self._last_keys_pressed = []
        self._playing = False
        self._default_flip = pygame.display.flip
        self._default_update = pygame.display.update
        self._default_event_get = pygame.event.get
        self._default_time_clock = pygame.time.Clock
        self._default_get_ticks = pygame.time.get_ticks
        self._game_time = 0.0

    def get_keys_pressed(self, screen_array, feedback):
        """
        Called whenever the screen buffer is refreshed. returns the keys we want pressed in the next until the next
        screen refresh

        :param screen_array: 3d numpy.array of float. screen_width * screen_height * rgb
        :param feedback: result of call to get_feedback
        :return: a list of the integer values of the keys we want pressed. See pygame.constants for values
        """
        raise NotImplementedError("Please override this method")

    def get_feedback(self):
        """
        Overriden method should hook into game events to give feeback to the learning agent

        :return: value we want to give feedback, reward/punishment to our learning agent
        """
        raise NotImplementedError("Please override this method")

    def start(self):
        """
        Start playing the game. We will now start listening for screen updates calling our play and reward functions
        and returning our intercepted key presses
        """
        if self._playing:
            raise Exception("Already playing")

        self._default_flip = pygame.display.flip
        self._default_update = pygame.display.update
        self._default_event_get = pygame.event.get
        self._default_time_clock = pygame.time.Clock
        self._default_get_ticks = pygame.time.get_ticks

        pygame.display.flip = function_intercept(pygame.display.flip, self._on_screen_update)
        pygame.display.update = function_intercept(pygame.display.update, self._on_screen_update)
        pygame.event.get = function_intercept(pygame.event.get, self._on_event_get)
        pygame.time.Clock = function_intercept(pygame.time.Clock, self._on_time_clock)
        pygame.time.get_ticks = function_intercept(pygame.time.get_ticks, self._get_game_time_ms)
        #TODO: handle pygame.time.set_timer...

        self._playing = True

    def stop(self):
        """
        Stop playing the game. Will try and return PyGame to the state it was in before we started
        """
        if not self._playing:
            raise Exception("Already stopped")

        pygame.display.flip = self._default_flip
        pygame.display.update = self._default_update
        pygame.event.get = self._default_event_get
        pygame.time.Clock = self._default_time_clock
        pygame.time.get_ticks = self._default_get_ticks

        self._playing = False

    def _get_ms_per_frame(self):
        return 1000.0 / self.desired_fps

    def _get_game_time_ms(self):
        return self._game_time

    def _on_time_clock(self, _, *args, **kwargs):
        return self._FixedFPSClock(self._get_ms_per_frame, self._game_time)

    def _on_screen_update(self, _, *args, **kwargs):
        surface_array = pygame.surfarray.array3d(pygame.display.get_surface())
        reward = self.get_feedback()
        keys = self.get_keys_pressed(surface_array, reward)
        self._last_keys_pressed = self._keys_pressed
        self._keys_pressed = keys

        # now we have processed a frame increment the game timer
        self._game_time += self._get_ms_per_frame()

    def _on_event_get(self, _, *args, **kwargs):
        key_down_events = [pygame.event.Event(KEYDOWN, {"key": x})
                           for x in self._keys_pressed if x not in self._last_keys_pressed]
        key_up_events = [pygame.event.Event(KEYUP, {"key": x})
                         for x in self._last_keys_pressed if x not in self._keys_pressed]

        result = []

        # have to deal with arg type filters
        if args:
            if hasattr(args[0], "__iter__"):
                args = args[0]

            for type_filter in args:
                if type_filter == QUIT:
                    pass  # never quit
                elif type_filter == KEYUP:
                    result = result + key_up_events
                elif type_filter == KEYDOWN:
                    result = result + key_down_events
        else:
            result = key_down_events + key_up_events

        return result

    @property
    def playing(self):
        """
        Returns if we are in a state where we are playing/intercepting PyGame calls
        :return: boolean
        """
        return self._playing

    @playing.setter
    def playing(self, value):
        if self._playing == value:
            return
        if self._playing:
            self.stop()
        else:
            self.start()

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    class _FixedFPSClock(object):
        def __init__(self, get_seconds_per_frame_func, get_time_ms_func):
            self._get_ms_per_frame_func = get_seconds_per_frame_func
            self._get_time_ms_func = get_time_ms_func

        def tick(self, _=None):
            return self._get_ms_per_frame_func()

        def tick_busy_loop(self, _=None):
            return self._get_ms_per_frame_func()

        def get_time(self):
            return self._get_time_ms_func()

        def get_raw_time(self):
            return self._get_time_ms_func()

        def get_fps(self):
            return int(1.0/self._get_ms_per_frame_func())