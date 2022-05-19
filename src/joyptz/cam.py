"""
The code to control a camera from a joystick.
"""

import math

from onvif import ONVIFCamera
import zeep
import pygame

BLACK = pygame.Color("black")
WHITE = pygame.Color("white")


def zeep_pythonvalue(self, xmlvalue):
    return xmlvalue


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
        self.XMAX = 1
        self.XMIN = -1
        self.YMAX = 1
        self.YMIN = -1
        self._active_vector = [0.0, 0.0, 0.0]

        self.init_camera(config)

    def loop(self):
        pygame.init()
        screen = pygame.display.set_mode((500, 700))
        pygame.display.set_caption("Joy PTZ")
        done = False
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
                    pass

            screen.fill(WHITE)
            textPrint.reset()
            joystick_count = pygame.joystick.get_count()
            textPrint.indent()
            for i in range(joystick_count):
                vector = []
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
                    vector.append(axis)
                    textPrint.tprint(screen, "Axis {} value: {:>6.3f}".format(i, axis))
                textPrint.unindent()

                textPrint.unindent()

            # now move the camera accordingly!
            # just take the first three axes as x,y, and zoom

            # well ok let's load it, but combine it from the two trigger axes.
            # They both rest at -1 and activate to +1
            # we want left trigger -1 to be zero and +1 to be 1
            # and right trigger -1 to be zero and +1 to be -1
            zoom = -(vector[2] + 1) / 2.0 + (vector[5] + 1) / 2.0

            vector = vector[:2] + [zoom]
            vector[1] *= -1  # vertical axis flipped on my controller
            mag = math.sqrt(sum([v**2 for v in vector]))
            textPrint.tprint(screen, str(vector))
            textPrint.tprint(screen, str(mag))
            # mag usually chilling at 0.005
            if mag < 0.006:
                textPrint.tprint(screen, "stopped")
                self.stop()
            else:
                self.perform_move(vector)

            pygame.display.flip()

            # Limit to this many frames per second.
            clock.tick(5)

        pygame.quit()

    def init_camera(self, config):
        """Set up the camera."""

        mycam = ONVIFCamera(
            config["host"], config["port"], config["username"], config["password"]
        )
        media = mycam.create_media_service()
        ptz = mycam.create_ptz_service()

        zeep.xsd.simple.AnySimpleType.pythonvalue = zeep_pythonvalue
        media_profile = media.GetProfiles()[0]

        # Get PTZ configuration options for getting continuous move range
        request = ptz.create_type("GetConfigurationOptions")
        request.ConfigurationToken = media_profile.PTZConfiguration.token
        ptz_configuration_options = ptz.GetConfigurationOptions(request)

        # load max ranges
        ranges = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0]
        self.XMAX = ranges.XRange.Max
        self.XMIN = ranges.XRange.Min
        self.YMAX = ranges.YRange.Max
        self.YMIN = ranges.YRange.Min

        request = ptz.create_type("ContinuousMove")
        request.ProfileToken = media_profile.token
        token = {"ProfileToken": media_profile.token}
        ptz.Stop(token)

        if request.Velocity is None:
            request.Velocity = ptz.GetStatus(token).Position
            request.Velocity.PanTilt.space = ranges.URI
            request.Velocity.Zoom.space = (
                ptz_configuration_options.Spaces.ContinuousZoomVelocitySpace[0].URI
            )
        self._request = request
        self._ptz = ptz

    def perform_move(self, vector):
        # if vector isn't that different from the last vector,
        # just leave the existing one to minimize jerkiness
        # of sending too many requests
        dist = math.sqrt(
            sum((x1 - x2) ** 2 for x1, x2 in zip(vector, self._active_vector))
        )
        if dist < 0.1:
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
