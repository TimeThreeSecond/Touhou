"""
配置文件 - 东方冰之勇者记强化学习
基于真实游戏文件: Touhou Hero of Ice Fairy.exe
基于实际战斗画面截图配置
"""
import os
import json
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / "logs"
MODEL_DIR = PROJECT_ROOT / "models"
SCREENSHOT_DIR = PROJECT_ROOT / "screenshots"
CONFIG_FILE = PROJECT_ROOT / "key_config.json"

# 创建必要目录
for d in [LOG_DIR, MODEL_DIR, SCREENSHOT_DIR]:
    d.mkdir(exist_ok=True)

# ==========================================
# 游戏窗口配置（基于真实游戏文件）
# ==========================================
# 实际可执行文件: Touhou Hero of Ice Fairy.exe
# 游戏引擎: Unity
GAME_WINDOW = {
    "exe_name": "Touhou Hero of Ice Fairy.exe",
    "title": "Touhou Hero of Ice Fairy",
    "fallback_titles": ["东方冰之勇者记", "Touhou"],
    # 游戏画面区域（相对于屏幕的坐标，用于截图）
    # 如果不知道具体坐标，可以先运行 utils.py 自动检测
    "region": None,  # None表示自动检测
}

# ==========================================
# 图像处理配置
# ==========================================
VISION = {
    "screen_width": 1920,      # 屏幕分辨率
    "screen_height": 1080,
    "capture_fps": 30,         # 截图帧率
    "resize_width": 320,       # 输入神经网络的图像宽度
    "resize_height": 180,      # 输入神经网络的图像高度
    "grayscale": True,         # 是否转为灰度图
}

# ==========================================
# UI检测区域配置（基于实际战斗画面截图）
# 截图分辨率: 2560x1600（用户提供的截图）
# 这些坐标需要根据实际游戏窗口分辨率按比例缩放
# ==========================================
UI_DETECTION = {
    # 玩家雪花血量区域（左上角）
    # 画面显示6个蓝色雪花图标表示血量
    "health_snowflakes": {
        "x_start": 0.035, "x_end": 0.20,
        "y_start": 0.03, "y_end": 0.10,
        "max_health": 6,           # 最大6个雪花
        "color_hint": "blue",      # 蓝色雪花
    },
    # 体力条区域（雪花下方黄色条）
    # 注意: 不同分辨率下位置可能有偏移，区域设置较宽以覆盖各种情况
    "stamina_bar": {
        "x_start": 0.06, "x_end": 0.25,
        "y_start": 0.11, "y_end": 0.16,
        "color_hint": "yellow",    # 黄色体力条
    },
    # Boss血条区域（右上角红色长条）
    # 注意: 包含白色边框，区域设置较宽
    "boss_health_bar": {
        "x_start": 0.58, "x_end": 0.88,
        "y_start": 0.06, "y_end": 0.13,
        "color_hint": "red",       # 红色血条
    },
    # Boss阶段文字区域（Stage 1/6）
    "boss_stage": {
        "x_start": 0.65, "x_end": 0.75,
        "y_start": 0.09, "y_end": 0.14,
    },
    # 符卡就绪状态区域（左侧READY图标）
    "spell_ready": {
        "x_start": 0.01, "x_end": 0.12,
        "y_start": 0.22, "y_end": 0.40,
        "color_hint": "ready_text", # READY字样
    },
    # 战斗时长区域（左下角）
    "battle_timer": {
        "x_start": 0.02, "x_end": 0.18,
        "y_start": 0.88, "y_end": 0.97,
    },
}

# ==========================================
# 动作空间配置
# ==========================================
ACTION_SPACE = {
    # 移动方向（8方向 + 静止）
    "move_directions": 9,  # 0:静止, 1-8:八个方向
    # 是否冲刺 (LeftShift)
    "use_dash": True,
    # 是否跳跃 (Space)
    "use_jump": True,
    # 是否释放左符卡 (Q)
    "use_spell_left": True,
    # 是否释放右符卡 (E)
    "use_spell_right": True,
    # 是否发射子弹 (长按鼠标左键)
    "use_shoot": True,
}

