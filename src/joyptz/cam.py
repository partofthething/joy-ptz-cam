"""
The code to control a camera from a joystick.
"""

import math
import json

from onvif import ONVIFCamera
from onvif.exceptions import ONVIFError


import zeep
import pygame

BLACK = pygame.Color("black")
WHITE = pygame.Color("white")


def zeep_pythonvalue(self, xmlvalue):
    return xmlvalue


def read_config(path):
    with open(path) as f:
        config = json.loads(f.read())
    return config


class TextPrint(object):
    """A little screen for pygame to print to."""

    def __init__(self):
        self.reset()
        self.font = pygame.font.Font(None, 20)

    def tprint(self, screen, textString):
        textBitmap = self.font.render(textString, True, BLACK)
        screen.blit(textBitmap, (self.x, self.y))
        self.y += self.line_height

    def reset(self):
        self.x = 10
        self.y = 10
        self.line_height = 15

    def indent(self):
        self.x += 10

    def unindent(self):
        self.x -= 10


class Camera:
    """The camera"""

    def __init__(self, config):
        self._request = None
        self._ptz = None
        self._token = None
        self._imaging = None
        self._imaging_token = None
        self._cam = None
        self.XMAX = 1
        self.XMIN = -1
        self.YMAX = 1
        self.YMIN = -1
        self._active_vector = [0.0, 0.0, 0.0]
        self._active_focus = 0.0

        self.init_camera(config)

    def loop(self):
        pygame.init()
        screen = pygame.display.set_mode((500, 700))
        pygame.display.set_caption("Joy PTZ")
        done = False
        locked = False
        ir_mode = 0
        preset = 1
        clock = pygame.time.Clock()
        pygame.joystick.init()
        textPrint = TextPrint()
        while not done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    done = True
                elif event.type == pygame.JOYBUTTONDOWN:
                    pass
                elif event.type == pygame.JOYBUTTONUP:
                    if event.button == 0:
                        locked = not locked
                    elif event.button == 5:
                        self.wiper_on()
                    elif event.button == 3:
                        ir_mode += 1
                        if ir_mode == 3:
                            ir_mode = 0

                        if ir_mode == 0:
                            self.ir_auto()
                        elif ir_mode == 1:
                            self.ir_on()
                        elif ir_mode == 2:
                            self.ir_off()
                elif event.type == pygame.JOYHATMOTION:
                    hat = event.value
                    if hat[0] == 1:
                        preset += 1
                        self.goto_preset(preset)
                    elif hat[0] == -1:
                        preset -= 1
                        self.goto_preset(preset)

            screen.fill(WHITE)
            textPrint.reset()
            joystick_count = pygame.joystick.get_count()
            textPrint.indent()
            for i in range(joystick_count):
                axes_vals = []
                joystick = pygame.joystick.Joystick(i)
                joystick.init()
                try:
                    jid = joystick.get_instance_id()
                except AttributeError:
                    # get_instance_id() is an SDL2 method
                    jid = joystick.get_id()
                textPrint.indent()
                name = joystick.get_name()
                textPrint.tprint(screen, "Joystick name: {}".format(name))

                try:
                    guid = joystick.get_guid()
                except AttributeError:
                    # get_guid() is an SDL2 method
                    pass
                else:
                    textPrint.tprint(screen, "GUID: {}".format(guid))

                axes = joystick.get_numaxes()
                textPrint.tprint(screen, "Number of axes: {}".format(axes))
                textPrint.indent()

                for i in range(axes):
                    axis = joystick.get_axis(i)
                    # clear out noise
                    if abs(axis) < 0.005:
                        axis = 0.0
                    axes_vals.append(axis)
                    textPrint.tprint(screen, "Axis {} value: {:>6.3f}".format(i, axis))
                textPrint.unindent()

                buttons = joystick.get_numbuttons()
                textPrint.tprint(screen, "Number of buttons: {}".format(buttons))
                textPrint.indent()

                for i in range(buttons):
                    button = joystick.get_button(i)
                    textPrint.tprint(screen, "Button {:>2} value: {}".format(i, button))

                textPrint.unindent()

                hats = joystick.get_numhats()
                textPrint.tprint(screen, "Number of hats: {}".format(hats))
                textPrint.indent()

                # Hat position. All or nothing for direction, not a float like
                # get_axis(). Position is a tuple of int values (x, y).
                for i in range(hats):
                    hat = joystick.get_hat(i)
                    textPrint.tprint(screen, "Hat {} value: {}".format(i, str(hat)))
                textPrint.unindent()

                textPrint.unindent()

            # now move the camera accordingly!
            # just take the first three axes as x,y, and zoom

            # well ok let's load it, but combine it from the two trigger axes.
            # They both rest at -1 and activate to +1
            # we want left trigger -1 to be zero and +1 to be 1
            # and right trigger -1 to be zero and +1 to be -1
            zoom = -(axes_vals[2] + 1) / 2.0 + (axes_vals[5] + 1) / 2.0

            move_vector = axes_vals[:2] + [zoom]
            move_vector[1] *= -1  # vertical axis flipped on my controller
            mag = math.sqrt(sum([v**2 for v in move_vector]))
            textPrint.tprint(screen, str(move_vector))
            textPrint.tprint(screen, str(mag))
            # mag usually chilling at 0.005
            if not locked:
                if mag < 0.006:
                    textPrint.tprint(screen, "stopped")
                    self.stop()
                else:
                    self.perform_move(move_vector)

            focus = axes_vals[3]
            if abs(focus) > 0.006:
                self.set_focus_change(focus)
            else:
                self.set_focus_change(0.0)

            pygame.display.flip()

            # Limit to this many frames per second.
            clock.tick(5)

        pygame.quit()

    def init_camera(self, config):
        """Set up the camera."""

        mycam = ONVIFCamera(
            config["host"],
            config.get("port", 80),
            config.get("username"),
            config.get("password"),
        )
        self.cam = mycam
        media = mycam.create_media_service()
        ptz = mycam.create_ptz_service()
        self._ptz = ptz

        zeep.xsd.simple.AnySimpleType.pythonvalue = zeep_pythonvalue
        media_profile = media.GetProfiles()[0]

        # Get PTZ configuration options for getting continuous move range
        request = ptz.create_type("GetConfigurationOptions")
        request.ConfigurationToken = media_profile.PTZConfiguration.token
        ptz_configuration_options = ptz.GetConfigurationOptions(request)

        image = mycam.create_imaging_service()
        request = image.create_type("GetImagingSettings")
        request.VideoSourceToken = media_profile.VideoSourceConfiguration.SourceToken
        self._imaging_token = media_profile.VideoSourceConfiguration.SourceToken
        # this info is kind of FYI during debugging/dev
        # current settings
        imaging_settings = image.GetImagingSettings(request)
        # valid options
        imaging_options = image.GetOptions(request)
        self._imaging = image

        # import ipdb
        # ipdb.set_trace()

        # load max ranges
        ranges = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0]
        self.XMAX = ranges.XRange.Max
        self.XMIN = ranges.XRange.Min
        self.YMAX = ranges.YRange.Max
        self.YMIN = ranges.YRange.Min

        request = ptz.create_type("ContinuousMove")
        request.ProfileToken = media_profile.token
        token = {"ProfileToken": media_profile.token}
        self._token = media_profile.token
        ptz.Stop(token)
        if request.Velocity is None:
            request.Velocity = ptz.GetStatus(token).Position
            if not request.Velocity.PanTilt:
                # call GetStatus again to get a new copy
                request.Velocity.PanTilt = ptz.GetStatus(token).Position.Zoom
                request.Velocity.PanTilt.y = 0
            request.Velocity.PanTilt.space = ranges.URI
            request.Velocity.Zoom.space = (
                ptz_configuration_options.Spaces.ContinuousZoomVelocitySpace[0].URI
            )
        self._request = request

    def perform_move(self, vector):
        # if vector isn't that different from the last vector,
        # just leave the existing one to minimize jerkiness
        # of sending too many requests
        dist = math.sqrt(
            sum((x1 - x2) ** 2 for x1, x2 in zip(vector, self._active_vector))
        )
        if dist < 0.05:
            # close enough. don't update anything
            return

        self._active_vector = vector
        x, y, zoom = vector  # assume unit vector

        self._request.Velocity.PanTilt.x = x * self.XMAX
        self._request.Velocity.PanTilt.y = y * self.YMAX
        self._request.Velocity.Zoom.x = zoom
        self._ptz.ContinuousMove(self._request)

    def stop(self):
        self._active_vector = [0.0, 0.0, 0.0]
        self._ptz.Stop({"ProfileToken": self._request.ProfileToken})

    def wiper_on(self):
        """Send an auxiliary command for tt:Wiper|On

        This command is shown in the GetNodes() results on ptz"""
        self._send_aux_cmd("tt:Wiper|On")

    def wiper_off(self):
        """Send an auxiliary command for tt:Wiper|Off"""
        self._send_aux_cmd("tt:Wiper|Off")

    def _send_aux_cmd(self, cmd):
        request = self._ptz.create_type("SendAuxiliaryCommand")
        request.ProfileToken = self._token
        request.AuxiliaryData = cmd
        resp = self._ptz.SendAuxiliaryCommand(request)

    def goto_preset(self, number):
        request = self._ptz.create_type("GotoPreset")
        request.ProfileToken = self._token
        request.PresetToken = str(number)
        try:
            resp = self._ptz.GotoPreset(request)
        except ONVIFError:
            print("Invalid preset {number}")

    def ir_on(self):
        print("IR ON")
        self.set_imaging_setting("IrCutFilter", "OFF")

    def ir_off(self):
        print("IR OFF")
        self.set_imaging_setting("IrCutFilter", "ON")

    def ir_auto(self):
        print("IR auto")
        self.set_imaging_setting("IrCutFilter", "AUTO")

    def set_imaging_setting(self, setting, val):
        request = self._imaging.create_type("SetImagingSettings")
        request.VideoSourceToken = self._imaging_token
        request.ImagingSettings = {setting: val}
        resp = self._imaging.SetImagingSettings(request)

    def set_focus_change(self, val):
        """skycam accepts speeds between -1 and 1."""
        dist = abs(val - self._active_focus)
        if dist < 0.05:
            return
        self._active_focus = val
        request = self._imaging.create_type("Move")
        request.VideoSourceToken = self._imaging_token
        request.Focus = {"Continuous": {"Speed": val}}
        resp = self._imaging.Move(request)
