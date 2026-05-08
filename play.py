"""
运行脚本 - 使用训练好的模型游玩
"""
import time
import argparse
from pathlib import Path

from config import MODEL_DIR
from game_env import TouhouEnv
from agent import PPOAgent


def play(model_path=None, render=True, fps=30):
    """
    使用训练好的模型运行游戏
    """
    if model_path is None:
        model_path = str(MODEL_DIR / "best.pt")
    print(f"加载模型: {model_path}")
    
    # 创建环境
    render_mode = "human" if render else None
    env = TouhouEnv(render_mode=render_mode, fps=fps)
    
    # 创建Agent
    obs_shape = env.observation_space.shape
    action_size = env.action_space.n
    agent = PPOAgent((obs_shape, 6), action_size)
    
    # 加载模型
    if Path(model_path).exists():
        try:
            agent.load(model_path)
        except Exception as e:
            print(f"[警告] 模型加载失败: {e}")
            print("将使用随机策略运行")
    else:
        print(f"[警告] 模型文件不存在: {model_path}")
        print("将使用随机策略运行")
    
    print("开始运行，按 Ctrl+C 停止")
    print("请确保游戏窗口在前台！")
    
    try:
        obs, _ = env.reset()
        episode_reward = 0
        episode_steps = 0
        
        while True:
            # 使用模型选择动作
            result = agent.select_action(obs, deterministic=True)
            action = result["action"]
            
            # 执行动作
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            episode_steps += 1
            
            if terminated or truncated:
                print(f"Episode结束: reward={episode_reward:.2f}, steps={episode_steps}")
                obs, _ = env.reset()
                episode_reward = 0
                episode_steps = 0
    
    except KeyboardInterrupt:
        print("\n停止运行")
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description="运行训练好的Agent")
    parser.add_argument("--model", type=str, default=None,
                       help="模型路径（默认: MODEL_DIR/best.pt）")
    parser.add_argument("--no-render", action="store_true",
                       help="不显示画面")
    parser.add_argument("--fps", type=int, default=30,
                       help="运行帧率")
    
    args = parser.parse_args()
    play(args.model, render=not args.no_render, fps=args.fps)


if __name__ == '__main__':
    main()
