"""Demo script for the collaborative hammering environment using a failsafe controller.
Uses a scripted expert to demonstrate the environment functionality.

Pressing 'o' switches between scripted policy and keyboard control.

Can be used with our provided training function
to train a safe RL agent with work space position actions.

Available observations (possible GymWrapper keys):
    robot0_eef_pos:
        (x,y,z) absolute position the end effector position
    robot0_gripper_qpos
        (l,r) gripper joint position
    robot0_gripper_qvel
        (l,r) gripper joint velocity
    gripper_aperture
        normalized distance between the gripper fingers in [0, 1]
    vec_eef_to_human_head
        (x,y,z) vector from end effector to human head
    dist_eef_to_human_head
        euclidean distance between human head and end effector
    vec_eef_to_human_lh
        (x,y,z) vector from end effector to human left hand
    dist_eef_to_human_lh
        euclidean distance between human left hand and end effector
    vec_eef_to_human_rh
        (x,y,z) vector from end effector to human right hand
    dist_eef_to_human_rh
        euclidean distance between human right hand and end effector
    nail_pos
        (x,y,z) Absolute position of the nail in Cartesian space
    vec_eef_to_nail
        (x,y,z) Vector from end-effector to the nail
    hammer_pos
        (x,y,z) Absolute position of the hammer in Cartesian space
    hammer_quat
        (x,y,z,w) Rotation quaternion of the hammer
    vec_eef_to_hammer
        (x,y,z) Vector from the end-effector to the hammer
    quat_eef_to_hammer
        (x,y,z,w) Rotation quaternion to represent the rotation difference of end-effector and hammer
    board_pos
        (x,y,z) Absolute position of the board in Cartesian space
    board_quat
        (x,y,z,w) Rotation quaternion of the board
    vec_eef_to_board
        (x,y,z) Vector from end-effector to board
    quat_eef_to_board
        (x,y,z,w) Rotation quaternion to represent the rotation difference of end-effector and board
    hammer_gripped
        (bool) Whether the hammer is within the gripper
    nail_hammering_progress
        (float) How far the nail is driven into the board. Normalized to [0,1]
    robot0_proprio-state
        (7-tuple) concatenation of
            - robot0_eef_pos (robot0_proprio-state[0:3])
            - robot0_gripper_qpos (robot0_proprio-state[3:5])
            - robot0_gripper_qvel (robot0_proprio-state[5:7])
    object-state
        (42-tuple) concatenation of
            - gripper_aperture (object-state[0:1])
            - vec_eef_to_human_lh (object-state[1:4])
            - dist_eef_to_human_lh (object-state[4:5])
            - vec_eef_to_human_rh (object-state[5:8])
            - dist_eef_to_human_rh (object-state[8:9])
            - vec_eef_to_human_head (object-state[9:12])
            - dist_eef_to_human_head (object-state[12:13])
            - hammer_pos[13:16]
            - hammer_quat[16:20]
            - vec_eef_to_hammer[20:23]
            - quat_eef_to_hammer[23:27]
            - board_pos[27:30]
            - board_quat[30:34]
            - vec_eef_to_board[34:37]
            - quat_eef_to_board[37:41]
            - hammer_gripped[41:42]
    goal-state
        (4-tuple) concatenation of
            - nail_pos[0:3]
            - nail_hammering_progress[3:4]

Author:
    Felix Trost

Changelog:
    02.05.2023 FT File creation
"""
import robosuite as suite
import time
import numpy as np
import glfw

from robosuite.controllers import load_controller_config

from human_robot_gym.utils.mjcf_utils import file_path_completion, merge_configs
from human_robot_gym.utils.cart_keyboard_controller import KeyboardControllerAgentCart
from human_robot_gym.utils.env_util import ExpertObsWrapper
import human_robot_gym.robots  # noqa: F401
from human_robot_gym.wrappers.visualization_wrapper import VisualizationWrapper
from human_robot_gym.wrappers.collision_prevention_wrapper import (
    CollisionPreventionWrapper,
)
from human_robot_gym.wrappers.ik_position_delta_wrapper import IKPositionDeltaWrapper
from human_robot_gym.demonstrations.experts import CollaborativeHammeringCartExpert

