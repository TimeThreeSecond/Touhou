"""
训练脚本
"""
import time
import numpy as np
from collections import deque

from config import TRAIN, MODEL_DIR
from game_env import TouhouEnv
from agent import PPOAgent


# 训练时长预设（基于每步 ~0.105s 的粗略估算，含 env step + inference + update 分摊 + reset）
TRAINING_PRESETS = {
    "1": {"name": "快速测试",  "steps": 35_000,   "hours": 1},
    "2": {"name": "短训",      "steps": 70_000,   "hours": 2},
    "3": {"name": "标准",      "steps": 275_000,  "hours": 8},
    "4": {"name": "完整",      "steps": 410_000,  "hours": 12},
}


def select_training_duration(n_steps):
    """让用户选择训练时长，返回对应的目标步数（对齐到 n_steps 整数倍）"""
    print("\n" + "=" * 50)
    print("请选择训练时长（基于当前速度粗略估算）")
    print("=" * 50)
    for key, preset in TRAINING_PRESETS.items():
        rounds = preset["steps"] // n_steps
        print(f"  [{key}] {preset['name']:8s}  ~{preset['hours']:2d}小时  "
              f"({preset['steps']:,} 步 / 约 {rounds} 轮)")
    print(f"  [5] 自定义     手动输入步数")
    print(f"  [6] 配置默认   使用 config.py 中的 {TRAIN['total_timesteps']:,} 步")
    print("-" * 50)

    choice = input("请输入选项 [1-6，默认3]: ").strip() or "3"

    if choice in TRAINING_PRESETS:
        preset = TRAINING_PRESETS[choice]
        target_steps = preset["steps"]
        desc = preset["name"]
    elif choice == "5":
        raw = input("请输入目标步数: ").strip()
        try:
            target_steps = int(raw)
            desc = "自定义"
        except ValueError:
            print(f"[警告] 输入无效，使用默认值 {TRAIN['total_timesteps']:,}")
            target_steps = TRAIN["total_timesteps"]
            desc = "配置默认"
    elif choice == "6":
        target_steps = TRAIN["total_timesteps"]
        desc = "配置默认"
    else:
        print(f"[警告] 无效选项，使用默认值 {TRAIN['total_timesteps']:,}")
        target_steps = TRAIN["total_timesteps"]
        desc = "配置默认"

    # 对齐到 n_steps 的整数倍（避免最后一轮数据不完整）
    aligned_steps = ((target_steps + n_steps - 1) // n_steps) * n_steps
    if aligned_steps != target_steps:
        print(f"[信息] 步数已对齐到 n_steps={n_steps} 的整数倍: "
              f"{target_steps:,} → {aligned_steps:,}")

    print(f"[确认] 训练模式: {desc}, 目标步数: {aligned_steps:,}")
    print("=" * 50 + "\n")
    return aligned_steps


def collect_rollout(env, agent, n_steps):
    """收集训练数据"""
    visual_observations = []
    structured_observations = []
    actions = []
    rewards = []
    dones = []
    values = []
    log_probs = []
    
    obs, _ = env.reset()
    visual_obs, structured_obs = obs
    episode_reward = 0
    episode_length = 0
    
    for step in range(n_steps):
        # 选择动作
        result = agent.select_action(obs, deterministic=False)
        action = result["action"]
        
        # 执行动作
        next_obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        
        # 存储数据
        visual_observations.append(visual_obs)
        structured_observations.append(structured_obs)
        actions.append(action)
        rewards.append(reward)
        dones.append(float(done))
        values.append(result["value"])
        log_probs.append(result["log_prob"])
        
        obs = next_obs
        if isinstance(next_obs, tuple):
            visual_obs, structured_obs = next_obs
        else:
            visual_obs = next_obs
            structured_obs = np.zeros(6, dtype=np.float32)
        
        episode_reward += reward
        episode_length += 1
        
        if done:
            print(f"Episode finished: reward={episode_reward:.2f}, length={episode_length}")
            obs, _ = env.reset()
            if isinstance(obs, tuple):
                visual_obs, structured_obs = obs
            else:
                visual_obs = obs
                structured_obs = np.zeros(6, dtype=np.float32)
            episode_reward = 0
            episode_length = 0
    
    return {
        "observations": (
            np.array(visual_observations),
            np.array(structured_observations),
        ),
        "actions": np.array(actions),
        "rewards": np.array(rewards),
        "dones": np.array(dones),
        "values": np.array(values),
        "old_log_probs": np.array(log_probs),
    }

def train():
    """主训练循环"""
    print("="*60)
    print("开始训练东方冰之勇者记强化学习Agent")
    print("="*60)
    
    # 创建环境
    env = TouhouEnv(render_mode=None)
    
    # 创建Agent
    obs_shape = env.observation_space.shape
    action_size = env.action_space.n
    agent = PPOAgent((obs_shape, 6), action_size, device=TRAIN["device"])
    
    # 训练统计
    total_steps = 0
    episode_rewards = deque(maxlen=100)
    best_reward = -float('inf')
    
    # 加载已有模型（如果存在）
    model_path = MODEL_DIR / "latest.pt"
    if model_path.exists():
        try:
            print(f"发现已有模型，加载中...")
            agent.load(str(model_path))
        except Exception as e:
            print(f"[警告] 模型加载失败（可能是旧版模型格式不兼容）: {e}")
            print("[信息] 将从头开始训练")
    
    print(f"观察空间: {obs_shape}")
    print(f"动作空间: {action_size}")
    print()

    # 选择训练时长
    target_steps = select_training_duration(TRAIN["n_steps"])

    try:
        while total_steps < target_steps:
            # 收集数据
            print(f"收集数据... (step {total_steps}/{target_steps})")
            rollout_data = collect_rollout(env, agent, TRAIN["n_steps"])

            # 更新策略
            print("更新策略...")
            agent.update(rollout_data)

            total_steps += TRAIN["n_steps"]
            agent.step_count = total_steps

            # 计算平均奖励
            avg_reward = np.mean(rollout_data["rewards"])
            print(f"平均奖励: {avg_reward:.4f}")

            # 保存模型
            if total_steps % TRAIN["save_freq"] == 0:
                save_path = MODEL_DIR / f"model_step_{total_steps}.pt"
                agent.save(str(save_path))
                agent.save(str(MODEL_DIR / "latest.pt"))

                # 保存最佳模型
                if avg_reward > best_reward:
                    best_reward = avg_reward
                    agent.save(str(MODEL_DIR / "best.pt"))
    
    except KeyboardInterrupt:
        print("\n训练被中断")
    finally:
        # 保存最终模型
        agent.save(str(MODEL_DIR / "final.pt"))
        env.close()
        print("训练结束，模型已保存")


if __name__ == '__main__':
    train()
