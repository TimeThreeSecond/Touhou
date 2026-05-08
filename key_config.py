"""
按键配置工具
用于检测和配置游戏按键
"""
import sys
import json
import time
from pathlib import Path

from config import DEFAULT_KEY_MAPPING, save_key_mapping, CONFIG_FILE, GAME_WINDOW


def show_current_config():
    """显示当前按键配置"""
    print("="*60)
    print("当前按键配置")
    print("="*60)
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print("[来源] 用户自定义配置")
        except:
            config = DEFAULT_KEY_MAPPING
            print("[来源] 默认配置（用户配置文件损坏）")
    else:
        config = DEFAULT_KEY_MAPPING
        print("[来源] 默认配置")
    
    print()
    print("功能 -> 按键")
    print("-"*60)
    has_empty = False
    for action, key in config.items():
        description = {
            "up": "向上移动",
            "down": "向下移动",
            "left": "向左移动",
            "right": "向右移动",
            "jump": "跳跃",
            "dash": "冲刺",
            "spell_left": "释放左符卡",
            "spell_right": "释放右符卡",
            "shoot": "发射子弹(长按鼠标左键)",
        }.get(action, action)
        display_key = key if key else "[未配置]"
        if not key:
            has_empty = True
        print(f"  {description:20s} -> {display_key}")
    
    if has_empty:
        print()
        print("[警告] 存在未配置的按键！")
        print("[提示] 请先启动游戏，查看设置菜单中的按键配置")
        print("[提示] 然后运行选项2进行按键配置")
    
    print("="*60)
    return config


def interactive_config():
    """交互式配置按键"""
    print("="*60)
    print("按键配置向导")
    print("="*60)
    print()
    print("【重要】请按以下步骤操作:")
    print("1. 启动游戏 'Touhou Hero of Ice Fairy'")
    print("2. 进入游戏的设置/选项菜单")
    print("3. 查看按键配置")
    print("4. 返回此处，输入对应的按键名称")
    print()
    print("注意: 直接回车将跳过该按键配置")
    print()
    
    config = DEFAULT_KEY_MAPPING.copy()
    
    actions = [
        ("up", "向上移动"),
        ("down", "向下移动"),
        ("left", "向左移动"),
        ("right", "向右移动"),
        ("jump", "跳跃"),
        ("dash", "冲刺"),
        ("spell_left", "释放左符卡"),
        ("spell_right", "释放右符卡"),
        ("shoot", "发射子弹(长按鼠标左键)"),
    ]
    
    for action, desc in actions:
        print(f"\n{desc}")
        user_input = input(f"  请输入按键名称: ").strip().lower()
        
        if user_input:
            config[action] = user_input
            print(f"  已设置为: {user_input}")
        else:
            print(f"  [跳过]")
    
    print()
    print("="*60)
    print("配置预览")
    print("="*60)
    for action, key in config.items():
        display_key = key if key else "[未配置]"
        print(f"  {action:10s} -> {display_key}")
    
    confirm = input("\n是否保存此配置? (y/n): ").strip().lower()
    if confirm in ['y', 'yes', '是']:
        if save_key_mapping(config):
            print("配置已保存！")
        else:
            print("配置保存失败！")
    else:
        print("配置未保存")


def _detect_game_window_pywin32():
    """使用 pywin32 检测游戏窗口，返回精确的客户区屏幕坐标"""
    import win32gui

    candidates = []
    # 标题黑名单：排除文件资源管理器、IDE 等常见非游戏窗口
    title_blacklist = ["文件资源管理器", "explorer", "visual studio", "pycharm", "code", "cmd", "powershell"]
    game_titles = ["Touhou Hero of Ice Fairy", "东方冰之勇者记"]

    def enum_callback(hwnd, extra):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        lower_title = title.lower()
        # 黑名单过滤
        if any(bad in lower_title for bad in title_blacklist):
            return True
        for game_title in game_titles:
            if game_title.lower() in lower_title:
                # 获取客户区大小
                client_rect = win32gui.GetClientRect(hwnd)
                client_w = client_rect[2] - client_rect[0]
                client_h = client_rect[3] - client_rect[1]
                # 尺寸过滤：排除过小窗口
                if client_w < 400 or client_h < 300:
                    return True
                # 将客户区左上角 (0, 0) 转换为屏幕坐标
                client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
                candidates.append({
                    "title": title,
                    "hwnd": hwnd,
                    "rect": (client_left, client_top, client_left + client_w, client_top + client_h),
                    "width": client_w,
                    "height": client_h,
                    "area": client_w * client_h,
                    "exact_match": any(
                        exact.lower() in lower_title
                        for exact in ["Touhou Hero of Ice Fairy", "东方冰之勇者记"]
                    ),
                })
                return True
        return True

    win32gui.EnumWindows(enum_callback, None)
    # 优先精确匹配标题的窗口，否则选面积最大的
    exact_matches = [c for c in candidates if c["exact_match"]]
    if exact_matches:
        return [max(exact_matches, key=lambda x: x["area"])]
    if candidates:
        return [max(candidates, key=lambda x: x["area"])]
    return []