if __name__ == "__main__":
    pybullet_urdf_file = file_path_completion(
        "models/assets/robots/schunk/robot_pybullet.urdf"
    )
    controller_config = dict()
    controller_conig_path = file_path_completion(
        "controllers/failsafe_controller/config/failsafe.json"
    )
    robot_conig_path = file_path_completion("models/robots/config/schunk.json")
    controller_config = load_controller_config(custom_fpath=controller_conig_path)
    robot_config = load_controller_config(custom_fpath=robot_conig_path)
    controller_config = merge_configs(controller_config, robot_config)
    controller_configs = [controller_config]

    rsenv = suite.make(
        "CollaborativeHammeringCart",
        robots="Schunk",  # use Schunk robot
        use_camera_obs=False,  # do not use pixel observations
        has_offscreen_renderer=False,  # not needed since not using pixel obs
        has_renderer=True,  # make sure we can render to the screen
        render_camera=None,
        render_collision_mesh=False,
        control_freq=5,  # control should happen fast enough so that simulation looks smooth
        hard_reset=False,
        horizon=1000,
        done_at_success=False,
        controller_configs=controller_configs,
        shield_type="SSM",
        visualize_failsafe_controller=False,
        visualize_pinocchio=False,
        base_human_pos_offset=[0.2, -0.9, 0.0],
        human_rand=[0, 0.0, 0.0],
        verbose=True,
        seed=0,
    )

    env = ExpertObsWrapper(
        env=rsenv,
        agent_keys=[
            "vec_eef_to_human_head",
            "vec_eef_to_human_lh",
            "vec_eef_to_human_rh",
        ],
        expert_keys=[
            "robot0_gripper_qpos",
            "vec_eef_to_nail",
        ]
    )
    env = CollisionPreventionWrapper(
        env=env, collision_check_fn=env.check_collision_action, replace_type=0,
    )
    env = VisualizationWrapper(env)
    action_limits = np.array([[-0.1, -0.1, -0.1], [0.1, 0.1, 0.1]])
    env = IKPositionDeltaWrapper(env=env, urdf_file=pybullet_urdf_file, action_limits=action_limits)
    kb_agent = KeyboardControllerAgentCart(env=env)
    expert = CollaborativeHammeringCartExpert(
        observation_space=env.observation_space,
        action_space=env.action_space,
        signal_to_noise_ratio=1,
        delta_time=0.1,
        seed=0,
    )

    use_kb_agent = False

    def switch_agent():
        global use_kb_agent
        use_kb_agent = not use_kb_agent

    kb_agent.add_keypress_callback(glfw.KEY_O, lambda *_: switch_agent())

    expert_obs_wrapper = ExpertObsWrapper.get_from_wrapped_env(env)

    for i_episode in range(20):
        observation = env.reset()
        t1 = time.time()
        t = 0
        while True:
            t += 1
            expert_observation = expert_obs_wrapper.current_expert_observation

            in_present_phase = rsenv.task_phase.value > 0
            action = np.array(
                [
                    *np.clip(
                        expert_observation["vec_eef_to_nail"] + np.array([-0.14, -0.01, np.sin(t * 0.1) * 0.1]),
                        -0.1,
                        0.1,
                    ), 1.0
                ]
            )
            action = kb_agent() if use_kb_agent else expert(obs_dict=expert_observation)

            if not in_present_phase:
                action *= 0

            if rsenv.task_phase.value > 1:
                action = action * 0.0 + np.array([0, 0, 1, 0])

            observation, reward, done, info = env.step(action)
            if done:
                print("Episode finished after {} timesteps".format(t + 1))
                break
        print("Episode {}, fps = {}".format(i_episode, t / (time.time() - t1)))
