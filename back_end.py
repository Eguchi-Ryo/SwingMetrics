import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import torch
from ultralytics import YOLO
from google.colab import files

# GPUが使用可能か確認
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# YOLOv8-Pose モデルのロード
model = YOLO("yolov8n-pose.pt")

KEYPOINT_NAMES = {
    0: "nose",
    5: "left_shoulder", 6: "right_shoulder",
    11: "left_hip", 12: "right_hip",
    13: "left_knee", 14: "right_knee"
}

# 骨格リンク定義（描画用）
SKELETON_PAIRS = [
    (5, 6),   # 肩同士
    (5, 11),  # 左肩 -> 左腰
    (6, 12),  # 右肩 -> 右腰
    (11, 12), # 腰同士
    (11, 13), # 左腰 -> 左膝
    (12, 14)  # 右腰 -> 右膝
]

def calculate_angle_2d(p_top, p_bottom):
    """垂直軸（Y軸）に対する傾き角度（度数法）"""
    dx = p_top[0] - p_bottom[0]
    dy = p_bottom[1] - p_top[1]
    radians = np.arctan2(dx, dy)
    return round(float(np.abs(radians * 180.0 / np.pi)), 1)

def analyze_and_draw_video(input_path: str, output_path: str, handness: str = "right"):
    cap = cv2.VideoCapture(input_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # 一時出力用VideoWriter
    temp_output = "temp_output.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

    frames_data = []
    initial_head_x = None
    frame_index = 0

    print("解析と骨格描画を開始します...")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # YOLO 推論 (GPU実行)
        results = model(frame, device=device, verbose=False)
        keypoints_dict = {}
        raw_kpts = None

        if results and len(results[0].keypoints) > 0:
            raw_kpts = results[0].keypoints.xy[0].cpu().numpy()
            for idx, name in KEYPOINT_NAMES.items():
                if idx < len(raw_kpts):
                    keypoints_dict[name] = [float(raw_kpts[idx][0]), float(raw_kpts[idx][1])]

        # アドレス時（初コマ）の頭の基準位置
        if frame_index == 0 and "nose" in keypoints_dict:
            initial_head_x = keypoints_dict["nose"][0]

        # 1. 体幹前傾角の計算
        shoulder = keypoints_dict.get("right_shoulder" if handness == "right" else "left_shoulder")
        hip = keypoints_dict.get("right_hip" if handness == "right" else "left_hip")
        spine_angle = calculate_angle_2d(shoulder, hip) if shoulder and hip else 0.0

        # 2. 頭の軸ブレ（X方向シフト）
        head_shift_x = 0.0
        if initial_head_x is not None and "nose" in keypoints_dict:
            head_shift_x = round(float(keypoints_dict["nose"][0] - initial_head_x), 1)

        # フレーム描画（骨格線 & 関節点）
        if raw_kpts is not None:
            for p1_idx, p2_idx in SKELETON_PAIRS:
                if p1_idx < len(raw_kpts) and p2_idx < len(raw_kpts):
                    pt1 = (int(raw_kpts[p1_idx][0]), int(raw_kpts[p1_idx][1]))
                    pt2 = (int(raw_kpts[p2_idx][0]), int(raw_kpts[p2_idx][1]))
                    if pt1 != (0, 0) and pt2 != (0, 0):
                        cv2.line(frame, pt1, pt2, (0, 255, 0), 3)

            for idx, pt in enumerate(raw_kpts):
                if idx in KEYPOINT_NAMES:
                    pos = (int(pt[0]), int(pt[1]))
                    if pos != (0, 0):
                        cv2.circle(frame, pos, 5, (0, 0, 255), -1)

        # 画面上にリアルタイム数値を描画
        cv2.putText(frame, f"Spine Angle: {spine_angle} deg", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        cv2.putText(frame, f"Head Shift: {head_shift_x} px", (30, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        out.write(frame)

        frames_data.append({
            "frame_index": frame_index,
            "timestamp_sec": round(frame_index / fps, 3),
            "spine_angle": spine_angle,
            "head_shift_x": head_shift_x
        })
        frame_index += 1

    cap.release()
    out.release()

    # Colab上で再生できるようにH.264へ再エンコード
    os.system(f"ffmpeg -y -i {temp_output} -vcodec libx264 {output_path} > /dev/null 2>&1")
    os.remove(temp_output)
    print("解析完了！")

    return frames_data

def calculate_score(frames_data):
    """スコア算出ロジック"""
    spine_angles = [f["spine_angle"] for f in frames_data if f["spine_angle"] > 0]
    head_shifts = [abs(f["head_shift_x"]) for f in frames_data]

    # 前傾維持（40点）
    variance = np.ptp(spine_angles) if spine_angles else 0
    score_spine = max(0, 40 - int(max(0, variance - 3.0) * 3))

    # 軸ブレ（20点）
    max_shift = max(head_shifts) if head_shifts else 0
    score_axis = max(0, 20 - int(max(0, max_shift - 15.0) * 0.5))

    # 暫定基準スコア
    total_score = min(100, score_spine + score_axis + 40)
    return total_score, variance, max_shift


# 1. 手元のスイング動画（.mp4）をアップロード
uploaded = files.upload()
video_filename = list(uploaded.keys())[0]

# 2. 解析と描画動画の作成
output_video = "analyzed_swing.mp4"
frames = analyze_and_draw_video(video_filename, output_video, handness="right")

# 3. スコア判定
score, var, shift = calculate_score(frames)
print(f"\n==============================")
print(f" 総合スコア: {score} / 100 点")
print(f" 前傾角ブレ幅: {var:.1f}°")
print(f" 頭の最大軸ブレ: {shift:.1f} px")
print(f"==============================")



# 前傾角と軸ブレの時系列グラフ描画
timestamps = [f["timestamp_sec"] for f in frames]
angles = [f["spine_angle"] for f in frames]
shifts = [f["head_shift_x"] for f in frames]

plt.figure(figsize=(12, 4))

plt.subplot(1, 2, 1)
plt.plot(timestamps, angles, color="teal", lw=2)
plt.title("Spine Angle over Time")
plt.xlabel("Time (sec)")
plt.ylabel("Angle (deg)")
plt.grid(True)

plt.subplot(1, 2, 2)
plt.plot(timestamps, shifts, color="coral", lw=2)
plt.title("Head Shift (X-axis) over Time")
plt.xlabel("Time (sec)")
plt.ylabel("Shift (px)")
plt.grid(True)

plt.tight_layout()
plt.show()

# 生成動画のブラウザ内再生
from IPython.display import HTML
from base64 import b64encode

mp4 = open(output_video, 'rb').read()
data_url = "data:video/mp4;base64," + b64encode(mp4).decode()
HTML(f"""
<video width=600 controls>
      <source src="{data_url}" type="video/mp4">
</video>
""")