"""Object tracking with OpenCV to steer the camera"""
import sys

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
    tracker_type = tracker_types[2]

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


class TrackedController(Controller):
    """Camera controller that uses opencv image tracking to adjust PTZ"""

    def __init__(self, cam, config):
        super().__init__(cam, config)

        # webcam
        # video = cv2.VideoCapture(0)
        video = self._video = cv2.VideoCapture(config["stream"])

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

    def loop(self):
        while True:
            # Read a new frame
            ok, frame = self._video.read()
            if not ok:
                break

            # Start timer
            timer = cv2.getTickCount()

            # Update tracker
            ok, bbox = self._tracker.update(frame)

            # Calculate Frames per second (FPS)
            fps = cv2.getTickFrequency() / (cv2.getTickCount() - timer)

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

            # Display tracker type on frame
            cv2.putText(
                frame,
                " Tracker",
                (100, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (50, 170, 50),
                2,
            )

            # Display FPS on frame
            cv2.putText(
                frame,
                "FPS : " + str(int(fps)),
                (100, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (50, 170, 50),
                2,
            )

            # Display result
            cv2.imshow("Tracking", frame)

            # Exit if ESC pressed
            k = cv2.waitKey(1) & 0xFF
            if k == 27:
                break
            elif k == ord("r"):
                self._tracker = select_new_roi(frame)
