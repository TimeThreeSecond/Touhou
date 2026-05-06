"""
游戏环境 - Gymnasium风格的RL环境
基于真实游戏: 东方冰之勇者记 (Touhou Hero of Ice Fairy)
可执行文件: Touhou Hero of Ice Fairy.exe

战斗画面UI:
- 左上角6个蓝色雪花 = 玩家血量
- 雪花下方黄色条 = 体力条（冲刺消耗）
- 右上角红色长条 = Boss血量
- Stage 1/6 = Boss有6条命，当前第1条
- 左侧READY = 符卡就绪
"""
import time
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from config import VISION, ACTION_SPACE, REWARD
from utils import GameCapture, GameController, StateExtractor


class TouhouEnv(gym.Env):
    """
    东方冰之勇者记强化学习环境

    游戏信息:
    - 名称: 东方冰之勇者记 ~ Touhou Hero of Ice Fairy
    - 引擎: Unity
    - 可执行文件: Touhou Hero of Ice Fairy.exe

    操作说明 (基于游戏内设置截图):
    - 移动: W/A/S/D (主按键) / 方向键 (副按键)
    - 跳跃: Space (主按键) / Numpad1 (副按键)
    - 冲刺: LeftShift (主按键) / RightButton (副按键)
    - 释放左符卡: Q (主按键) / Numpad2 (副按键)
    - 释放右符卡: E (主按键) / Numpad3 (副按键)
    - 发射子弹: 长按鼠标左键
    """

    metadata = {'render_modes': ['human', 'rgb_array']}

    def __init__(self, render_mode=None, fps=30):
        super().__init__()

        self.render_mode = render_mode
        self.fps = fps
        self.frame_time = 1.0 / fps

        # 游戏交互组件
        self.capture = GameCapture()
        self.controller = GameController()
        self.extractor = StateExtractor()

        # 动作空间
        # 离散动作：方向(9) × 冲刺(2) × 跳跃(2) × 左符卡(2) × 右符卡(2) × 射击(2) = 288种组合
        self.action_size = (
            ACTION_SPACE["move_directions"] *
            (2 if ACTION_SPACE["use_dash"] else 1) *
            (2 if ACTION_SPACE["use_jump"] else 1) *
            (2 if ACTION_SPACE["use_spell_left"] else 1) *
            (2 if ACTION_SPACE["use_spell_right"] else 1) *
            (2 if ACTION_SPACE["use_shoot"] else 1)
        )
        self.action_space = spaces.Discrete(self.action_size)

        # 帧堆叠（用于捕捉运动信息）
        self.frame_stack_size = 4
        self.frame_stack = None
        
        # 观察空间：帧堆叠后的图像
        input_channels = 1 if VISION["grayscale"] else 3
        obs_shape = (self.frame_stack_size * input_channels, 
                     VISION["resize_height"], VISION["resize_width"])
        
        self.observation_space = spaces.Box(
            low=0.0, high=1.0,
            shape=obs_shape,
            dtype=np.float32
        )
        
        # 游戏状态
        self.episode_steps = 0
        self.max_steps = 10000
        self.total_reward = 0.0
        self.done = False

        # 用于渲染
        self.last_raw_frame = None

        # 历史奖励信息（用于计算变化）
        self.prev_state_info = None

    def _get_observation(self):
        """获取当前观察"""
        state, raw = self.capture.get_state()
        self.last_raw_frame = raw

        if state is None:
            # 如果截图失败，返回零矩阵
            if VISION["grayscale"]:
                return np.zeros((1, VISION["resize_height"], VISION["resize_width"]), dtype=np.float32)
            else:
                return np.zeros((3, VISION["resize_height"], VISION["resize_width"]), dtype=np.float32)

        return state

    def _action_to_dict(self, action):
        """将离散动作转换为动作字典"""
        action_dict = {
            "direction": 0,
            "dash": False,
            "jump": False,
            "spell_left": False,
            "spell_right": False,
            "shoot": False,
        }

        idx = action

        # 方向
        action_dict["direction"] = idx % ACTION_SPACE["move_directions"]
        idx //= ACTION_SPACE["move_directions"]

        # 冲刺
        if ACTION_SPACE["use_dash"]:
            action_dict["dash"] = (idx % 2) == 1
            idx //= 2

        # 跳跃
        if ACTION_SPACE["use_jump"]:
            action_dict["jump"] = (idx % 2) == 1
            idx //= 2

        # 左符卡
        if ACTION_SPACE["use_spell_left"]:
            action_dict["spell_left"] = (idx % 2) == 1
            idx //= 2

        # 右符卡
        if ACTION_SPACE["use_spell_right"]:
            action_dict["spell_right"] = (idx % 2) == 1
            idx //= 2

        # 射击
        if ACTION_SPACE["use_shoot"]:
            action_dict["shoot"] = (idx % 2) == 1

        return action_dict

    def _get_reward(self, state_info, action_dict):
        """
        计算奖励（基于实际战斗画面UI）

        UI元素:
        - health: 玩家雪花血量 (0-6)
        - stamina: 体力条 (0.0-1.0)
        - boss_health: Boss血量 (0.0-1.0)
        - boss_stage: Boss阶段 (1-6)
        - health_changed: 血量变化 (+增加, -减少)
        - boss_health_changed: Boss血量变化 (正值表示造成伤害)
        - boss_stage_changed: 阶段变化 (正值表示进入下一阶段)
        """
        reward = 0.0

        # ---- 基础奖励 ----
        # 存活奖励（每帧给予少量正奖励鼓励生存）
        reward += REWARD["alive_reward"]

        # 时间惩罚（鼓励快速击杀）
        reward += REWARD["time_penalty"]

        if state_info is None:
            return reward

        # ---- 血量变化奖励/惩罚 ----
        if state_info["health_changed"] < 0:
            # 被击中，雪花减少
            reward += REWARD["health_loss_penalty"] * abs(state_info["health_changed"])
        elif state_info["health_changed"] > 0:
            # 血量恢复（如有回血道具）
            reward += REWARD["health_gain_reward"] * state_info["health_changed"]

        # ---- Boss伤害奖励 ----
        if state_info["boss_health_changed"] > 0:
            # 对Boss造成了伤害
            # 基础伤害奖励 + 与伤害量成正比的奖励
            damage = state_info["boss_health_changed"]
            reward += REWARD["boss_damage_reward"] * damage * 10

        # ---- Boss阶段突破奖励 ----
        if state_info["boss_stage_changed"] > 0:
            # 击败了Boss一条命，进入下一阶段
            reward += REWARD["boss_stage_clear_reward"] * state_info["boss_stage_changed"]

        # ---- 攻击行为奖励 ----
        if action_dict.get("shoot", False):
            # 鼓励持续射击（因为需要长按鼠标左键输出）
            reward += REWARD["shoot_reward"]

        if action_dict.get("spell_left", False) or action_dict.get("spell_right", False):
            # 鼓励使用符卡技能
            reward += REWARD["spell_use_reward"]

        # ---- 体力管理 ----
        if state_info["stamina"] is not None:
            if state_info["stamina"] < 0.1:
                # 体力过低，无法冲刺，轻微惩罚
                reward += REWARD["stamina_low_penalty"]
            if action_dict.get("dash", False) and state_info["stamina"] > 0:
                # 使用冲刺消耗体力，微小惩罚（鼓励节约使用）
                reward += REWARD["stamina_consume_penalty"]

        # ---- 死亡/通关大奖励/惩罚 ----
        if not state_info["is_alive"]:
            # 玩家死亡，大惩罚
            reward += REWARD["health_loss_penalty"] * 3  # 额外死亡惩罚

        # Boss被彻底击败（第6阶段血量归零）
        if state_info["boss_stage"] == 6 and state_info["boss_health"] is not None:
            if state_info["boss_health"] <= 0.01 and state_info["boss_health_changed"] > 0.1:
                reward += REWARD["boss_kill_reward"]

        return reward

    def _check_done(self, state_info):
        """
        检查是否结束

        结束条件:
        1. 玩家血量归零（死亡）
        2. Boss被彻底击败（第6阶段血量归零）
        3. 达到最大步数
        """
        if state_info is None:
            return False

        # 玩家死亡
        if not state_info["is_alive"]:
            return True

        # Boss被彻底击败（Stage 6且血量接近0）
        if (state_info["boss_stage"] == 6 and
            state_info["boss_health"] is not None and
            state_info["boss_health"] <= 0.01):
            return True

        # 达到最大步数
        if self.episode_steps >= self.max_steps:
            return True

        return False

    def reset(self, seed=None, options=None):
        """重置环境"""
        super().reset(seed=seed)

        # 释放所有按键
        self.controller.reset()

        # 重置状态提取器
        self.extractor.reset()

        # 重置状态
        self.episode_steps = 0
        self.total_reward = 0.0
        self.done = False
        self.prev_state_info = None

        # 初始化帧堆叠
        obs = self._get_observation()
        self.frame_stack = np.repeat(obs, self.frame_stack_size, axis=0)

        # 等待游戏准备
        time.sleep(0.5)

        info = {
            "game": "Touhou Hero of Ice Fairy",
            "exe": "Touhou Hero of Ice Fairy.exe",
            "action_space_size": self.action_size,
        }
        return self.frame_stack, info

    def step(self, action):
        """执行一步"""
        self.episode_steps += 1

        # 解码动作
        action_dict = self._action_to_dict(action)

        # 执行动作
        self.controller.execute_action(action_dict)

        # 等待一帧
        time.sleep(self.frame_time)

        # 获取新的观察
        obs = self._get_observation()

        # 更新帧堆叠
        self.frame_stack = np.roll(self.frame_stack, -obs.shape[0], axis=0)
        self.frame_stack[-obs.shape[0]:] = obs

        # 提取游戏状态
        state_info = self.extractor.extract(self.last_raw_frame)

        # 计算奖励
        reward = self._get_reward(state_info, action_dict)
        self.total_reward += reward

        # 检查是否结束
        terminated = self._check_done(state_info)
        truncated = self.episode_steps >= self.max_steps
        self.done = terminated or truncated

        info = {
            "episode_steps": self.episode_steps,
            "total_reward": self.total_reward,
            "state_info": state_info,
        }

        return self.frame_stack, reward, terminated, truncated, info

    def render(self):
        """渲染"""
        if self.render_mode == "human":
            import cv2
            if self.last_raw_frame is not None:
                # 在画面上叠加状态信息
                display = self.last_raw_frame.copy()
                state_info = self.extractor.extract(self.last_raw_frame)

                if state_info:
                    texts = [
                        f"Step: {self.episode_steps}",
                        f"HP: {state_info['health']}/6" if state_info['health'] else "HP: N/A",
                        f"Boss: {state_info['boss_health']:.1%}" if state_info['boss_health'] else "Boss: N/A",
                        f"Stage: {state_info['boss_stage']}/6" if state_info['boss_stage'] else "Stage: N/A",
                        f"Reward: {self.total_reward:.1f}",
                    ]
                    y = 30
                    for text in texts:
                        cv2.putText(display, text, (display.shape[1] - 250, y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        y += 25

                # 创建可调整大小的窗口（首次显示时初始化）
                window_name = "Touhou RL"
                try:
                    cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
                except cv2.error:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(window_name, 1280, 800)

                cv2.imshow(window_name, display)
                cv2.waitKey(1)
        elif self.render_mode == "rgb_array":
            return self.last_raw_frame

    def close(self):
        """关闭环境"""
        self.controller.reset()
        if self.render_mode == "human":
            import cv2
            cv2.destroyAllWindows()


class TouhouEnvSimple(TouhouEnv):
    """
    简化版环境 - 使用更简单的观察空间（适合快速测试）
    """

    def __init__(self, render_mode=None, fps=30):
        super().__init__(render_mode, fps)

        self.observation_space = spaces.Box(
            low=0.0, high=1.0,
            shape=(self.frame_stack_size * (1 if VISION["grayscale"] else 3),
                   VISION["resize_height"], VISION["resize_width"]),
            dtype=np.float32
        )

    def reset(self, seed=None, options=None):
        obs, info = super().reset(seed, options)
        return self.frame_stack, info

    def step(self, action):
        return super().step(action)


if __name__ == '__main__':
    # 测试环境
    print("="*60)
    print("测试环境")
    print("="*60)
    print("游戏: 东方冰之勇者记 (Touhou Hero of Ice Fairy)")
    print("可执行文件: Touhou Hero of Ice Fairy.exe")
    print()

    env = TouhouEnv(render_mode="human")

    print(f"观察空间: {env.observation_space}")
    print(f"动作空间: {env.action_space}")
    print()

    obs, info = env.reset()
    print(f"观察形状: {obs.shape}")
    print()

    print("按 Ctrl+C 停止测试")
    print()

    try:
        for i in range(100):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            state = info.get("state_info", {})
            boss_hp = state.get('boss_health')
            boss_hp_str = f"{boss_hp:.1%}" if boss_hp is not None else 'N/A'
            print(f"Step {i}: reward={reward:+.2f}, "
                  f"HP={state.get('health', 'N/A')}, "
                  f"Boss={boss_hp_str}, "
                  f"Stage={state.get('boss_stage', 'N/A')}")

            if terminated or truncated:
                print("Episode finished")
                break
    except KeyboardInterrupt:
        print("\n测试已停止")
    finally:
        env.close()