def _detect_game_window_ctypes():
    """使用 ctypes 备用方案检测游戏窗口，返回精确的客户区屏幕坐标"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    candidates = []
    # 标题黑名单：排除文件资源管理器、IDE 等常见非游戏窗口
    title_blacklist = ["文件资源管理器", "explorer", "visual studio", "pycharm", "code", "cmd", "powershell"]
    game_titles = ["Touhou Hero of Ice Fairy", "东方冰之勇者记"]

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

        for game_title in game_titles:
            if game_title.lower() in lower_title:
                # 获取客户区大小
                client_rect = wintypes.RECT()
                if user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
                    client_w = client_rect.right - client_rect.left
                    client_h = client_rect.bottom - client_rect.top
                    # 尺寸过滤：排除过小窗口
                    if client_w < 400 or client_h < 300:
                        return True
                    # 将客户区左上角 (0, 0) 转换为屏幕坐标
                    pt = wintypes.POINT(0, 0)
                    user32.ClientToScreen(hwnd, ctypes.byref(pt))
                    candidates.append({
                        "title": title,
                        "hwnd": hwnd,
                        "rect": (pt.x, pt.y, pt.x + client_w, pt.y + client_h),
                        "width": client_w,
                        "height": client_h,
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

    # 优先精确匹配标题的窗口，否则选面积最大的
    exact_matches = [c for c in candidates if c["exact_match"]]
    if exact_matches:
        return [max(exact_matches, key=lambda x: x["area"])]
    if candidates:
        return [max(candidates, key=lambda x: x["area"])]
    return []


def _get_process_path(hwnd):
    """通过窗口句柄获取进程可执行文件路径（ctypes 实现）"""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value)
    if not h_process:
        return None

    filename = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(1024)
    success = kernel32.QueryFullProcessImageNameW(h_process, 0, filename, ctypes.byref(size))
    kernel32.CloseHandle(h_process)

    if success:
        return filename.value
    return None


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


def detect_game_window():
    """检测游戏窗口（优先 pywin32，失败则使用 ctypes 备用），含进程验证"""
    print("="*60)
    print("游戏窗口检测")
    print("="*60)
    print()
    print("正在查找游戏窗口...")
    print("请确保游戏正在运行")
    print()

    candidates = []

    # 尝试 pywin32
    try:
        pywin32_windows = _detect_game_window_pywin32()
        if pywin32_windows:
            candidates.extend(pywin32_windows)
            print("[信息] 使用 pywin32 检测到候选窗口")
    except Exception as e:
        print(f"[信息] pywin32 检测失败: {e}")

    # 尝试 ctypes 备用方案
    try:
        ctypes_windows = _detect_game_window_ctypes()
        if ctypes_windows:
            # 去重：避免同一窗口被两个分支都加入
            existing_hwnds = {c["hwnd"] for c in candidates}
            for w in ctypes_windows:
                if w["hwnd"] not in existing_hwnds:
                    candidates.append(w)
            if candidates:
                print("[信息] 使用 ctypes 备用方案检测到候选窗口")
    except Exception as e:
        print(f"[信息] ctypes 备用方案失败: {e}")

    if not candidates:
        _list_visible_windows()
        print("未找到游戏窗口！")
        print("请确保游戏已启动")
        print()
        print("如仍无法检测，请手动在 config.py 中设置 GAME_WINDOW['region']")
        return

    # 进程验证
    exe_name = GAME_WINDOW.get("exe_name", "Touhou Hero of Ice Fairy.exe")
    verified = []
    for c in candidates:
        path = _get_process_path(c["hwnd"])
        if path and exe_name.lower() in path.lower():
            c["verified"] = True
            c["process_path"] = path
            verified.append(c)
        else:
            c["verified"] = False
            c["process_path"] = path

    # 选择策略：优先进程验证通过的，其次精确标题匹配，最后面积最大
    if verified:
        win = max(verified, key=lambda x: x["area"])
        print(f"[信息] 进程验证通过: {win['process_path']}")
    else:
        exact = [c for c in candidates if c.get("exact_match")]
        if exact:
            win = max(exact, key=lambda x: x["area"])
        else:
            win = max(candidates, key=lambda x: x["area"])
        if win.get("process_path"):
            print(f"[警告] 窗口标题匹配但进程路径不符: {win['process_path']}")
            print(f"[警告] 期望进程: {exe_name}")
        else:
            print("[信息] 无法验证进程路径，依赖标题匹配")

    print(f"\n找到游戏窗口:")
    print(f"  标题: {win['title']}")
    print(f"  位置: ({win['rect'][0]}, {win['rect'][1]})")
    print(f"  大小: {win['width']}x{win['height']}")
    print(f"  句柄: {win['hwnd']}")

    print()
    print("建议的截图区域配置:")
    print("  请在 config.py 中设置 GAME_WINDOW['region']")
    print(f"\n  窗口: {win['title']}")
    print(f"  region = {{")
    print(f"      'left': {win['rect'][0]},")
    print(f"      'top': {win['rect'][1]},")
    print(f"      'width': {win['width']},")
    print(f"      'height': {win['height']}")
    print(f"  }}")


def test_keys():
    """测试按键是否正常工作"""
    print("="*60)
    print("按键测试工具")
    print("="*60)
    print()
    print("此工具将模拟游戏实际按键操作")
    print("请确保游戏窗口在前台并已进入战斗场景")
    print("按 Ctrl+C 停止测试")
    print()
    print("注意: 测试基于 config.py 中的按键配置")
    print()

    try:
        import pydirectinput
        pydirectinput.FAILSAFE = False

        # 加载当前按键配置
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                key_map = json.load(f)
        else:
            key_map = DEFAULT_KEY_MAPPING

        print("5秒后开始测试...")
        time.sleep(5)

        # 测试WASD移动
        print("\n测试移动 (WASD)...")
        for key_name, desc in [("up", "向上"), ("down", "向下"), ("left", "向左"), ("right", "向右")]:
            key = key_map.get(key_name, "")
            if key:
                print(f"  按下 {desc} ({key})")
                pydirectinput.keyDown(key)
                time.sleep(0.5)
                pydirectinput.keyUp(key)
                time.sleep(0.3)

        # 测试跳跃
        jump_key = key_map.get("jump", "")
        if jump_key:
            print(f"\n测试跳跃 ({jump_key})...")
            pydirectinput.keyDown(jump_key)
            time.sleep(0.3)
            pydirectinput.keyUp(jump_key)
            time.sleep(0.5)

        # 测试冲刺
        dash_key = key_map.get("dash", "")
        if dash_key:
            print(f"\n测试冲刺 ({dash_key})...")
            pydirectinput.keyDown(dash_key)
            time.sleep(1.0)
            pydirectinput.keyUp(dash_key)
            time.sleep(0.5)

        # 测试射击（鼠标左键长按）
        shoot_key = key_map.get("shoot", "")
        if shoot_key:
            print(f"\n测试射击 ({shoot_key})...")
            if shoot_key in ["left", "right", "middle"]:
                pydirectinput.mouseDown(button=shoot_key)
                time.sleep(1.5)
                pydirectinput.mouseUp(button=shoot_key)
            else:
                pydirectinput.keyDown(shoot_key)
                time.sleep(1.5)
                pydirectinput.keyUp(shoot_key)
            time.sleep(0.5)

        # 测试符卡
        for spell_name, spell_desc in [("spell_left", "左符卡(Q)"), ("spell_right", "右符卡(E)")]:
            spell_key = key_map.get(spell_name, "")
            if spell_key:
                print(f"\n测试{spell_desc} ({spell_key})...")
                pydirectinput.keyDown(spell_key)
                time.sleep(0.3)
                pydirectinput.keyUp(spell_key)
                time.sleep(0.5)

        print("\n测试完成！")

    except ImportError:
        print("[错误] 未安装 pydirectinput")
        print("请运行: pip install pydirectinput")
    except KeyboardInterrupt:
        print("\n测试已停止")
    except Exception as e:
        print(f"[错误] 测试失败: {e}")


def main():
    print("="*60)
    print("东方冰之勇者记 - 按键配置工具")
    print("="*60)
    print()
    print("基于游戏文件: Touhou Hero of Ice Fairy.exe")
    print()
    print("选项:")
    print("  1. 查看当前配置")
    print("  2. 修改按键配置")
    print("  3. 检测游戏窗口")
    print("  4. 测试按键")
    print("  5. 退出")
    print()
    
    while True:
        choice = input("请选择操作 (1-5): ").strip()
        
        if choice == "1":
            show_current_config()
        elif choice == "2":
            interactive_config()
        elif choice == "3":
            detect_game_window()
        elif choice == "4":
            test_keys()
        elif choice == "5":
            print("再见！")
            break
        else:
            print("无效选项，请重新选择")
        
        print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已退出")
