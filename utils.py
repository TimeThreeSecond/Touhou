"""
工具函数 - 截图、按键模拟、窗口检测、状态提取
基于真实游戏文件: Touhou Hero of Ice Fairy.exe
基于实际战斗画面截图实现状态检测
"""
import time
from time import sleep

import cv2
import numpy as np
import mss
from pathlib import Path

from config import GAME_WINDOW, VISION, KEY_MAPPING, UI_DETECTION


class GameCapture:
    """游戏画面捕获"""

    def __init__(self, region=None):
        self.sct = mss.MSS()
        self.region = region or self._find_game_window()
        if self.region is None:
            print("[警告] 未找到游戏窗口，请手动设置 region")
            print("[提示] 方法1: 运行 key_config.py 检测游戏窗口")
            print("[提示] 方法2: 在 config.py 中手动设置 GAME_WINDOW['region']")

    def _find_game_window_pywin32(self):
        """使用 pywin32 查找游戏窗口"""
        import win32gui

        result = {}

        def enum_callback(hwnd, extra):
            nonlocal result
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                for t in [GAME_WINDOW["title"]] + GAME_WINDOW["fallback_titles"]:
                    if t.lower() in title.lower():
                        rect = win32gui.GetWindowRect(hwnd)
                        left, top, right, bottom = rect
                        result = {
                            "left": left,
                            "top": top,
                            "width": right - left,
                            "height": bottom - top,
                            "title": title,
                            "hwnd": hwnd,
                        }
                        return False
            return True

        win32gui.EnumWindows(enum_callback, None)
        return result

    def _find_game_window_ctypes(self):
        """使用 ctypes 备用方案查找游戏窗口（无需 pywin32）"""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        result = {}

        # 回调函数类型
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM
        )

        def enum_callback(hwnd, lParam):
            if result:
                return True  # 已找到，继续枚举

            # 检查窗口是否可见
            if not user32.IsWindowVisible(hwnd):
                return True

            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value

            for t in [GAME_WINDOW["title"]] + GAME_WINDOW["fallback_titles"]:
                if t.lower() in title.lower():
                    rect = wintypes.RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        result["left"] = rect.left
                        result["top"] = rect.top
                        result["width"] = rect.right - rect.left
                        result["height"] = rect.bottom - rect.top
                        result["title"] = title
                        result["hwnd"] = hwnd
                    return False
            return True

        callback = EnumWindowsProc(enum_callback)
        user32.EnumWindows(callback, 0)
        return result

    def _find_game_window(self):
        """自动查找游戏窗口（优先 pywin32，失败则使用 ctypes 备用）"""
        result = None

        # 尝试 pywin32
        try:
            result = self._find_game_window_pywin32()
            if result:
                print("[信息] 使用 pywin32 找到游戏窗口")
        except Exception as e:
            print(f"[信息] pywin32 检测失败: {e}")

        # 尝试 ctypes 备用方案
        if not result:
            try:
                result = self._find_game_window_ctypes()
                if result:
                    print("[信息] 使用 ctypes 备用方案找到游戏窗口")
            except Exception as e:
                print(f"[信息] ctypes 备用方案也失败: {e}")

        if result:
            print(f"[信息] 找到游戏窗口:")
            print(f"  标题: {result['title']}")
            print(f"  位置: ({result['left']}, {result['top']})")
            print(f"  大小: {result['width']}x{result['height']}")
            # 返回客户端区域（去掉标题栏和边框）
            # 这里简单估算标题栏高度约30-40px
            title_height = 40
            return {
                "left": result["left"],
                "top": result["top"] + title_height,
                "width": result["width"],
                "height": result["height"] - title_height,
            }

        print("[错误] 无法自动检测游戏窗口")
        return None

    def capture(self):
        """捕获游戏画面"""
        if self.region is None:
            return None

        try:
            screenshot = self.sct.grab(self.region)
            img = np.array(screenshot)
            # BGRA -> BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"[错误] 截图失败: {e}")
            return None

    def preprocess(self, img):
        """预处理图像用于神经网络输入"""
        if img is None:
            return None

        # 调整大小
        img = cv2.resize(img, (VISION["resize_width"], VISION["resize_height"]))

        # 灰度化（可选）
        if VISION["grayscale"]:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = np.expand_dims(img, axis=0)  # (1, H, W)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = np.transpose(img, (2, 0, 1))  # (C, H, W)

        # 归一化到 [0, 1]
        img = img.astype(np.float32) / 255.0

        return img

    def get_state(self):
        """获取处理后的状态"""
        raw = self.capture()
        if raw is None:
            return None, None
        processed = self.preprocess(raw)
        return processed, raw

    def save_screenshot(self, filename=None):
        """保存截图"""
        raw = self.capture()
        if raw is not None:
            if filename is None:
                filename = f"screenshot_{int(time.time())}.png"
            path = Path("screenshots") / filename
            cv2.imwrite(str(path), raw)
            print(f"[信息] 截图已保存: {path}")


