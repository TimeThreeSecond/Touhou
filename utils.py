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
        # 设置 DPI aware，防止 Windows 显示缩放导致截图坐标偏移
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        
        self.sct = mss.MSS()
        self.region = region or self._find_game_window()
        if self.region is None:
            print("[警告] 未找到游戏窗口，请手动设置 region")
            print("[提示] 方法1: 运行 key_config.py 检测游戏窗口")
            print("[提示] 方法2: 在 config.py 中手动设置 GAME_WINDOW['region']")

    def _find_game_window_pywin32(self):
        """使用 pywin32 查找游戏窗口，返回精确的客户区屏幕坐标"""
        import win32gui

        candidates = []
        # 标题黑名单：排除文件资源管理器、IDE 等常见非游戏窗口
        title_blacklist = ["文件资源管理器", "explorer", "visual studio", "pycharm", "code", "cmd", "powershell"]
        game_titles = [GAME_WINDOW["title"]] + GAME_WINDOW.get("fallback_titles", [])

        def enum_callback(hwnd, extra):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            # 黑名单过滤
            lower_title = title.lower()
            if any(bad in lower_title for bad in title_blacklist):
                return True
            # 标题匹配
            for t in game_titles:
                if t.lower() in lower_title:
                    # 获取客户区大小
                    client_rect = win32gui.GetClientRect(hwnd)
                    client_w = client_rect[2] - client_rect[0]
                    client_h = client_rect[3] - client_rect[1]
                    # 尺寸过滤：排除过小窗口（弹窗、任务栏图标等）
                    if client_w < 400 or client_h < 300:
                        return True
                    # 将客户区左上角 (0, 0) 转换为屏幕坐标
                    client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
                    candidates.append({
                        "left": client_left,
                        "top": client_top,
                        "width": client_w,
                        "height": client_h,
                        "title": title,
                        "hwnd": hwnd,
                        "area": client_w * client_h,
                        "exact_match": any(
                            exact.lower() in lower_title
                            for exact in ["Touhou Hero of Ice Fairy", "东方冰之勇者记"]
                        ),
                    })
                    return True
            return True

        win32gui.EnumWindows(enum_callback, None)

        if not candidates:
            return {}
        # 优先精确匹配标题的窗口，否则选面积最大的
        exact_matches = [c for c in candidates if c["exact_match"]]
        if exact_matches:
            return max(exact_matches, key=lambda x: x["area"])
        return max(candidates, key=lambda x: x["area"])

    def _find_game_window_ctypes(self):
        """使用 ctypes 备用方案查找游戏窗口，返回精确的客户区屏幕坐标"""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        candidates = []
        # 标题黑名单：排除文件资源管理器、IDE 等常见非游戏窗口
        title_blacklist = ["文件资源管理器", "explorer", "visual studio", "pycharm", "code", "cmd", "powershell"]
        game_titles = [GAME_WINDOW["title"]] + GAME_WINDOW.get("fallback_titles", [])

        # 回调函数类型
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM
        )

        def enum_callback(hwnd, lParam):
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

            # 黑名单过滤
            lower_title = title.lower()
            if any(bad in lower_title for bad in title_blacklist):
                return True

            for t in game_titles:
                if t.lower() in lower_title:
                    # 获取客户区大小
                    client_rect = wintypes.RECT()
                    if user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
                        client_w = client_rect.right - client_rect.left
                        client_h = client_rect.bottom - client_rect.top
                        # 尺寸过滤：排除过小窗口（弹窗、任务栏图标等）
                        if client_w < 400 or client_h < 300:
                            return True
                        # 将客户区左上角 (0, 0) 转换为屏幕坐标
                        pt = wintypes.POINT(0, 0)
                        user32.ClientToScreen(hwnd, ctypes.byref(pt))
                        candidates.append({
                            "left": pt.x,
                            "top": pt.y,
                            "width": client_w,
                            "height": client_h,
                            "title": title,
                            "hwnd": hwnd,
                            "area": client_w * client_h,
                            "exact_match": any(
                                exact.lower() in lower_title
                                for exact in ["Touhou Hero of Ice Fairy", "东方冰之勇者记"]
                            ),
                        })
                    return True
            return True

        callback = EnumWindowsProc(enum_callback)
        user32.EnumWindows(callback, 0)

        if not candidates:
            return {}
        # 优先精确匹配标题的窗口，否则选面积最大的
        exact_matches = [c for c in candidates if c["exact_match"]]
        if exact_matches:
            return max(exact_matches, key=lambda x: x["area"])
        return max(candidates, key=lambda x: x["area"])

    @staticmethod
    def _get_process_path(hwnd):
        """通过窗口句柄获取进程可执行文件路径（ctypes 实现，不依赖 pywin32）"""
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        # 获取进程 ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # 打开进程
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
        if not h_process:
            return None

        # 获取进程路径
        filename = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        success = kernel32.QueryFullProcessImageNameW(h_process, 0, filename, ctypes.byref(size))
        kernel32.CloseHandle(h_process)

        if success:
            return filename.value
        return None

    @staticmethod
    def _list_visible_windows():
        """列出所有可见窗口标题（调试用）"""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        windows = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_callback(hwnd, lParam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if title:
                windows.append(title)
            return True

        callback = EnumWindowsProc(enum_callback)
        user32.EnumWindows(callback, 0)

        print("\n[调试] 当前所有可见窗口标题（供排查）:")
        print("-" * 60)
        for i, title in enumerate(windows, 1):
            print(f"  {i}. {title}")
        print("-" * 60)
        print("[提示] 如果以上列表中没有游戏窗口，请检查游戏是否已启动")
        print("[提示] 如果游戏窗口标题与配置不符，请在 config.py 中修改 GAME_WINDOW['title']")

    def _find_game_window(self):
        """自动查找游戏窗口（优先 pywin32，失败则使用 ctypes 备用）"""
        candidates = []

        # 尝试 pywin32
        try:
            result = self._find_game_window_pywin32()
            if result:
                candidates.append(result)
                print("[信息] 使用 pywin32 找到候选窗口")
        except Exception as e:
            print(f"[信息] pywin32 检测失败: {e}")

        # 尝试 ctypes 备用方案
        try:
            result = self._find_game_window_ctypes()
            if result:
                # 避免与 pywin32 结果重复（同一窗口）
                if not candidates or candidates[0].get("hwnd") != result.get("hwnd"):
                    candidates.append(result)
                    print("[信息] 使用 ctypes 备用方案找到候选窗口")
        except Exception as e:
            print(f"[信息] ctypes 备用方案失败: {e}")

        if not candidates:
            self._list_visible_windows()
            print("[错误] 无法自动检测游戏窗口")
            return None

        # 进程验证：检查窗口所属进程是否真的是游戏 exe
        exe_name = GAME_WINDOW.get("exe_name", "Touhou Hero of Ice Fairy.exe")
        verified_candidates = []
        for c in candidates:
            process_path = self._get_process_path(c["hwnd"])
            if process_path:
                if exe_name.lower() in process_path.lower():
                    c["verified"] = True
                    c["process_path"] = process_path
                    verified_candidates.append(c)
                else:
                    c["verified"] = False
                    c["process_path"] = process_path
            else:
                c["verified"] = False
                c["process_path"] = None

        # 选择策略：优先选进程验证通过的，其次精确标题匹配，最后面积最大
        if verified_candidates:
            result = max(verified_candidates, key=lambda x: x["area"])
            print(f"[信息] 进程验证通过: {result['process_path']}")
        else:
            exact_matches = [c for c in candidates if c.get("exact_match")]
            if exact_matches:
                result = max(exact_matches, key=lambda x: x["area"])
            else:
                result = max(candidates, key=lambda x: x["area"])
            if result.get("process_path"):
                print(f"[警告] 窗口标题匹配但进程路径不符: {result['process_path']}")
                print(f"[警告] 期望进程: {exe_name}")
            else:
                print("[信息] 无法验证进程路径，依赖标题匹配")

        print(f"[信息] 找到游戏窗口:")
        print(f"  标题: {result['title']}")
        print(f"  客户区屏幕位置: ({result['left']}, {result['top']})")
        print(f"  客户区大小: {result['width']}x{result['height']}")
        return {
            "left": result["left"],
            "top": result["top"],
            "width": result["width"],
            "height": result["height"],
        }

    def capture(self):
        """捕获游戏画面"""
        if self.region is None:
            return None

        try:
            screenshot = self.sct.grab(self.region)
            img = np.array(screenshot)
            # 验证截图尺寸
            if img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
                print(f"[错误] 截图尺寸异常: shape={img.shape}, region={self.region}")
                return None
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
            self.pydirectinput.PAUSE = 0.0  # 禁用按键后的自动sleep，修复延迟
            print("[信息] 使用 pydirectinput 进行输入模拟")
        except ImportError:
            try:
                import pyautogui
                self.input_lib = "pyautogui"
                self.pyautogui = pyautogui
                self.pyautogui.FAILSAFE = False
                self.pyautogui.PAUSE = 0.0  # 禁用按键后的自动sleep
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

    # 基准分辨率（阈值基于此分辨率标定，使用相对坐标自动适配）
    # 参考UI检测报告: 1600×900 实际截图
    BASE_WIDTH = 1600
    BASE_HEIGHT = 900

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

        算法: 水平投影峰值计数法
        1. HSV蓝色掩膜提取雪花区域
        2. 闭运算填充雪花内部的白色边框/深蓝中心空洞
        3. 垂直投影（每列蓝色像素求和）得到一维曲线
        4. 检测曲线峰值的个数 = 雪花个数

        优点: 不依赖轮廓分离，即使相邻雪花边缘粘连也能通过峰值区分
        """
        region = self._get_region(img, UI_DETECTION["health_snowflakes"])
        if region.size == 0:
            return None

        scale = self._get_scale_factor(img)

        # HSV蓝色检测（覆盖浅蓝填充到深蓝中心）
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([95, 30, 50])
        upper_blue = np.array([145, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # 无蓝色像素 → 血量归零
        if np.sum(mask > 0) < 10:
            return 0

        # 闭运算填充雪花内部孔洞（白色边框+深蓝中心造成空洞）
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        # 开运算去除零星噪点
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 垂直投影：统计每列蓝色像素数
        h, w = mask.shape
        projection = np.sum(mask > 0, axis=0).astype(np.float32)

        # 高斯平滑投影曲线
        ksize = max(3, int(5 * scale + 0.5) | 1)  # 保证奇数
        projection = cv2.GaussianBlur(projection, (1, ksize), 0).flatten()

        # 峰值检测
        min_dist = max(15, int(25 * scale))  # 最小峰间距（防止同一雪花被多次计数）
        peak_threshold = np.max(projection) * 0.25

        peaks = []
        i = 0
        while i < w:
            if projection[i] > peak_threshold:
                peak_start = i
                while i < w and projection[i] > peak_threshold:
                    i += 1
                peak_end = i
                # 区间内找局部最大值位置
                peak_pos = peak_start + int(np.argmax(projection[peak_start:peak_end]))
                if not peaks or (peak_pos - peaks[-1]) > min_dist:
                    peaks.append(peak_pos)
            else:
                i += 1

        count = min(len(peaks), UI_DETECTION["health_snowflakes"]["max_health"])
        return count

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
        # 红色范围（Boss血条红色: H≈174~179, S≈136~255, V≈255）
        lower_red1 = np.array([0, 50, 40])
        upper_red1 = np.array([15, 255, 255])
        lower_red2 = np.array([160, 50, 40])
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

    def detect_boss_stage(self, img, prev_boss_health=None, current_boss_health=None):
        """
        检测Boss阶段（Stage X/6）
        返回: 当前阶段 (1-6) 或 None（非Boss战或无文字区域）

        检测策略:
        1. 亮红色文字检测: Stage X/6 文字为 RGB≈(231,3,45)，通过HSV红色范围识别
        2. 白色文字检测: Boss名称和技能名称为白色，灰度二值化识别
        3. HP启发式: Boss血量突降+恢复判定阶段转换
        """
        region = self._get_region(img, UI_DETECTION["boss_stage"])
        if region.size == 0:
            return None

        # ---- 文字存在性检测 ----

        # 1. 红色文字检测（Stage X/6 文字）
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 80, 80])
        upper_red1 = np.array([15, 255, 255])
        lower_red2 = np.array([160, 80, 80])
        upper_red2 = np.array([180, 255, 255])
        red_mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
        has_red_text = np.sum(red_mask > 0) > 30

        # 2. 白色文字检测（Boss名称和技能名称）
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        _, white_binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        white_ratio = np.sum(white_binary > 0) / white_binary.size
        has_white_text = white_ratio > 0.01

        # 既没有红色文字也没有白色文字 → 非Boss战或无UI
        if not (has_red_text or has_white_text):
            return None

        # ---- 阶段值推断 ----

        # Boss已击败且无文字 → 返回上一阶段（由调用方处理结束）
        if current_boss_health is not None and current_boss_health <= 0.01 and not has_red_text:
            return self.prev_boss_stage

        # HP启发式：Boss血量突降+恢复 → 阶段转换
        if prev_boss_health is not None and len(self.boss_health_history) >= 5:
            recent_low = np.min(self.boss_health_history[-5:])
            if recent_low < 0.1 and prev_boss_health > 0.8:
                if self.prev_boss_stage is not None:
                    return min(self.prev_boss_stage + 1, 6)

        # 默认：有Boss但未检测到阶段变化 → 返回之前阶段或1
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
        # READY文字RGB≈(255,240,224), 在HSV中S≈31（饱和度低）
        # 降低饱和度阈值以捕获浅黄色文字
        lower_ready = np.array([10, 20, 80])
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

            # 检测Boss血量（先检测，后更新 prev，供阶段检测使用上一帧的值）
            boss_health = self.detect_boss_health(img)
            if boss_health is not None:
                state["boss_health"] = boss_health
                if self.prev_boss_health is not None:
                    state["boss_health_changed"] = self.prev_boss_health - boss_health
                self.boss_health_history.append(boss_health)
                if len(self.boss_health_history) > 30:
                    self.boss_health_history.pop(0)

            # 检测Boss阶段（在更新 prev_boss_health 之前调用，使条件判断使用上帧值）
            prev_boss_hp = self.prev_boss_health  # 保存上一帧血量用于阶段检测
            boss_stage = self.detect_boss_stage(img, prev_boss_hp, current_boss_health=boss_health)

            # 更新 prev_boss_health（放在阶段检测之后）
            if boss_health is not None:
                self.prev_boss_health = boss_health
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
    print("="*60)
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
    cv2.resizeWindow(window_name, 510, 360)

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
