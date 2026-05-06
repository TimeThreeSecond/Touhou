"""
环境检查脚本 - 在运行RL框架前检查依赖
"""
import sys
import subprocess
import importlib.util
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    print(f"Python版本: {sys.version}")
    if sys.version_info < (3, 8):
        print("[错误] 需要Python 3.8或更高版本")
        return False
    print("[通过] Python版本符合要求")
    return True


def check_package(package_name, import_name=None):
    """检查包是否安装"""
    if import_name is None:
        import_name = package_name
    
    spec = importlib.util.find_spec(import_name)
    if spec is None:
        print(f"[缺失] {package_name} 未安装")
        return False
    
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"[通过] {package_name} 已安装 (版本: {version})")
        return True
    except Exception as e:
        print(f"[警告] {package_name} 已安装但导入失败: {e}")
        return False


def check_conda():
    """检查conda环境"""
    try:
        result = subprocess.run(['conda', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"[通过] Conda已安装: {result.stdout.strip()}")
            
            # 列出环境
            env_result = subprocess.run(['conda', 'env', 'list'],
                                      capture_output=True, text=True, timeout=10)
            if env_result.returncode == 0:
                print("\n可用的Conda环境:")
                print(env_result.stdout)
            return True
        else:
            print("[信息] Conda未找到（将使用系统Python）")
            return False
    except FileNotFoundError:
        print("[信息] Conda未安装或未添加到PATH（将使用系统Python）")
        return False
    except Exception as e:
        print(f"[信息] 检查Conda时出错: {e}")
        return False


def install_instructions():
    """输出安装指南"""
    print("\n" + "="*60)
    print("安装指南")
    print("="*60)
    print("\n如果缺少依赖，请运行以下命令安装：")
    print("\n1. 基础依赖（必须）:")
    print("   pip install torch numpy opencv-python mss pyautogui pydirectinput gymnasium")
    print("\n2. 可选依赖（推荐）:")
    print("   pip install tensorboard matplotlib pillow")
    print("\n3. 如果使用conda环境:")
    print("   conda activate <your_env_name>")
    print("   pip install <上述包>")
    print("="*60)


def main():
    print("="*60)
    print("东方冰之勇者记 - 强化学习环境检查")
    print("="*60)
    print()
    
    # 检查Python版本
    python_ok = check_python_version()
    print()
    
    # 检查conda
    check_conda()
    print()
    
    # 检查必要包
    required_packages = {
        'torch': 'torch',
        'numpy': 'numpy',
        'opencv-python': 'cv2',
        'mss': 'mss',
        'gymnasium': 'gymnasium',
        'pyautogui': 'pyautogui',
        'pydirectinput': 'pydirectinput',
    }
    
    optional_packages = {
        'tensorboard': 'tensorboard',
        'matplotlib': 'matplotlib',
        'PIL': 'PIL',
    }
    
    print("检查必要依赖:")
    all_ok = True
    for pkg, imp in required_packages.items():
        if not check_package(pkg, imp):
            all_ok = False
    
    print("\n检查可选依赖:")
    for pkg, imp in optional_packages.items():
        check_package(pkg, imp)
    
    print()
    if all_ok and python_ok:
        print("[成功] 环境检查通过！可以开始训练。")
        return 0
    else:
        print("[失败] 环境检查未通过，请安装缺失的依赖。")
        install_instructions()
        return 1


if __name__ == '__main__':
    sys.exit(main())