# ==========================================
# 奖励配置（基于实际战斗画面设计）
# ==========================================
# 画面元素:
# - 左上角6个雪花 = 玩家血量
# - 雪花下方黄条 = 体力条（冲刺消耗）
# - 右上角红条 = Boss血量
# - Stage 1/6 = Boss有6条命
REWARD = {
    # ---- 基础奖励 ----
    "alive_reward": 0.05,          # 每帧存活奖励（鼓励生存）
    "time_penalty": -0.005,        # 时间惩罚（鼓励快速击杀）

    # ---- 血量相关 ----
    "health_loss_penalty": -5.0,   # 每损失1个雪花（被击中）的惩罚
    "health_gain_reward": 2.0,     # 恢复血量的奖励（如有回血机制）

    # ---- Boss伤害奖励 ----
    "boss_damage_reward": 2.0,     # 对Boss造成伤害的基础奖励
    "boss_stage_clear_reward": 15.0, # 击败Boss一条命（Stage增加）的奖励
    "boss_kill_reward": 100.0,     # 彻底击败Boss的奖励

    # ---- 攻击相关 ----
    "shoot_reward": 0.02,          # 每帧持续射击的微小奖励（鼓励输出）
    "spell_use_reward": 0.5,       # 使用符卡的奖励（鼓励技能使用）

    # ---- 体力管理 ----
    "stamina_low_penalty": -0.1,   # 体力过低时的惩罚（无法冲刺）
    "stamina_consume_penalty": -0.01, # 消耗体力的微小惩罚（鼓励节约）

    # ---- 位置相关（鼓励靠近Boss攻击）----
    "distance_penalty_factor": -0.01, # 距离Boss过远的惩罚系数
}

# ==========================================
# 训练配置
# ==========================================
TRAIN = {
    "algorithm": "PPO",        # PPO / DQN / A2C
    "total_timesteps": 1000000,
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.01,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
    "save_freq": 10000,
    "log_freq": 1000,
    "device": "auto",          # auto / cpu / cuda
}

# ==========================================
# 模型配置
# ==========================================
MODEL = {
    "cnn_layers": [
        (32, 8, 4),  # (out_channels, kernel_size, stride)
        (64, 4, 2),
        (64, 3, 1),
    ],
    "fc_layers": [512, 256],
}

# ==========================================
# 按键映射
# ==========================================
# 东方冰之勇者记操作说明（基于游戏内设置截图）:
# - 移动: W/A/S/D (主按键) / 方向键 (副按键)
# - 跳跃: Space (主按键) / Numpad1 (副按键)
# - 冲刺: LeftShift (主按键) / RightButton (副按键)
# - 释放右符卡: E (主按键) / Numpad3 (副按键)
# - 释放左符卡: Q (主按键) / Numpad2 (副按键)
# - 发射子弹: 长按鼠标左键 (用户补充)

DEFAULT_KEY_MAPPING = {
    "up": "w",          # 向上移动 (主按键)
    "down": "s",        # 向下移动 (主按键)
    "left": "a",        # 向左移动 (主按键)
    "right": "d",       # 向右移动 (主按键)
    "jump": "space",    # 跳跃 (主按键)
    "dash": "shift",    # 冲刺 (主按键: LeftShift)
    "spell_right": "e", # 释放右符卡 (主按键)
    "spell_left": "q",  # 释放左符卡 (主按键)
    "shoot": "left",    # 发射子弹: 长按鼠标左键
}

# 加载用户自定义按键配置
def load_key_mapping():
    """加载按键配置，如果存在用户配置文件则使用用户的"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            empty_keys = [k for k, v in user_config.items() if not v]
            if empty_keys:
                print(f"[警告] 以下按键未配置: {', '.join(empty_keys)}")
            else:
                print(f"[信息] 已加载自定义按键配置: {CONFIG_FILE}")
            return user_config
        except Exception as e:
            print(f"[警告] 加载按键配置失败: {e}")

    print("[信息] 使用默认按键配置")
    return DEFAULT_KEY_MAPPING.copy()

# 当前使用的按键映射
KEY_MAPPING = load_key_mapping()

# 保存按键配置
def save_key_mapping(mapping):
    """保存按键配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"[信息] 按键配置已保存: {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"[错误] 保存按键配置失败: {e}")
        return False
