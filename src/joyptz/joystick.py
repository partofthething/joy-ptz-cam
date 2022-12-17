"""
Control the cam with pygame.

Joystick or keyboard.
"""

import pygame

from .controller import Controller

BLACK = pygame.Color("black")
WHITE = pygame.Color("white")


class TextPrint(object):
    """A little screen for pygame to print to."""

    def __init__(self, screen):
        self._screen = screen
        self.reset()
        self.font = pygame.font.Font(None, 20)

    def info(self, textString):
        textBitmap = self.font.render(textString, True, BLACK)
        self._screen.blit(textBitmap, (self.x, self.y))
        self.y += self.line_height

    def reset(self):
        self._screen.fill(WHITE)
        self.x = 10
        self.y = 10
        self.line_height = 15

    def indent(self):
        self.x += 10

    def unindent(self):
        self.x -= 10


MOVE_KEYS = [
    pygame.K_RIGHT,
    pygame.K_LEFT,
    pygame.K_UP,
    pygame.K_DOWN,
    pygame.K_EQUALS,
    pygame.K_MINUS,
]


class JoystickController(Controller):
    """Pygame-based I/O camera controller"""

    def __init__(self, cam, config):
        pygame.init()
        screen = pygame.display.set_mode((500, 700))
        pygame.display.set_caption("Joy PTZ")
        # this just locks the mouse in the window which isn't
        # really what we want.
        # pygame.event.set_grab(True)
        pygame.joystick.init()
        log = TextPrint(screen)
        super().__init__(cam, config, log)

    def loop(self):
        done = False
        preset = 1
        clock = pygame.time.Clock()
        while not done:
            self.log.reset()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    done = True
                self._handle_joystick_event(event)
                self._handle_keyboard_event(event)

            self._read_joystick_axes()
            self._process_move_vector()

            pygame.display.flip()

            # Limit to this many frames per second.
            clock.tick(5)

        pygame.quit()

    def _read_joystick_axes(self):
        """Read joystick axes"""
        joystick_count = pygame.joystick.get_count()
        self.log.indent()
        axes_vals = []
        for i in range(joystick_count):
            axes_vals = []
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            try:
                jid = joystick.get_instance_id()
            except AttributeError:
                # get_instance_id() is an SDL2 method
                jid = joystick.get_id()
            self.log.indent()
            name = joystick.get_name()
            self.log.info("Joystick name: {}".format(name))

            try:
                guid = joystick.get_guid()
            except AttributeError:
                # get_guid() is an SDL2 method
                pass
            else:
                self.log.info("GUID: {}".format(guid))

            axes = joystick.get_numaxes()
            self.log.info("Number of axes: {}".format(axes))
            self.log.indent()

            for i in range(axes):
                axis = joystick.get_axis(i)
                # clear out noise on return to zero
                if abs(axis) < 0.005:
                    axis = 0.0
                axes_vals.append(axis)
                self.log.info("Axis {} value: {:>6.3f}".format(i, axis))
            self.log.unindent()

            buttons = joystick.get_numbuttons()
            self.log.info("Number of buttons: {}".format(buttons))
            self.log.indent()

            for i in range(buttons):
                button = joystick.get_button(i)
                self.log.info("Button {:>2} value: {}".format(i, button))

            self.log.unindent()

            hats = joystick.get_numhats()
            self.log.info("Number of hats: {}".format(hats))
            self.log.indent()

            # Hat position. All or nothing for direction, not a float like
            # get_axis(). Position is a tuple of int values (x, y).
            for i in range(hats):
                hat = joystick.get_hat(i)
                self.log.info("Hat {} value: {}".format(i, str(hat)))
            self.log.unindent()

            self.log.unindent()
        if axes_vals:
            # now move the camera accordingly!
            # just take the first three axes as x,y, and zoom

            # well ok let's load it, but combine it from the two trigger axes.
            # They both rest at -1 and activate to +1
            # we want left trigger -1 to be zero and +1 to be 1
            # and right trigger -1 to be zero and +1 to be -1
            if len(axes_vals) >= 6:
                # handle cases where there are no triggers without crashing.
                zoom = -(axes_vals[2] + 1) / 2.0 + (axes_vals[5] + 1) / 2.0
            else:
                zoom = 0.0

            move_vector = axes_vals[:2] + [zoom]

            # add a response curve so slight motions are easier to control
            # simply square everything while retaining sign for starters.
            move_vector = [i * abs(i) for i in move_vector]

            # fix vertical axis flipped on my controller
            move_vector[1] *= -1
            self._move_vector = move_vector

            self._focus = axes_vals[3]

    def _handle_keyboard_event(self, event):
        if event.type == pygame.KEYDOWN:
            vector = self._move_vector
            if event.key == pygame.K_RIGHT:
                vector[0] = self._speed
            elif event.key == pygame.K_LEFT:
                vector[0] = -self._speed
            elif event.key == pygame.K_DOWN:
                vector[1] = -self._speed
            elif event.key == pygame.K_UP:
                vector[1] = self._speed
            elif event.key == pygame.K_EQUALS:
                vector[2] = 1
            elif event.key == pygame.K_MINUS:
                vector[2] = -1

            try:
                speed = int(event.unicode)
                self._speed = float(speed) / 10.0
                self.log.info(f"Speed {self._speed}!")
            except ValueError:
                pass
            self.log.info(f"{event.key} {event.unicode}")
        if event.type == pygame.KEYUP and event.key in MOVE_KEYS:
            self.log.info("Stopping!")
            self._move_vector = [0, 0, 0]

    def _handle_joystick_event(self, event):
        if event.type == pygame.JOYBUTTONDOWN:
            pass
        elif event.type == pygame.JOYBUTTONUP:
            if event.button == 0:
                self.locked = not self.locked
            elif event.button == 5:
                self.cam.wiper_on()
            elif event.button == 3:
                self.ir_mode += 1
                if self.ir_mode == 3:
                    self.ir_mode = 0

                if self.ir_mode == 0:
                    self.cam.ir_auto()
                elif self.ir_mode == 1:
                    self.cam.ir_on()
                elif self.ir_mode == 2:
                    self.cam.ir_off()
        elif event.type == pygame.JOYHATMOTION:
            hat = event.value
            if hat[0] == 1:
                preset += 1
                self.cam.goto_preset(preset)
            elif hat[0] == -1:
                preset -= 1
                self.cam.goto_preset(preset)
