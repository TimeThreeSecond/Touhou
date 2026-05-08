"""
强化学习Agent
支持 PPO, DQN, A2C
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path

from config import MODEL, TRAIN


class CNNFeatureExtractor(nn.Module):
    """CNN特征提取器"""
    
    def __init__(self, input_channels, height, width):
        super().__init__()
        layers = []
        in_channels = input_channels
        h, w = height, width
        
        for out_channels, kernel_size, stride in MODEL["cnn_layers"]:
            layers.append(nn.Conv2d(in_channels, out_channels, kernel_size, stride))
            layers.append(nn.ReLU())
            in_channels = out_channels
            h = (h - kernel_size) // stride + 1
            w = (w - kernel_size) // stride + 1
        
        self.cnn = nn.Sequential(*layers)
        self.feature_size = in_channels * h * w
    
    def forward(self, x):
        return self.cnn(x)


class PolicyNetwork(nn.Module):
    """策略网络"""
    
    def __init__(self, feature_size, action_size):
        super().__init__()
        layers = []
        in_size = feature_size
        for hidden_size in MODEL["fc_layers"]:
            layers.append(nn.Linear(in_size, hidden_size))
            layers.append(nn.ReLU())
            in_size = hidden_size
        layers.append(nn.Linear(in_size, action_size))
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)
    
    def get_action(self, x, deterministic=False):
        logits = self.forward(x)
        probs = F.softmax(logits, dim=-1)
        if deterministic:
            action = torch.argmax(probs, dim=-1)
        else:
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
        log_prob = F.log_softmax(logits, dim=-1).gather(1, action.unsqueeze(-1)).squeeze(-1)
        return action, log_prob, probs


class ValueNetwork(nn.Module):
    """价值网络"""
    
    def __init__(self, feature_size):
        super().__init__()
        layers = []
        in_size = feature_size
        for hidden_size in MODEL["fc_layers"]:
            layers.append(nn.Linear(in_size, hidden_size))
            layers.append(nn.ReLU())
            in_size = hidden_size
        layers.append(nn.Linear(in_size, 1))
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x).squeeze(-1)


class PPOAgent:
    """PPO Agent"""
    
    def __init__(self, observation_shape, action_size, device=None, structured_dim=6):
        self.observation_shape = observation_shape
        self.action_size = action_size
        self.structured_dim = structured_dim
        
        if device is None or device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        print(f"使用设备: {self.device}")
        
        # 解析观察空间：支持纯视觉 (C,H,W) 或多模态 ((C,H,W), structured_dim)
        if isinstance(observation_shape, (list, tuple)) and len(observation_shape) == 2:
            visual_shape = observation_shape[0]
            self.structured_dim = observation_shape[1] if isinstance(observation_shape[1], int) else observation_shape[1][0]
        else:
            visual_shape = observation_shape
        
        input_channels = visual_shape[0] if len(visual_shape) == 3 else 1
        height = visual_shape[-2] if len(visual_shape) >= 2 else 84
        width = visual_shape[-1] if len(visual_shape) >= 2 else 84
        
        self.feature_extractor = CNNFeatureExtractor(input_channels, height, width).to(self.device)
        
        # 拼接视觉特征与结构化状态后的维度
        combined_feature_size = self.feature_extractor.feature_size + self.structured_dim
        self.policy = PolicyNetwork(combined_feature_size, action_size).to(self.device)
        self.value = ValueNetwork(combined_feature_size).to(self.device)
        
        self.optimizer = torch.optim.Adam(
            list(self.feature_extractor.parameters()) + 
            list(self.policy.parameters()) + 
            list(self.value.parameters()),
            lr=TRAIN["learning_rate"]
        )
        
        self.gamma = TRAIN["gamma"]
        self.gae_lambda = TRAIN["gae_lambda"]
        self.clip_range = TRAIN["clip_range"]
        self.ent_coef = TRAIN["ent_coef"]
        self.vf_coef = TRAIN["vf_coef"]
        self.max_grad_norm = TRAIN["max_grad_norm"]
        self.step_count = 0
    
    def select_action(self, observation, deterministic=False):
        with torch.no_grad():
            # 解包多模态观察
            if isinstance(observation, tuple):
                visual_obs, structured_obs = observation
            else:
                visual_obs = observation
                structured_obs = np.zeros(self.structured_dim, dtype=np.float32)
            
            if not isinstance(structured_obs, np.ndarray):
                structured_obs = np.array(structured_obs, dtype=np.float32)
            
            visual_tensor = torch.FloatTensor(visual_obs).unsqueeze(0).to(self.device)
            structured_tensor = torch.FloatTensor(structured_obs).unsqueeze(0).to(self.device)
            
            visual_features = self.feature_extractor(visual_tensor)
            visual_features = visual_features.view(visual_features.size(0), -1)
            
            # 拼接视觉特征与结构化状态
            features = torch.cat([visual_features, structured_tensor], dim=-1)
            
            action, log_prob, probs = self.policy.get_action(features, deterministic)
            value = self.value(features)
            
            return {
                "action": action.cpu().numpy()[0],
                "log_prob": log_prob.cpu().numpy()[0],
                "value": value.cpu().numpy()[0],
                "probs": probs.cpu().numpy()[0],
            }
    
    def compute_gae(self, rewards, values, dones):
        advantages = []
        gae = 0
        for t in reversed(range(len(rewards))):
            next_value = 0 if t == len(rewards) - 1 else values[t + 1]
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
            advantages.insert(0, gae)
        return np.array(advantages)
    
    def update(self, rollout_data):
        # 解包多模态观察
        if isinstance(rollout_data["observations"], tuple):
            visual_obs = torch.FloatTensor(rollout_data["observations"][0]).to(self.device)
            structured_obs = torch.FloatTensor(rollout_data["observations"][1]).to(self.device)
        else:
            visual_obs = torch.FloatTensor(rollout_data["observations"]).to(self.device)
            structured_obs = torch.zeros((len(visual_obs), self.structured_dim), device=self.device)
        
        actions = torch.LongTensor(rollout_data["actions"]).to(self.device)
        old_log_probs = torch.FloatTensor(rollout_data["old_log_probs"]).to(self.device)
        
        advantages = self.compute_gae(rollout_data["rewards"], rollout_data["values"], rollout_data["dones"])
        returns = advantages + rollout_data["values"]
        
        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        dataset_size = len(visual_obs)
        indices = np.arange(dataset_size)
        
        for epoch in range(4):
            np.random.shuffle(indices)
            for start in range(0, dataset_size, TRAIN["batch_size"]):
                end = start + TRAIN["batch_size"]
                batch_idx = indices[start:end]
                
                batch_visual = visual_obs[batch_idx]
                batch_structured = structured_obs[batch_idx]
                batch_actions = actions[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]
                
                visual_features = self.feature_extractor(batch_visual)
                visual_features = visual_features.view(visual_features.size(0), -1)
                
                # 拼接视觉特征与结构化状态
                features = torch.cat([visual_features, batch_structured], dim=-1)
                
                logits = self.policy(features)
                probs = F.softmax(logits, dim=-1)
                dist = torch.distributions.Categorical(probs)
                new_log_probs = dist.log_prob(batch_actions)
                entropy = dist.entropy()
                
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_range, 1 + self.clip_range) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                values = self.value(features)
                value_loss = F.mse_loss(values, batch_returns)
                
                loss = policy_loss + self.vf_coef * value_loss - self.ent_coef * entropy.mean()
                
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(
                    list(self.feature_extractor.parameters()) + 
                    list(self.policy.parameters()) + 
                    list(self.value.parameters()),
                    self.max_grad_norm
                )
                self.optimizer.step()
    
    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "feature_extractor": self.feature_extractor.state_dict(),
            "policy": self.policy.state_dict(),
            "value": self.value.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "step_count": self.step_count,
        }, path)
        print(f"模型已保存: {path}")
    
    def load(self, path):
        checkpoint = torch.load(path, map_location=self.device)
        self.feature_extractor.load_state_dict(checkpoint["feature_extractor"])
        self.policy.load_state_dict(checkpoint["policy"])
        self.value.load_state_dict(checkpoint["value"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.step_count = checkpoint.get("step_count", 0)
        print(f"模型已加载: {path}")


if __name__ == '__main__':
    print("测试Agent...")
    agent = PPOAgent(((4, 180, 320), 6), 288)
    obs = (np.zeros((4, 180, 320), dtype=np.float32), np.zeros(6, dtype=np.float32))
    result = agent.select_action(obs)
    print(f"动作: {result['action']}, 价值: {result['value']:.4f}")
    print("Agent创建成功")
