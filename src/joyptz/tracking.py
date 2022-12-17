"""Object tracking with OpenCV to steer the camera"""
import sys
import math

import cv2

from .controller import Controller

(major_ver, minor_ver, subminor_ver) = (cv2.__version__).split(".")


def select_new_roi(frame):
    """
    Build a new tracker and select a new ROI.

    Used for init and to re-select a new ROI when one is lost.
    """
    tracker_types = [
        "BOOSTING",
        "MIL",
        "KCF",
        "TLD",
        "MEDIANFLOW",
        "GOTURN",
        "MOSSE",
        "CSRT",
    ]
    tracker_type = "MOSSE"
    # MOSSE is pretty impressive and can handle occlusion pretty well.
    # it does swap over to other boats though, which is kinda sad, but
    # better than all the others it seems

    if int(minor_ver) < 3:
        tracker = cv2.Tracker_create(tracker_type)
    else:
        tracker = {
            "BOOSTING": cv2.legacy.TrackerBoosting_create,
            "MIL": cv2.TrackerMIL_create,
            "KCF": cv2.TrackerKCF_create,
            "TLD": cv2.legacy.TrackerTLD_create,
            "MEDIANFLOW": cv2.legacy.TrackerMedianFlow_create,
            "GOTURN": cv2.TrackerGOTURN_create,
            "MOSSE": cv2.legacy.TrackerMOSSE_create,
            "CSRT": cv2.legacy.TrackerCSRT_create,
        }[tracker_type]()
    bbox = cv2.selectROI(frame, False)
    ok = tracker.init(frame, bbox)

    return tracker


WOBBLE_THRESHOLD = 0.02
INITIAL_SPEED = 0.07
SPEED_INCREMENT = 0.25
INITIAL_MAG = 10
PT_UPDATE_INTERVAL_S = 0.5
CLOSE_ENOUGH_FRAC = 0.1
NOT_CLOSE_ENOUGH_FRAC = 0.25
SPEED_ADJUST_FRAC = 0.2


class TrackedController(Controller):
    """Camera controller that uses opencv image tracking to adjust PTZ"""

    def __init__(self, cam, config, log=None):
        super().__init__(cam, config, log)
        self._speed = INITIAL_SPEED
        self._last_mag = INITIAL_MAG

        # webcam
        # video = cv2.VideoCapture(0)
        video = self._video = cv2.VideoCapture(config["cam"]["stream"])

        # Exit if video not opened.
        if not video.isOpened():
            print("Could not open video")
            sys.exit()

        # Read first frame.
        ok, frame = video.read()
        if not ok:
            print("Cannot read video file")
            sys.exit()

        # Define an initial bounding box
        bbox = (287, 23, 86, 320)
        self._tracker = select_new_roi(frame)

        height, width, channels = frame.shape
        self._center = (width // 2, height // 2)

        if config["output"]:
            fourcc = cv2.VideoWriter_fourcc(*"MP4V")
            self._out = cv2.VideoWriter("output.mp4", fourcc, 20.0, (width, height))
        else:
            self._out = None

    def loop(self):
        move_timer = cv2.getTickCount()
        mag = INITIAL_MAG
        closeness = 1.0
        while True:
            # Read a new frame
            ok, frame = self._video.read()
            if not ok:
                break

            tracker_timer = cv2.getTickCount()

            ok, bbox = self._tracker.update(frame)

            tracker_timer2 = cv2.getTickCount()
            tick_freq = cv2.getTickFrequency()
            fps = tick_freq / (tracker_timer2 - tracker_timer)

            if (tracker_timer2 - move_timer) / tick_freq > PT_UPDATE_INTERVAL_S:
                # throttle move vector updates to every x seconds
                move_timer = tracker_timer2
                if closeness > NOT_CLOSE_ENOUGH_FRAC:
                    # only start moving if you're far enough
                    self._adjust_speed(closeness)
                    self._process_move_vector()

            # Draw bounding box
            if ok:
                # Tracking success
                track_center = (
                    int(bbox[0] + bbox[2] // 2),
                    int(bbox[1] + bbox[3] // 2),
                )
                corner1 = (int(bbox[0]), int(bbox[1]))
                corner2 = (int(bbox[0] + bbox[2]), int(bbox[1] + bbox[3]))
                cv2.rectangle(frame, corner1, corner2, (255, 0, 0), 2, 1)
                cv2.arrowedLine(frame, self._center, track_center, (255, 0, 0), 2, 1)
                mag = math.sqrt(
                    (track_center[0] - self._center[0]) ** 2
                    + (track_center[1] - self._center[1]) ** 2
                )

                # [x,y,zoom]

                # need some normalize measure of how 'close' the camera is to the target.
                # will try to have it range between 0 and 1 where 0 is right on,
                # and 1 is on the edge of the cam.
                # compare mag to the bounding box average of width/height
                box_dim = math.sqrt(self._center[0] ** 2 + self._center[1] ** 2)
                closeness = mag / box_dim
                if closeness < CLOSE_ENOUGH_FRAC:
                    self._move_vector = [0, 0, 0]
                    self._speed = INITIAL_SPEED
                    self._process_move_vector()
                    self.log.info("STOP")
                else:
                    # don't always make a unit vector. Keep it slow if the arrow is small
                    # relative to the screen size.
                    self._move_vector = [
                        (track_center[0] - self._center[0]) / (mag) * self._speed,
                        -(track_center[1] - self._center[1]) / (mag) * self._speed,
                        0.0,
                    ]
                    # prevent on-axis wobble
                    if abs(self._move_vector[0]) < WOBBLE_THRESHOLD:
                        self._move_vector[0] = 0.0
                    if abs(self._move_vector[1]) < WOBBLE_THRESHOLD:
                        self._move_vector[1] = 0.0
            else:
                # Tracking failure
                cv2.putText(
                    frame,
                    "Tracking failure detected",
                    (100, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 0, 255),
                    2,
                )
                self._move_vector = [0, 0, 0]
                self._process_move_vector()

            # Display tracker type on frame
            cv2.putText(
                frame,
                (
                    f"FPS: {fps:04.0f}"
                    f" MAG: {mag:04.1f} SPEED: {self._speed:0.2f}"
                    f" CLOSENESS: {closeness:0.2f}"
                    f" MOVE: ({self._move_vector[0]:0.2f},{self._move_vector[1]:0.2f})"
                ),
                (100, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (50, 170, 50),
                2,
            )

            # Display result
            cv2.imshow("Tracking", frame)
            if self._out is not None:
                self._out.write(frame)

            # Exit if ESC pressed
            k = cv2.waitKey(1) & 0xFF
            if k == 27:
                break
            elif k == ord("r"):
                self._tracker = select_new_roi(frame)
                self._speed = INITIAL_SPEED

    def _adjust_speed(self, mag):
        """Adjust the vector scaling to change the speed of the Pan/tilt"""
        if not self._last_mag:
            return

        # only adjust speed if difference crosses a threshold, indicating rapid change
        if abs(mag - self._last_mag) / mag < SPEED_ADJUST_FRAC:
            return

        if mag > self._last_mag:
            self._speed += SPEED_INCREMENT
        elif mag < self._last_mag:
            self._speed -= SPEED_INCREMENT

        # enforce bounds
        if self._speed > 1.0:
            self._speed = 1.0
        elif self._speed < INITIAL_SPEED:
            self._speed = INITIAL_SPEED

        self._last_mag = mag
