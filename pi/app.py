#!/usr/bin/env python3
"""Raspberry Pi webcam: person presence and two-hand heart via FireBeetle BLE."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import time
from latest_camera import LatestCamera
from pathlib import Path

from gesture_core import (CommandPolicy, GestureState, PI3_TIMING, Hand, Observation, Point,
                          Pose, classify_heart, crop_candidate_poses, distance, heart_crop_boxes)

LOG = logging.getLogger("gesture-pump")
DEVICE_NAME = "Campfire-FireBeetle"
SERVICE_UUID = "A6E40001-B5A3-F393-E0A9-E50E24DCCA9E"
COMMAND_UUID = "A6E40002-B5A3-F393-E0A9-E50E24DCCA9E"
COMMAND_NAMES = {0: "person absent", 1: "person present",
                 4: "two-hand heart ON", 5: "heart OFF", 6: "STOP ALL"}


def y_up(landmark) -> Point:
    return Point(float(landmark.x), 1.0 - float(landmark.y))


class WebcamProcessor:
    def __init__(self, camera: str, width: int, height: int, fps: int,
                 hand_model: Path, pose_model: Path, mirror: bool,
                 open_camera: bool = True, max_people: int = 6,
                 cpu_threads: int = 4, profile: str = "full"):
        import cv2
        import mediapipe as mp

        # Explicit XNNPACK threading: the Pi 3 otherwise uses one inference
        # thread. Independent models may run concurrently on the same image.
        class CpuOptions(mp.tasks.BaseOptions):
            def to_pb2(options):
                proto = super().to_pb2()
                proto.acceleration.Clear()
                proto.acceleration.xnnpack.num_threads = cpu_threads
                return proto

        self.cv2 = cv2
        self.mp = mp
        self.camera_arg = camera
        self.width, self.height, self.fps = width, height, fps
        self.mirror = mirror
        self.max_people = max_people
        self.profile = profile
        self.capture = None
        self.camera_reader = None
        self.last_timestamp_ms = 0
        self.tracked_pose = None
        vision = mp.tasks.vision
        # At least four hands, so ANY visible person's heart counts even when
        # --max-people 1 limits pose tracking for speed on the Pi 3B+.
        self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=CpuOptions(model_asset_path=str(hand_model)),
            running_mode=vision.RunningMode.VIDEO, num_hands=max(4, max_people * 2),
            min_hand_detection_confidence=.5, min_hand_presence_confidence=.5,
            min_tracking_confidence=.5))
        # IMAGE mode keeps independent left/right crops from corrupting the
        # tracking state of the full-frame VIDEO landmarker.
        self.crop_hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=CpuOptions(model_asset_path=str(hand_model)),
            running_mode=vision.RunningMode.VIDEO if profile == "pi3" else vision.RunningMode.IMAGE, num_hands=1,
            min_hand_detection_confidence=.5))
        self.pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=CpuOptions(model_asset_path=str(pose_model)),
            running_mode=vision.RunningMode.VIDEO, num_poses=max_people,
            min_pose_detection_confidence=.5, min_pose_presence_confidence=.5,
            min_tracking_confidence=.5))
        self.people = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
            base_options=CpuOptions(model_asset_path=str(pose_model.parent / 'efficientdet_lite0.tflite')),
            category_allowlist=['person', 'dog', 'cat', 'bird', 'horse', 'cow', 'sheep', 'bear'],
            score_threshold=.35, max_results=max_people + 8))
        self.faces = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=CpuOptions(model_asset_path=str(pose_model.parent / 'blaze_face_short_range.tflite')),
            min_detection_confidence=.5))
        self.roi_hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=CpuOptions(model_asset_path=str(hand_model)),
            running_mode=vision.RunningMode.VIDEO if profile == "pi3" else vision.RunningMode.IMAGE,
            num_hands=1 if profile == "pi3" else 2,
            min_hand_detection_confidence=.5, min_hand_presence_confidence=.5))
        self.skin = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=CpuOptions(model_asset_path=str(pose_model.parent / 'selfie_multiclass_256x256.tflite')),
            output_confidence_masks=True)) if profile == "full" else None
        if open_camera:
            self.open_camera()

    def open_camera(self) -> None:
        cv2 = self.cv2
        source = int(self.camera_arg) if self.camera_arg.isdecimal() else self.camera_arg
        cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"Cannot open USB camera {self.camera_arg}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.capture = cap
        self.camera_reader = LatestCamera(cap)
        LOG.info("Camera opened: %s (requested %sx%s @ %s fps)",
                 self.camera_arg, self.width, self.height, self.fps)

    def read(self) -> tuple[Observation, object]:
        if self.camera_reader is None:
            self.open_camera()
        try:
            frame, captured_at = self.camera_reader.read()
        except Exception:
            self.camera_reader.close()
            self.camera_reader = self.capture = None
            raise
        if self.mirror:
            frame = self.cv2.flip(frame, 1)
        return self.analyze(frame, captured_at), frame

    def analyze(self, frame, captured_at: float | None = None) -> Observation:
        cv2, mp = self.cv2, self.mp
        if captured_at is None:
            captured_at = time.monotonic()
        timestamp_ms = max(int(captured_at * 1000), self.last_timestamp_ms + 1)
        self.last_timestamp_ms = timestamp_ms
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        tracked = []
        if self.profile == "pi3" and self.tracked_pose is not None:
            tracked = self._split_heart_hands(frame, self.tracked_pose)
            if classify_heart(tracked) is None:
                tracked = []
                self.tracked_pose = None
        pose_result = None
        hand_result = None if tracked else self.hands.detect_for_video(image, timestamp_ms)
        objects = self.people.detect(image).detections
        faces = self.faces.detect(image).detections
        preliminary_heart = (classify_heart([
            self._hand_from_marks(marks, y_up)
            for marks in hand_result.hand_landmarks if len(marks) >= 21])
            if hand_result is not None and self.profile == "pi3" else None)
        if not tracked and not preliminary_heart and (
                self.profile == "full" or hand_result.hand_landmarks or any(
                    d.categories[0].category_name == 'person' and d.categories[0].score >= .5
                    for d in objects)):
            pose_result = self.pose.detect_for_video(image, timestamp_ms)
        people = [d for d in objects if d.categories[0].category_name == 'person'
                  and d.categories[0].score >= .5][:self.max_people]
        person_candidates = [d for d in objects if d.categories[0].category_name == 'person'][:self.max_people]
        animals = [d.bounding_box for d in objects if d.categories[0].category_name != 'person']
        # Face models can occasionally mistake a dog's face for a human face.
        # Veto only overlapping animal regions, not people elsewhere in frame.
        def outside_animals(face, offset_x=0, offset_y=0):
            b = face.bounding_box
            x, y = offset_x+b.origin_x+b.width/2, offset_y+b.origin_y+b.height/2
            return not any(a.origin_x <= x <= a.origin_x+a.width and
                           a.origin_y <= y <= a.origin_y+a.height for a in animals)
        face_present = any(f.categories[0].score >= .7 and outside_animals(f)
                           for f in faces)

        # Pose keypoints alone can hallucinate shoulders on animals or tents.
        # Require a spatially matching person detector, or independent face/hand evidence.
        detected_person = False
        bodies = []
        people_count = 0
        for landmarks in (pose_result.pose_landmarks if pose_result else []):
            shoulders = (landmarks[11], landmarks[12])
            h, w = frame.shape[:2]
            matching_person = any(
                d.bounding_box.origin_x <= sum(p.x for p in shoulders) * w / 2 <= d.bounding_box.origin_x + d.bounding_box.width
                and d.bounding_box.origin_y <= sum(p.y for p in shoulders) * h / 2 <= d.bounding_box.origin_y + d.bounding_box.height
                for d in people)
            if matching_person and all(getattr(p, "visibility", 1.0) >= .45 for p in shoulders):
                detected_person = True
                people_count += 1
            needed_indices = (11, 12, 15, 16)
            if all(getattr(landmarks[i], "visibility", 1.0) >= .40 for i in needed_indices):
                bodies.append(Pose(*(y_up(landmarks[i]) for i in needed_indices)))

        hands: list[Hand] = list(tracked)
        for marks in (hand_result.hand_landmarks if hand_result else []):
            if len(marks) < 21:
                continue
            hands.append(self._hand_from_marks(marks, lambda z: y_up(z)))

        # Two hands touching in a heart frequently collapse into one result
        # in the full image. Split around pose wrists and try once per side.
        if classify_heart(hands) is None:
            for candidate in crop_candidate_poses(bodies):
                split = self._split_heart_hands(frame, candidate)
                if classify_heart(split) == "two-hand":
                    hands = split
                    if self.profile == "pi3":
                        self.tracked_pose = candidate
                    break
        # Small people and touching hands need local image detail. Bounded
        # crops reuse the hand model; a crop itself never authorizes a pump.
        if self.profile == "full" and classify_heart(hands) is None:
            h, w = frame.shape[:2]
            boxes = []
            for d in people:
                b = d.bounding_box
                if b.width < w * .7:
                    boxes.append((max(0., (b.origin_x - .1*b.width)/w),
                                  max(0., (b.origin_y - .05*b.height)/h),
                                  min(1., (b.origin_x + 1.1*b.width)/w),
                                  min(1., (b.origin_y + b.height)/h)))
            # Close-up heart with shoulders outside the image: separate the
            # left/right hands, without relying on a body pose.
            boxes.extend(((0., 0., .58, 1.), (.42, 0., 1., 1.)))
            for box in boxes[:self.max_people + 2]:
                found = self._hands_in_box(frame, box)
                for hand in found:
                    if not any(distance(hand.wrist, old.wrist) < .035 for old in hands):
                        hands.append(hand)
                if classify_heart(hands):
                    break
        h, w = frame.shape[:2]
        hands = [hand for hand in hands if not any(
            a.origin_x <= hand.middle_mcp.x*w <= a.origin_x+a.width and
            a.origin_y <= (1-hand.middle_mcp.y)*h <= a.origin_y+a.height
            for a in animals)]
        # A distant person's face may only resolve inside their detected box.
        if not (detected_person or face_present or hands):
            h, w = frame.shape[:2]
            for d in person_candidates:
                b = d.bounding_box
                x0, y0 = max(0, b.origin_x), max(0, b.origin_y)
                x1, y1 = min(w, b.origin_x+b.width), min(h, b.origin_y+b.height)
                if b.height > 1.4*b.width:
                    y1 = min(y1, y0 + int(.65*b.height))
                crop = frame[y0:y1, x0:x1]
                if not crop.size:
                    continue
                local_faces = self.faces.detect(mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))).detections
                if any(outside_animals(f, x0, y0) for f in local_faces):
                    face_present = True
                    break
        if person_candidates and not (detected_person or face_present or hands):
            # Pose-guided head crops recover small faces without searching
            # arbitrary background patches. Require a stronger face score.
            h, w = frame.shape[:2]
            for body in bodies[:self.max_people]:
                left, right = body.left_shoulder, body.right_shoulder
                span = abs(left.x-right.x)*w
                sx, sy = (left.x+right.x)*w/2, (1-(left.y+right.y)/2)*h
                x0, x1 = max(0,int(sx-.65*span)), min(w,int(sx+.65*span))
                y0, y1 = max(0,int(sy-1.5*span)), min(h,int(sy+.15*span))
                crop = frame[y0:y1,x0:x1]
                if min(crop.shape[:2], default=0) < 12:
                    continue
                local_faces = self.faces.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))).detections
                if any(f.categories[0].score >= .7 and outside_animals(f,x0,y0) for f in local_faces):
                    face_present = True
                    break
        # At very close range shoulders may be outside the picture, but
        # reliably detected hands still mean a person is visible.
        detected_person = detected_person or face_present or bool(hands)
        if not detected_person and self.skin is not None:
            # Close hands/forearms need not expose face, shoulders or all 21
            # hand joints. A learned human-part mask supplements presence only;
            # it never supplies hand landmarks or authorizes pumping.
            mask_result = self.skin.segment(image)
            skin = (mask_result.confidence_masks[2].numpy_view() +
                    mask_result.confidence_masks[3].numpy_view()).squeeze() > .8
            unmasked_skin = skin.copy()
            mh, mw = skin.shape
            h, w = frame.shape[:2]
            for a in animals:
                x0, y0 = max(0, int(a.origin_x*mw/w)), max(0, int(a.origin_y*mh/h))
                x1 = min(mw, int((a.origin_x+a.width)*mw/w))
                y1 = min(mh, int((a.origin_y+a.height)*mh/h))
                skin[y0:y1, x0:x1] = False
            detected_person = bool(skin.mean() >= .02)
            if not detected_person and unmasked_skin.mean() >= .02:
                # A real hand can overlap an animal or be misclassified as
                # one. For presence only, require agreement between independent
                # human-part segmentation and hand joints at the same pixels.
                for box in ((0.,0.,.58,1.), (.42,0.,1.,1.)):
                    for candidate in self._hands_in_box(frame, box, padding=0.):
                        points = (candidate.middle_mcp, candidate.index_mcp,
                                  candidate.index_pip, candidate.index_tip, candidate.thumb_tip)
                        supported = sum(p is not None and 0 <= p.x < 1 and 0 < p.y <= 1
                                        and bool(unmasked_skin[int((1-p.y)*mh),int(p.x*mw)])
                                        for p in points)
                        if supported >= 4:
                            detected_person = True
                            break
                    if detected_person:
                        break
        if self.profile == "pi3" and self.tracked_pose is not None:
            if classify_heart(hands):
                p = self.tracked_pose
                wrists = sorted((hand.wrist for hand in hands), key=lambda pt: pt.x)
                self.tracked_pose = Pose(p.left_shoulder, p.right_shoulder, wrists[0], wrists[-1])
            else:
                self.tracked_pose = None
        return Observation(captured_at, detected_person, bodies[0] if bodies else None,
                           hands, completed_at=time.monotonic(), people_count=people_count)

    @staticmethod
    def _hand_from_marks(marks, project) -> Hand:
        return Hand(wrist=project(marks[0]), middle_mcp=project(marks[9]),
                    index_tip=project(marks[8]), thumb_tip=project(marks[4]),
                    index_mcp=project(marks[5]), index_pip=project(marks[6]))

    def _hands_in_box(self, frame, box, padding: float = .15) -> list[Hand]:
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = box
        x0, y0, x1, y1 = int(x0*w), int(y0*h), int(x1*w), int(y1*h)
        crop = frame[y0:y1, x0:x1]
        if min(crop.shape[:2], default=0) < 24:
            return []
        # Leave context around clipped wrists; landmarks map back to the
        # unpadded source coordinates, so duplicate hands remain detectable.
        pad = round(max(crop.shape[:2]) * padding)
        crop = self.cv2.copyMakeBorder(crop, pad, pad, pad, pad, self.cv2.BORDER_CONSTANT)
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                              data=self.cv2.cvtColor(crop, self.cv2.COLOR_BGR2RGB))
        result = self.roi_hands.detect(image)
        def project(mark):
            return Point((x0-pad + mark.x*(x1-x0+2*pad))/w,
                         1-(y0-pad + mark.y*(y1-y0+2*pad))/h)
        return [self._hand_from_marks(marks, project) for marks in result.hand_landmarks]

    def _split_heart_hands(self, frame, pose: Pose) -> list[Hand]:
        boxes = heart_crop_boxes(pose)
        if boxes is None:
            return []
        cv2, mp = self.cv2, self.mp
        height, width = frame.shape[:2]
        expected_wrists = sorted((pose.left_wrist, pose.right_wrist), key=lambda p: p.x)
        shoulder_span = distance(pose.left_shoulder, pose.right_shoulder)
        result: list[Hand] = []
        for side, (box, expected) in enumerate(zip(boxes, expected_wrists)):
            x0, y0, x1, y1 = box
            px0, py0 = int(x0 * width), int(y0 * height)
            px1, py1 = int(x1 * width), int(y1 * height)
            crop = frame[py0:py1, px0:px1]
            if crop.size == 0:
                return []
            image = mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            if self.profile == "pi3":
                runner = self.crop_hands if side == 0 else self.roi_hands
                # One consistent video tracker per side; never mix two crops
                # into the same tracking stream.
                stamp = max(int(time.monotonic()*1000), self.last_timestamp_ms)
                key = "_left_crop_stamp" if side == 0 else "_right_crop_stamp"
                stamp = max(stamp, getattr(self, key, -1) + 1)
                setattr(self, key, stamp)
                found = runner.detect_for_video(image, stamp).hand_landmarks
            else:
                found = self.crop_hands.detect(image).hand_landmarks
            if not found:
                return []

            def project(mark):
                return Point((px0 + mark.x * (px1 - px0)) / width,
                             1 - (py0 + mark.y * (py1 - py0)) / height)

            hand = self._hand_from_marks(found[0], project)
            if abs(hand.wrist.x - expected.x) > .4 * shoulder_span:
                return []
            result.append(hand)
        if distance(result[0].wrist, result[1].wrist) < .2 * shoulder_span:
            return []
        return result

    def close(self) -> None:
        if self.camera_reader is not None:
            self.camera_reader.close()
        self.hands.close()
        self.crop_hands.close()
        self.pose.close()
        self.people.close()
        self.faces.close()
        self.roi_hands.close()
        if self.skin is not None:
            self.skin.close()


async def camera_loop(processor: WebcamProcessor, state: GestureState,
                      stop: asyncio.Event, preview: bool, debug: bool) -> None:
    cv2 = processor.cv2
    last_report = time.monotonic()
    last_slow_report = -100.0
    processed_frames = 0
    while not stop.is_set():
        try:
            observation, frame = await asyncio.to_thread(processor.read)
            state.observe(observation)
            processed_frames += 1
            report_now = time.monotonic()
            if report_now - observation.time > state.timing.max_inference_age and report_now - last_slow_report >= 2:
                LOG.warning("CV frame age %.2fs exceeds pump limit; lower resolution or --max-people",
                            report_now - observation.time)
                last_slow_report = report_now
            if debug and report_now - last_report >= 1.0:
                fps = processed_frames / (report_now - last_report)
                LOG.info("CV: person=%s heart=%s pose=%s hands=%s people=%s actual_fps=%.1f frame_age=%.2fs raw_heart=%s confirmed=%d green=%s yellow=%s",
                         state.person, state.heart_kind, observation.pose is not None,
                         len(observation.hands), observation.people_count, fps, report_now - observation.time,
                         classify_heart(observation.hands), state.positive_heart_frames,
                         state.safe_person(report_now), state.safe_heart(report_now))
                last_report, processed_frames = report_now, 0
            if preview:
                display_time = time.monotonic()
                heart = state.heart_kind if state.safe_heart(display_time) else "-"
                status = f"person={state.safe_person(display_time)}  heart={heart}"
                cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            .65, (0, 255, 255), 2)
                cv2.imshow("Raspberry Pi gesture pump - q to quit", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    stop.set()
        except Exception as exc:
            LOG.error("Camera/CV error: %s; outputs will time out and camera will retry", exc)
            await asyncio.sleep(1)
    if preview:
        cv2.destroyAllWindows()


async def write_commands(client, commands: list[int], dry_run: bool) -> None:
    # Send release before a potentially slow presence write/acknowledgement.
    if 5 in commands and 6 not in commands:
        commands = [5] + [command for command in commands if command != 5]
    for command in commands:
        if dry_run:
            LOG.info("DRY RUN -> %s (%s)", command, COMMAND_NAMES[command])
        else:
            await client.write_gatt_char(COMMAND_UUID, bytes([command]), response=True)
            if command in (0, 1, 6):
                LOG.info("BLE -> %s (%s)", command, COMMAND_NAMES[command])


async def sender_loop(state: GestureState, stop: asyncio.Event,
                      dry_run: bool, address: str | None) -> None:
    policy = CommandPolicy(state)
    if dry_run:
        while not stop.is_set():
            await write_commands(None, policy.commands(time.monotonic()), True)
            await asyncio.sleep(.05)
        return

    from bleak import BleakClient, BleakScanner

    while not stop.is_set():
        client = None
        try:
            device = address or await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=8)
            if device is None:
                LOG.warning("BLE device %s not found; retrying", DEVICE_NAME)
                await asyncio.sleep(1)
                continue
            client = BleakClient(device, timeout=10)
            await client.connect()
            if client.services.get_characteristic(COMMAND_UUID) is None:
                raise RuntimeError("Connected BLE device does not have the expected command characteristic")
            LOG.info("FireBeetle connected via BLE")
            policy.reset_transport()
            # A previous run must never leave a pump request active.
            await write_commands(client, [6], False)
            last_heart_output = None
            while client.is_connected and not stop.is_set():
                commands = policy.commands(time.monotonic())
                await write_commands(client, commands, False)
                for command in commands:
                    if command in (4, 5) and command != last_heart_output:
                        LOG.info("BLE heart output -> %s", COMMAND_NAMES[command])
                        last_heart_output = command
                await asyncio.sleep(.05)
            if not client.is_connected:
                LOG.warning("FireBeetle disconnected; firmware stops all outputs")
        except Exception as exc:
            LOG.warning("BLE unavailable: %s; reconnecting", exc)
        finally:
            if client is not None and client.is_connected:
                try:
                    await write_commands(client, [6], False)
                except Exception as exc:
                    LOG.warning("Could not send shutdown command: %s", exc)
                try:
                    await client.disconnect()
                except Exception:
                    pass
            policy.reset_transport()
        if not stop.is_set():
            await asyncio.sleep(1)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", default="0", help="USB camera index or /dev/videoX (default: 0)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--max-people", type=int, choices=range(1, 7), default=6,
                        help="Maximum people for pose/hand search (default: 6)")
    parser.add_argument("--cpu-threads", type=int, choices=range(1, 5), default=4,
                        help="XNNPACK threads per model (default: 4)")
    parser.add_argument("--profile", choices=("full", "pi3"), default="full",
                        help="pi3 skips expensive exhaustive recovery; use visible upper body and chest-level heart")
    parser.add_argument("--hand-model", type=Path, default=root / "models/hand_landmarker.task")
    parser.add_argument("--pose-model", type=Path, default=root / "models/pose_landmarker_lite.task")
    parser.add_argument("--ble-address", help="Optional FireBeetle BLE address; default: scan by name")
    parser.add_argument("--preview", action="store_true", help="Show live picture; requires a desktop session")
    parser.add_argument("--no-mirror", action="store_true", help="Do not mirror webcam image")
    parser.add_argument("--dry-run", action="store_true", help="Log commands without connecting to FireBeetle")
    parser.add_argument("--debug", action="store_true", help="Log CV status every two seconds")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    for model in (args.hand_model, args.pose_model,
                  args.pose_model.parent / 'efficientdet_lite0.tflite',
                  args.pose_model.parent / 'blaze_face_short_range.tflite',
                  args.pose_model.parent / 'selfie_multiclass_256x256.tflite'):
        if not model.is_file():
            raise SystemExit(f"Missing model: {model}\nRun python download_models.py first.")
    state = GestureState(PI3_TIMING if args.profile == "pi3" else None)
    stop = asyncio.Event()
    LOG.info("Control timing: inference<=%.2fs result_gap<=%.2fs frame_age<=%.2fs; start=%d frames; negative grace=%.2fs",
             state.timing.max_inference_age, state.timing.max_result_gap,
             state.timing.max_frame_age, state.timing.confirm_frames, state.timing.release_grace)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    processor = WebcamProcessor(args.camera, args.width, args.height, args.fps,
                               args.hand_model, args.pose_model, not args.no_mirror,
                               max_people=args.max_people, cpu_threads=args.cpu_threads,
                               profile=args.profile)
    camera_task = asyncio.create_task(camera_loop(processor, state, stop, args.preview, args.debug))
    sender_task = asyncio.create_task(sender_loop(state, stop, args.dry_run, args.ble_address))
    try:
        await stop.wait()
    finally:
        await asyncio.gather(camera_task, sender_task)
        processor.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        pass