class GameController:
    """游戏控制器 - 模拟按键"""

    def __init__(self):
        self.current_keys = set()
        self._setup_input()

    def _setup_input(self):
        """设置输入库"""
        try:
            import pydirectinput
            self.input_lib = "pydirectinput"
            self.pydirectinput = pydirectinput
            self.pydirectinput.FAILSAFE = False
            print("[信息] 使用 pydirectinput 进行输入模拟")
        except ImportError:
            try:
                import pyautogui
                self.input_lib = "pyautogui"
                self.pyautogui = pyautogui
                self.pyautogui.FAILSAFE = False
                print("[信息] 使用 pyautogui 进行输入模拟")
            except ImportError:
                print("[错误] 未安装 pydirectinput 或 pyautogui")
                print("[提示] 请运行: pip install pydirectinput")
                self.input_lib = None

    def _is_mouse_button(self, key):
        """判断是否为鼠标按键"""
        return key in ["left", "right", "middle"]

    def press_key(self, key):
        """按下按键（保持）"""
        if self.input_lib is None:
            return

        if key not in self.current_keys:
            try:
                if self._is_mouse_button(key):
                    if self.input_lib == "pydirectinput":
                        self.pydirectinput.mouseDown(button=key)
                    else:
                        self.pyautogui.mouseDown(button=key)
                else:
                    if self.input_lib == "pydirectinput":
                        self.pydirectinput.keyDown(key)
                    else:
                        self.pyautogui.keyDown(key)
                self.current_keys.add(key)
            except Exception as e:
                print(f"[错误] 按下按键失败 {key}: {e}")

    def release_key(self, key):
        """释放按键"""
        if self.input_lib is None:
            return

        if key in self.current_keys:
            try:
                if self._is_mouse_button(key):
                    if self.input_lib == "pydirectinput":
                        self.pydirectinput.mouseUp(button=key)
                    else:
                        self.pyautogui.mouseUp(button=key)
                else:
                    if self.input_lib == "pydirectinput":
                        self.pydirectinput.keyUp(key)
                    else:
                        self.pyautogui.keyUp(key)
                self.current_keys.discard(key)
            except Exception as e:
                print(f"[错误] 释放按键失败 {key}: {e}")

    def release_all(self):
        """释放所有按键"""
        for key in list(self.current_keys):
            self.release_key(key)

    def _check_key_config(self):
        """检查按键是否已配置"""
        required_keys = ["up", "down", "left", "right"]
        empty_keys = [k for k, v in KEY_MAPPING.items() if not v and k in required_keys]
        if empty_keys:
            print(f"[错误] 以下关键按键未配置: {', '.join(empty_keys)}")
            print("[提示] 请先运行 key_config.py 配置游戏按键")
            return False
        return True

    def execute_action(self, action_dict):
        """
        执行动作
        action_dict: {
            "direction": int (0-8, 0=静止, 1=上, 2=右上, ..., 8=左上)
            "dash": bool      # 冲刺
            "jump": bool      # 跳跃
            "spell_left": bool   # 释放左符卡
            "spell_right": bool  # 释放右符卡
            "shoot": bool     # 射击
        }
        """
        if self.input_lib is None:
            return

        if not self._check_key_config():
            return

        # 方向映射
        direction_map = {
            0: [],
            1: [KEY_MAPPING["up"]],
            2: [KEY_MAPPING["up"], KEY_MAPPING["right"]],
            3: [KEY_MAPPING["right"]],
            4: [KEY_MAPPING["down"], KEY_MAPPING["right"]],
            5: [KEY_MAPPING["down"]],
            6: [KEY_MAPPING["down"], KEY_MAPPING["left"]],
            7: [KEY_MAPPING["left"]],
            8: [KEY_MAPPING["up"], KEY_MAPPING["left"]],
        }

        # 释放之前的方向键
        for key in [KEY_MAPPING["up"], KEY_MAPPING["down"],
                    KEY_MAPPING["left"], KEY_MAPPING["right"]]:
            self.release_key(key)

        # 按下新的方向键
        direction = action_dict.get("direction", 0)
        keys_to_press = direction_map.get(direction, [])
        for key in keys_to_press:
            if key:
                self.press_key(key)

        # 冲刺键
        dash_key = KEY_MAPPING.get("dash", "")
        if dash_key:
            if action_dict.get("dash", False):
                self.press_key(dash_key)
            else:
                self.release_key(dash_key)

        # 跳跃键
        jump_key = KEY_MAPPING.get("jump", "")
        if jump_key:
            if action_dict.get("jump", False):
                self.press_key(jump_key)
            else:
                self.release_key(jump_key)

        # 左符卡
        spell_left_key = KEY_MAPPING.get("spell_left", "")
        if spell_left_key:
            if action_dict.get("spell_left", False):
                self.press_key(spell_left_key)
            else:
                self.release_key(spell_left_key)

        # 右符卡
        spell_right_key = KEY_MAPPING.get("spell_right", "")
        if spell_right_key:
            if action_dict.get("spell_right", False):
                self.press_key(spell_right_key)
            else:
                self.release_key(spell_right_key)

        # 发射子弹（长按鼠标左键）
        shoot_key = KEY_MAPPING.get("shoot", "")
        if shoot_key:
            if action_dict.get("shoot", False):
                self.press_key(shoot_key)
            else:
                self.release_key(shoot_key)

    def reset(self):
        """重置所有按键"""
        self.release_all()


