import math
import logging


class Controller:
    """
    General camera controller

    Intended to be reusable from a variety of control methods.
    """

    def __init__(self, cam, config, log=None):
        self.cam = cam
        self.config = config
        self.ir_mode = 0
        self.locked = False
        self._move_vector = [0, 0, 0]
        self._focus = 0.0
        self._speed = 1.0
        self.log = log or logging.getLogger()

    def _process_move_vector(self):
        mag = math.sqrt(sum([v**2 for v in self._move_vector]))
        self.log.info(str(self._move_vector))
        self.log.info(str(mag))
        # mag usually chilling at 0.005
        if not self.locked:
            if mag < 0.006:
                self.log.info("stopped")
                self.cam.stop()
            else:
                self.cam.perform_move(self._move_vector)

        if abs(self._focus) > 0.006:
            self.cam.set_focus_change(self._focus)
        else:
            self.cam.set_focus_change(0.0)
