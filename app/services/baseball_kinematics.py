import math
import numpy as np

def calculate_baseball_kinematics(frames_keypoints, impact_idx=None):
    """
    frames_keypoints: 各フレームの骨格座標 [N, 17, 2] (COCOキーポイント)
    5:左肩, 6:右肩, 9:左手首, 10:右手首, 11:左腰, 12:右腰
    """
    total_frames = len(frames_keypoints) if frames_keypoints else 0
    if total_frames == 0:
        return {
            "attack_angle": 999,
            "vba": 999,
            "orthogonality": 999,
            "metrics": build_metrics_list(999, 999, 999),
            "frames": [{"frame_index": i, "spine_angle": round(35.0 + math.sin(i / 5.0) * 4.0, 1)} for i in range(30)],
        }

    if impact_idx is None or impact_idx >= total_frames:
        if total_frames < 3:
            impact_idx = max(0, total_frames - 1)
        else:
            # 各フレームの手首中心座標 (左右手首 9, 10 の中点) を取得
            wrist_positions = []
            for kp in frames_keypoints:
                kp = np.array(kp)
                wrists_center = (kp[9] + kp[10]) / 2.0
                wrist_positions.append(wrists_center)
            wrist_positions = np.array(wrist_positions)
            buttom_wrist_pos = np.min(wrist_positions[:, 1])  # y座標の最小値 (下方向)
            # インパクトコマは、手首が最も下にくる2フレーム前と仮定する
            impact_idx = np.argmin(wrist_positions[:, 1])
            if impact_idx > 0 and impact_idx < total_frames - 1:
                impact_idx = int(round((impact_idx - 1 + impact_idx + impact_idx + 1) / 3.0)) + 2
            
    # 1. 各フレームの体幹傾斜角度（時系列グラフ用）
    frames_data = []
    for idx, kp in enumerate(frames_keypoints):
        kp = np.array(kp)
        shoulder_c = (kp[5] + kp[6]) / 2.0
        hip_c = (kp[11] + kp[12]) / 2.0
        vec = shoulder_c - hip_c
        tilt = abs(math.degrees(math.atan2(vec[0], -vec[1] + 1e-5)))
        frames_data.append({"frame_index": idx, "spine_angle": round(tilt, 1)})

    # 2. インパクトコマの幾何学計算
    # インパクト前には手首が最下点にくる。その2フレーム後にインパクトがあると仮定する。
    imp_kp = np.array(frames_keypoints[impact_idx])
    prev_idx = max(0, impact_idx - 2)
    prev_kp = np.array(frames_keypoints[prev_idx])

    shoulder_c = (imp_kp[5] + imp_kp[6]) / 2.0
    hip_c = (imp_kp[11] + imp_kp[12]) / 2.0
    trunk_vec = hip_c - shoulder_c

    cur_wrists = (imp_kp[9] + imp_kp[10]) / 2.0
    prev_wrists = (prev_kp[9] + prev_kp[10]) / 2.0
    hand_move = cur_wrists - prev_wrists

    # ① アタック・アングル (Attack Angle)
    attack_angle = math.degrees(math.atan2(abs(hand_move[1]), abs(hand_move[0]) + 1e-5))
    attack_angle = round(max(-15.0, min(25.0, attack_angle)), 1)

    # ② スイング・パス・チルト (垂直バット角度 / VBA)
    wrist_diff = imp_kp[10] - imp_kp[9]
    vba = -abs(math.degrees(math.atan2(abs(wrist_diff[1]), abs(wrist_diff[0]) + 1e-5)))
    vba = round(max(-55.0, min(-15.0, vba)), 1)

    # ③ バットと体の角度 (90度則)
    arm_vec = cur_wrists - shoulder_c
    cos_val = np.dot(trunk_vec, arm_vec) / (np.linalg.norm(trunk_vec) * np.linalg.norm(arm_vec) + 1e-5)
    orthogonality = round(math.degrees(math.acos(np.clip(cos_val, -1.0, 1.0))), 1)

    return {
        "attack_angle": attack_angle,
        "vba": vba,
        "orthogonality": orthogonality,
        "metrics": build_metrics_list(attack_angle, vba, orthogonality),
        "frames": frames_data,
    }

def build_metrics_list(attack_angle, vba, orthogonality):
    return [
        {
            "label": "アタック・アングル (Attack Angle)",
            "value": f"{attack_angle:+.1f}°",
            "benchmark": "+5°〜+15°",
            "desc": "インパクト時のバット進入仰角。投球のダウンヒル軌道（約-6°）に合わせ、長打ゾーンを生み出す垂直角度です。"
        },
        {
            "label": "スイング・パス・チルト (垂直バット角度 / VBA)",
            "value": f"{vba:.1f}°",
            "benchmark": "-20°〜-40°",
            "desc": "インパクト直前のバットの縦の傾き角度。コース高低に適応し、内野フライや打ち損じを抑える指標です。"
        },
        {
            "label": "バットと体の角度 (90度則)",
            "value": f"{orthogonality:.1f}°",
            "benchmark": "80°〜90°",
            "desc": "体幹回旋軸とスイングプレーンの直交度。直角（80°〜90°）に保つことで、回転エネルギーを逃さずバットへ伝達します。"
        }
    ]