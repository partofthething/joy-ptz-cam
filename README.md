# Joystick PTZ ONVIF camera controller

This lets you use a joystick to control a PTZ camera that supports
the ONVIF protocol via Python.

Special thanks to pygame and https://github.com/RichardoMrMu/python-onvif 
for helping turn the concepts into reality.

## Quick Start

* Clone this repo
* Make a venv
* Run `python setup.py install`
* Make a file called `credentials.json` and add you camera username/password do it

Example credentials file in JSON format

```
{
    "cam1": {
        "username": "admin",
        "password": "mypass",
        "port": "80",
        "host": "camera1.local"
    },
    "cam2": {
        "username": "admin",
        "password": "mypass1",
        "port": "8080",
        "host": "camera2.local"
    }
}
```

* Run the program:

```
$ python joyptz --config credentials.json cam1
```

* Enjoy


