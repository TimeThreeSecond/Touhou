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
    # fallback 包含中英文，但实际匹配后会通过进程路径验证排除误匹配
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
# 基准截图分辨率: 1600×900（无黑边，全屏/无边框全屏）
# 使用相对坐标（百分比），自动适配不同分辨率
# 参考UI检测报告: 东方冰之勇者记_UI检测报告.md
# ==========================================
UI_DETECTION = {
    # 玩家雪花血量区域（左上角）
    # 实际位置(1600×900): x=128~462, y=50~114
    # 左侧有等级钻石图标(x=50~106)，已排除在区域外
    # 6个蓝色雪花，间距不均匀(58~62px)，单图标约60×55px
    "health_snowflakes": {
        "x_start": 0.08, "x_end": 0.29,
        "y_start": 0.055, "y_end": 0.127,
        "max_health": 6,
        "color_hint": "blue",
    },
    # 体力条区域（雪花下方金黄色条）
    # 实际位置(1600×900): x=145~464, y=128~139
    # 总槽宽约310px, 填充色RGB≈(244,200,91), 两端直角
    "stamina_bar": {
        "x_start": 0.09, "x_end": 0.29,
        "y_start": 0.14, "y_end": 0.16,
        "color_hint": "yellow",
    },
    # Boss血条区域（右上角红色长条）
    # 实际位置(1600×900): x=955~1372, y=86~125
    # 左侧尖角/斜切，右侧平齐，含白色边框
    # 红色填充RGB≈(255,0,48)~(255,119,123)，空槽为白色
    "boss_health_bar": {
        "x_start": 0.595, "x_end": 0.86,
        "y_start": 0.095, "y_end": 0.14,
        "color_hint": "red",
    },
    # Boss阶段/技能文字区域（血条下方）
    # 实际位置(1600×900): Stage 1/6红色字 x=960~1150, y=95~115
    # Boss名称底板 x=1185~1382, y=48~73
    "boss_stage": {
        "x_start": 0.60, "x_end": 0.86,
        "y_start": 0.05, "y_end": 0.13,
    },
    # 符卡就绪状态区域（左侧纵向排列）
    # 实际位置(1600×900): x=31~179, y=170~368
    # 2张卡上下排列，单卡约70×90px
    # READY文字RGB≈(255,240,224)黄色描边字
    "spell_ready": {
        "x_start": 0.019, "x_end": 0.112,
        "y_start": 0.19, "y_end": 0.41,
        "color_hint": "ready_text",
    },
    # 战斗时长区域（左下角）
    # 实际位置(1600×900): x=57~260, y=824~843
    # 浅灰色字RGB≈(194,188,193)，透明背景
    "battle_timer": {
        "x_start": 0.035, "x_end": 0.165,
        "y_start": 0.915, "y_end": 0.94,
    },
    # 物品栏（右下角）— 仅用于参考，当前未用于状态检测
    # 实际位置(1600×900): x=1294~1539, y=820~866
    # 7个横向等距槽位，圆角矩形边框
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
    "spell_use_reward": -0.05,     # 使用符卡的微小惩罚（防止无脑spam）

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
