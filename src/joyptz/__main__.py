import argparse

from . import cam
from . import joystick

parser = argparse.ArgumentParser(description='Control a camera')
parser.add_argument('--config')
parser.add_argument('camname')
args = parser.parse_args()

config = cam.read_config(args.config)
camera = cam.Camera(config[args.camname])

control = joystick.Controller(camera)
control.loop()
