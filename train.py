"""
训练脚本
"""
import time
import numpy as np
from pathlib import Path
from collections import deque

from config import TRAIN
from game_env import TouhouEnv
from agent import PPOAgent


def collect_rollout(env, agent, n_steps):
    """收集训练数据"""
    observations = []
    actions = []
    rewards = []
    dones = []
    values = []
    log_probs = []
    
    obs, _ = env.reset()
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
        observations.append(obs)
        actions.append(action)
        rewards.append(reward)
        dones.append(float(done))
        values.append(result["value"])
        log_probs.append(result["log_prob"])
        
        obs = next_obs
        episode_reward += reward
        episode_length += 1
        
        if done:
            print(f"Episode finished: reward={episode_reward:.2f}, length={episode_length}")
            obs, _ = env.reset()
            episode_reward = 0
            episode_length = 0
    
    return {
        "observations": np.array(observations),
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
    agent = PPOAgent(obs_shape, action_size, device=TRAIN["device"])
    
    # 训练统计
    total_steps = 0
    episode_rewards = deque(maxlen=100)
    best_reward = -float('inf')
    
    # 加载已有模型（如果存在）
    model_path = Path("models/latest.pt")
    if model_path.exists():
        print(f"发现已有模型，加载中...")
        agent.load(str(model_path))
    
    print(f"观察空间: {obs_shape}")
    print(f"动作空间: {action_size}")
    print(f"目标步数: {TRAIN['total_timesteps']}")
    print()
    
    try:
        while total_steps < TRAIN["total_timesteps"]:
            # 收集数据
            print(f"收集数据... (step {total_steps}/{TRAIN['total_timesteps']})")
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
                save_path = f"models/model_step_{total_steps}.pt"
                agent.save(save_path)
                agent.save("models/latest.pt")
                
                # 保存最佳模型
                if avg_reward > best_reward:
                    best_reward = avg_reward
                    agent.save("models/best.pt")
    
    except KeyboardInterrupt:
        print("\n训练被中断")
    finally:
        # 保存最终模型
        agent.save("models/final.pt")
        env.close()
        print("训练结束，模型已保存")


if __name__ == '__main__':
    train()