class StateExtractor:
    """
    状态提取器 - 从游戏画面中提取关键状态信息
    基于实际战斗画面截图实现

    画面UI元素:
    - 左上角: 6个蓝色雪花 = 玩家血量, 下方黄色条 = 体力
    - 右上角: 红色长条 = Boss血量, Stage 1/6 = Boss阶段
    - 左侧中部: 两个READY符卡图标

    支持分辨率自适应:
    - 基准分辨率: 2560x1600 (用户提供的原始截图)
    - 自动缩放检测阈值以适应不同窗口大小
    """

    # 基准分辨率（阈值基于此分辨率标定）
    BASE_WIDTH = 2560
    BASE_HEIGHT = 1600

    def __init__(self):
        self.prev_health = None
        self.prev_boss_health = None
        self.prev_boss_stage = None
        self.prev_stamina = None
        self.frame_count = 0
        self.health_history = []
        self.boss_health_history = []

    def _get_scale_factor(self, img):
        """计算当前图像相对于基准分辨率的缩放因子"""
        h, w = img.shape[:2]
        area_scale = (w * h) / (self.BASE_WIDTH * self.BASE_HEIGHT)
        # 面积缩放是线性比例的平方，但UI元素通常是按宽度或高度线性缩放
        # 这里使用几何平均，使面积阈值更合理
        linear_scale = ((w / self.BASE_WIDTH) * (h / self.BASE_HEIGHT)) ** 0.5
        return max(linear_scale, 0.3)  # 最小缩放因子，防止过小分辨率导致阈值过低

    def _get_region(self, img, region_config):
        """获取图像中的相对区域"""
        h, w = img.shape[:2]
        x1 = int(region_config["x_start"] * w)
        y1 = int(region_config["y_start"] * h)
        x2 = int(region_config["x_end"] * w)
        y2 = int(region_config["y_end"] * h)
        return img[y1:y2, x1:x2]

    def detect_health(self, img):
        """
        检测玩家血量（左上角雪花数量）
        返回: 当前雪花数 (0-6)
        """
        region = self._get_region(img, UI_DETECTION["health_snowflakes"])
        if region.size == 0:
            return None

        scale = self._get_scale_factor(img)

        # 转换到HSV颜色空间检测蓝色雪花
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # 蓝色范围 (根据雪花颜色调整)
        lower_blue = np.array([90, 50, 150])
        upper_blue = np.array([130, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # 形态学操作去除噪点
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 筛选符合雪花大小的轮廓（阈值根据分辨率自适应）
        snowflakes = 0
        min_area = int(15 * scale)
        max_area = int(200 * scale)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                snowflakes += 1

        # 限制最大值为6
        snowflakes = min(snowflakes, UI_DETECTION["health_snowflakes"]["max_health"])
        return snowflakes

    def detect_stamina(self, img):
        """
        检测体力条（雪花下方黄色条）
        返回: 体力比例 (0.0 - 1.0)
        """
        region = self._get_region(img, UI_DETECTION["stamina_bar"])
        if region.size == 0:
            return None

        # 转换到HSV检测黄色/金黄色
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # 放宽黄色范围以覆盖不同显示器下的色差
        lower_yellow = np.array([15, 60, 60])
        upper_yellow = np.array([45, 255, 255])
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

        # 计算黄色像素占比
        total_pixels = mask.shape[1]  # 宽度
        if total_pixels == 0:
            return None

        # 对每一列检测是否有黄色（降低阈值，体力条很细）
        yellow_cols = np.sum(mask > 0, axis=0)
        # 阈值: 列高度的 5%（体力条通常只占区域高度的一小部分）
        yellow_count = np.sum(yellow_cols > mask.shape[0] * 0.05)

        ratio = yellow_count / total_pixels
        return min(max(ratio, 0.0), 1.0)

    def detect_boss_health(self, img):
        """
        检测Boss血量（右上角红色条）
        返回: Boss血量比例 (0.0 - 1.0)
        """
        region = self._get_region(img, UI_DETECTION["boss_health_bar"])
        if region.size == 0:
            return None

        # 转换到HSV检测红色
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # 放宽红色范围以覆盖深红、暗红等不同色调
        lower_red1 = np.array([0, 50, 40])
        upper_red1 = np.array([15, 255, 255])
        lower_red2 = np.array([165, 50, 40])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = mask1 | mask2

        # 计算红色像素占比
        total_pixels = mask.shape[1]
        if total_pixels == 0:
            return None

        # 方法: 统计包含红色像素的列数（降低阈值，血条可能很细）
        red_cols = np.sum(mask > 0, axis=0)
        # 阈值: 列高度的 3%（血条可能只有几像素高）
        red_count = np.sum(red_cols > mask.shape[0] * 0.03)

        ratio = red_count / total_pixels
        # 由于血条区域包含白色边框等，实际比例可能需要补偿
        # 但此处直接返回检测到的红色列占比
        return min(max(ratio, 0.0), 1.0)

    def detect_boss_stage(self, img):
        """
        检测Boss阶段（Stage X/6）
        返回: 当前阶段 (1-6) 或 None
        简化实现：基于右上角文字区域的颜色/亮度变化
        """
        region = self._get_region(img, UI_DETECTION["boss_stage"])
        if region.size == 0:
            return None

        # 将区域转为灰度，检测白色文字
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        # 二值化检测亮文字
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # 检测是否有足够的白色像素（有文字存在）
        white_ratio = np.sum(binary > 0) / binary.size
        if white_ratio < 0.01:
            return None

        # 简化的阶段检测：基于Boss血条突降判断阶段转换
        # 实际阶段数通过历史血量推断
        if self.prev_boss_health is not None and len(self.boss_health_history) > 5:
            # 如果Boss血量从很低突然恢复到很高，说明进入了新阶段
            avg_recent = np.mean(self.boss_health_history[-5:])
            if avg_recent < 0.1 and self.prev_boss_health > 0.8:
                if self.prev_boss_stage is not None:
                    return min(self.prev_boss_stage + 1, 6)

        # 默认返回之前检测到的阶段或1
        return self.prev_boss_stage if self.prev_boss_stage is not None else 1

    def detect_spells_ready(self, img):
        """
        检测符卡是否就绪（左侧READY图标）
        返回: (left_ready, right_ready) bool元组
        """
        region = self._get_region(img, UI_DETECTION["spell_ready"])
        if region.size == 0:
            return (False, False)

        scale = self._get_scale_factor(img)

        # 检测READY文字（黄色/金色/橙色）
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # 放宽范围以覆盖不同亮度下的READY文字
        lower_ready = np.array([10, 50, 80])
        upper_ready = np.array([50, 255, 255])
        mask = cv2.inRange(hsv, lower_ready, upper_ready)

        # 将区域分为上下两部分（Q符卡在上，E符卡在下）
        h = mask.shape[0]
        top_half = mask[:h//2, :]
        bottom_half = mask[h//2:, :]

        # 像素计数阈值根据分辨率自适应（大幅降低，READY文字可能很小）
        pixel_threshold = max(int(20 * scale), 5)
        left_ready = np.sum(top_half > 0) > pixel_threshold
        right_ready = np.sum(bottom_half > 0) > pixel_threshold

        return (left_ready, right_ready)

    def extract(self, img):
        """
        从原始图像提取游戏状态
        返回包含所有检测信息的字典
        """
        state = {
            "health": None,           # 玩家雪花血量 (0-6)
            "stamina": None,          # 体力比例 (0.0-1.0)
            "boss_health": None,      # Boss血量比例 (0.0-1.0)
            "boss_stage": None,       # Boss阶段 (1-6)
            "spell_left_ready": False,  # 左符卡就绪
            "spell_right_ready": False, # 右符卡就绪
            "health_changed": 0,      # 血量变化 (+增加, -减少)
            "boss_health_changed": 0.0, # Boss血量变化
            "boss_stage_changed": 0,  # Boss阶段变化
            "is_alive": True,         # 是否存活
            "frame_count": self.frame_count,
        }

        if img is None:
            return state

        self.frame_count += 1

        try:
            # 检测玩家血量
            health = self.detect_health(img)
            if health is not None:
                state["health"] = health
                if self.prev_health is not None:
                    state["health_changed"] = health - self.prev_health
                self.prev_health = health
                self.health_history.append(health)
                if len(self.health_history) > 30:
                    self.health_history.pop(0)

            # 检测体力
            stamina = self.detect_stamina(img)
            if stamina is not None:
                state["stamina"] = stamina
                self.prev_stamina = stamina

            # 检测Boss血量
            boss_health = self.detect_boss_health(img)
            if boss_health is not None:
                state["boss_health"] = boss_health
                if self.prev_boss_health is not None:
                    state["boss_health_changed"] = self.prev_boss_health - boss_health
                self.prev_boss_health = boss_health
                self.boss_health_history.append(boss_health)
                if len(self.boss_health_history) > 30:
                    self.boss_health_history.pop(0)

            # 检测Boss阶段
            boss_stage = self.detect_boss_stage(img)
            if boss_stage is not None:
                state["boss_stage"] = boss_stage
                if self.prev_boss_stage is not None:
                    state["boss_stage_changed"] = boss_stage - self.prev_boss_stage
                self.prev_boss_stage = boss_stage

            # 检测符卡就绪状态
            left_ready, right_ready = self.detect_spells_ready(img)
            state["spell_left_ready"] = left_ready
            state["spell_right_ready"] = right_ready

            # 判断是否存活
            if health is not None:
                state["is_alive"] = health > 0

        except Exception as e:
            print(f"[警告] 状态提取出错: {e}")

        return state

    def reset(self):
        """重置历史状态"""
        self.prev_health = None
        self.prev_boss_health = None
        self.prev_boss_stage = None
        self.prev_stamina = None
        self.frame_count = 0
        self.health_history = []
        self.boss_health_history = []


def test_capture():
    """测试截图功能"""
    print("="*60)
    print("截图测试")
    print("="*60)
    print("游戏: 东方冰之勇者记 (Touhou Hero of Ice Fairy)")
    print("可执行文件: Touhou Hero of Ice Fairy.exe")
    print()
    print("按 Ctrl+C 停止测试")
    print("按 S 保存当前截图")
    print("按 D 显示检测到的状态信息")
    print("两秒后开始检测....")
    sleep(2)

    capture = GameCapture()
    extractor = StateExtractor()

    if capture.region is None:
        print("[错误] 未找到游戏窗口，请确保游戏已运行")
        return

    print("开始捕获...")

    # 创建可调整大小的窗口，初始尺寸设为 1280x800
    window_name = "Game Capture Test"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 800)

    try:
        while True:
            state, raw = capture.get_state()
            if raw is not None:
                # 显示画面
                display = raw.copy()

                # 检测状态
                game_state = extractor.extract(raw)

                # 在画面上显示检测信息
                info_text = [
                    f"Health: {game_state['health']}/6",
                    f"Stamina: {game_state['stamina']:.2f}" if game_state['stamina'] else "Stamina: N/A",
                    f"Boss HP: {game_state['boss_health']:.2f}" if game_state['boss_health'] else "Boss HP: N/A",
                    f"Stage: {game_state['boss_stage']}/6" if game_state['boss_stage'] else "Stage: N/A",
                    f"Q: {'READY' if game_state['spell_left_ready'] else 'CD'}",
                    f"E: {'READY' if game_state['spell_right_ready'] else 'CD'}",
                ]
                y_offset = 30
                for text in info_text:
                    cv2.putText(display, text, (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    y_offset += 25

                cv2.imshow(window_name, display)
                key = cv2.waitKey(33)  # ~30fps

                if key & 0xFF == ord('q'):
                    break
                elif key & 0xFF == ord('s'):
                    capture.save_screenshot()
                elif key & 0xFF == ord('d'):
                    print(f"\n检测状态: {game_state}")
            else:
                print("\n[错误] 截图失败")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n测试已停止")
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    test_capture()
