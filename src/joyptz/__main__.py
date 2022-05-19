import argparse
import json

from . import cam

parser = argparse.ArgumentParser(description='Control a camera')
parser.add_argument('--config')
parser.add_argument('camname')
args = parser.parse_args()

with open(args.config) as f:
    config = json.loads(f.read())

camera = cam.Camera(config[args.camname])
camera.loop()

