import argparse

from . import cam

parser = argparse.ArgumentParser(description="Control a camera")
parser.add_argument("--config")
parser.add_argument("camname")
parser.add_argument("control")
args = parser.parse_args()

config = cam.read_config(args.config)[args.camname]
camera = cam.Camera(config)

if args.control.lower() == "joystick":
    from . import joystick

    control_cls = joystick.JoystickController
elif args.control.lower() == "tracker":
    from . import tracking

    control_cls = tracking.TrackedController

control = control_cls(camera, config)
control.loop()
