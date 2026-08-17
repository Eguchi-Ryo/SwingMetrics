import os
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from app.services.baseball_kinematics import calculate_baseball_kinematics

# YOLOv8-Pose モデル
MODEL = YOLO("yolov8n-pose.pt")

# 骨格描画用リンク定義 (COCO 17キーポイント)
SKELETON_CONNECTIONS = [
    (5, 6),   # 左肩 - 右肩
    (5, 7),   # 左肩 - 左肘
    (7, 9),   # 左肘 - 左手首
    (6, 8),   # 右肩 - 右肘
    (8, 10),  # 右肘 - 右手首
    (5, 11),  # 左肩 - 左腰
    (6, 12),  # 右肩 - 右腰
    (11, 12), # 左腰 - 右腰
    (11, 13), # 左腰 - 左膝
    (13, 15), # 左膝 - 左足首
    (12, 14), # 右腰 - 右膝
    (14, 16), # 右膝 - 右足首
]

def draw_single_person_skeleton(frame, keypoints, color=(96, 165, 250)):
    """最大面積の打者1名のみに絞って骨格線と関節を描画"""
    # 骨格リンク描画
    for p1_idx, p2_idx in SKELETON_CONNECTIONS:
        pt1 = keypoints[p1_idx]
        pt2 = keypoints[p2_idx]
        if pt1[0] > 0 and pt1[1] > 0 and pt2[0] > 0 and pt2[1] > 0:
            cv2.line(frame, (int(pt1[0]), int(pt1[1])), (int(pt2[0]), int(pt2[1])), color, 2, cv2.LINE_AA)

    # 関節ポイント描画
    for idx, pt in enumerate(keypoints):
        if pt[0] > 0 and pt[1] > 0:
            # 手首は目立つように強調 (緑色)
            pt_color = (52, 211, 153) if idx in (9, 10) else (255, 255, 255)
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 4, pt_color, -1, cv2.LINE_AA)
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 5, color, 1, cv2.LINE_AA)


def analyze_batting_video(video_path, output_dir=None, progress_callback=None):
    """
    動画から最大面積の人物（打者）のみを特定して抽出・解析・描画する
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if output_dir is None:
        output_dir = video_path.parent
    else:
        output_dir = Path(output_dir)

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if total_frames <= 0:
        cap.release()
        raise ValueError("Invalid video file (0 frames).")

    temp_output = output_dir / f"temp_{video_path.name}"
    final_output = output_dir / f"annotated_{video_path.name}"
    
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(temp_output), fourcc, fps, (width, height))

    frames_keypoints = []
    hand_speeds = []
    prev_wrists = None

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = MODEL(frame, verbose=False)
        annotated_frame = frame.copy()
        keypoints_detected = False

        if results and len(results[0].keypoints) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()  # [N, 4] -> x1, y1, x2, y2
            kp_data = results[0].keypoints.xy.cpu().numpy()  # [N, 17, 2]

            if len(boxes) > 0 and len(kp_data) > 0:
                # 各人物のバウンディングボックス面積（幅 × 高さ）を算出
                areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
                # 一番大きく写っている人物のインデックスを特定
                target_person_idx = int(np.argmax(areas))

                person_kp = kp_data[target_person_idx] # [17, 2]
                frames_keypoints.append(person_kp)
                keypoints_detected = True

                # 打者のみに骨格を描画
                draw_single_person_skeleton(annotated_frame, person_kp)

                # 手首移動速度のトラッキング
                cur_wrists = (person_kp[9] + person_kp[10]) / 2.0
                if prev_wrists is not None:
                    speed = np.linalg.norm(cur_wrists - prev_wrists)
                    hand_speeds.append(speed)
                else:
                    hand_speeds.append(0.0)
                prev_wrists = cur_wrists

        if not keypoints_detected:
            frames_keypoints.append(frames_keypoints[-1] if frames_keypoints else np.zeros((17, 2)))
            hand_speeds.append(0.0)

        out.write(annotated_frame)
        frame_idx += 1

        if progress_callback and total_frames > 0:
            progress = int((frame_idx / total_frames) * 85)
            progress_callback(progress)

    cap.release()
    out.release()

    # Webブラウザ再生用 H.264 (libx264) 変換
    try:
        ffmpeg_cmd = f'ffmpeg -y -i "{temp_output}" -vcodec libx264 -pix_fmt yuv420p -movflags +faststart "{final_output}" -loglevel error'
        ret_code = os.system(ffmpeg_cmd)
        if ret_code != 0:
            temp_output.replace(final_output)
        else:
            if temp_output.exists():
                temp_output.unlink()
    except Exception:
        temp_output.replace(final_output)

    # 手首速度が最大になるコマをインパクトと自動特定
    impact_frame_idx = int(np.argmax(hand_speeds)) if hand_speeds else int(total_frames * 0.6)

    # 打撃幾何学指標の計算
    kinematics = calculate_baseball_kinematics(frames_keypoints, impact_idx=impact_frame_idx)
    kinematics["annotated_video_url"] = f"/videos/{final_output.name}"
    kinematics["impact_frame"] = impact_frame_idx

    if progress_callback:
        progress_callback(100)

    return kinematics