"""Startup code"""
import argparse
import json

from . import cam


def read_config(path):
    """Read config file."""
    with open(path, "r", encoding="utf-8") as config_file:
        config_data = json.loads(config_file.read())
    return config_data


parser = argparse.ArgumentParser(description="Control a camera")
parser.add_argument("--config", help="Path to configuration file.")
parser.add_argument("--output", default=False, action="store_true")
parser.add_argument(
    "camname",
    help="The camera name (should correspond with an entry in the config file)",
)
parser.add_argument(
    "control",
    choices=["joystick", "tracker", "network"],
    help="Which control mode you want to use",
)
args = parser.parse_args()

config = read_config(args.config)

config["output"] = args.output
config["cam"] = config[args.camname]  # general name e.g. to get stream info

camera = cam.Camera(config[args.camname])

if args.control.lower() == "joystick":
    from . import joystick

    ControlCls = joystick.JoystickController
elif args.control.lower() == "tracker":
    from . import tracking

    ControlCls = tracking.TrackedController
elif args.control.lower() == "network":
    from . import mqtt

    ControlCls = mqtt.NetworkController
else:
    raise ValueError(f"Invalid control arg {args.control}")

control = ControlCls(camera, config)
control.loop()
