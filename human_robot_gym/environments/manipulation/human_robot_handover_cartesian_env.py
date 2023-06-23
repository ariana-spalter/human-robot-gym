"""This file describes a variant for the pick place task
where the robot should place the object onto the hand of the human.

Author
    Felix Trost (FT)

Changelog:
    16.05.23 FT File creation
"""
from enum import Enum
from typing import Any, Dict, List, Optional, OrderedDict, Tuple, Union

import xml.etree.ElementTree as ET

import numpy as np
from robosuite.utils.observables import Observable, sensor
from scipy.spatial.transform import Rotation
import mujoco_py

from robosuite.models.arenas import TableArena
from robosuite.models.objects.primitive.box import BoxObject
from robosuite.models.objects.composite import HammerObject
from robosuite.utils.placement_samplers import ObjectPositionSampler
import robosuite.utils.transform_utils as T

from human_robot_gym.environments.manipulation.human_env import COLLISION_TYPE
from human_robot_gym.environments.manipulation.pick_place_human_cartesian_env import PickPlaceHumanCart
from human_robot_gym.utils.mjcf_utils import xml_path_completion, rot_to_quat, quat_to_rot
from human_robot_gym.utils.pairing import cantor_pairing
from human_robot_gym.utils.animation_utils import (
    sin_modulation, layered_sin_modulations, sample_animation_loop_properties
)


class HumanRobotHandoverPhase(Enum):
    APPROACH = 0
    PRESENT = 1
    WAIT = 2
    RETREAT = 3
    COMPLETE = 4


class HumanRobotHandoverCart(PickPlaceHumanCart):
    """This class corresponds to the pick place task for a single robot arm in a human environment
    where the robot should place the object to a spot on the table the human is pointing at.

    Args:
        robots (str | List[str]): Specification for specific robot arm(s) to be instantiated within this env
            (e.g: `"Sawyer"` would generate one arm; `["Panda", "Panda", "Sawyer"]` would generate three robot arms)
            Note: Must be a single single-arm robot!

        robot_base_offset (None | List[float] | List[List[float]]): Offset (x, y, z) of the robot bases.
            If more than one robot is loaded provide a list of doubles, one for each robot.
            Specify `None` for an offset of (0, 0, 0) for each robot.

        env_configuration (str): Specifies how to position the robots within the environment (default is `"default"`).
            For most single arm environments, this argument has no impact on the robot setup.

        controller_configs (None | str | List[Dict[str, Any]]): If set, contains relevant controller parameters
            for creating a custom controller. Else, uses the default controller for this specific task.
            Should either be single dict if same controller is to be used for all robots or else it should be
            a list of the same length as `robots` param

        gripper_types (str | List[str]): type of gripper, used to instantiate
            gripper models from gripper factory. Default is `"default"`, which is the default grippers(s) associated
            with the robot(s) the `robots` specification. `None` removes the gripper, and any other (valid) model
            overrides the default gripper. Should either be single `str` if same gripper type is to be used for all
            robots or else it should be a list of the same length as the `robots` param

        initialization_noise (Dict[str, Any] | List[Dict[str, Any]]): Dict containing the initialization noise
            parameters. The expected keys and corresponding value types are specified below:

            :`'magnitude'`: The scale factor of uni-variate random noise applied to each of a robot's given initial
                joint positions. Setting this value to `None` or `0.0` results in no noise being applied.
                If `"gaussian"` type of noise is applied then this magnitude scales the standard deviation applied,
                If `"uniform"` type of noise is applied then this magnitude sets the bounds of the sampling range
            :`'type'`: Type of noise to apply. Can either specify `"gaussian"` or `"uniform"`

            Should either be single dict if same noise value is to be used for all robots or else it should be a
            list of the same length as `robots` param

            :Note: Specifying `"default"` will automatically use the default noise settings.
                Specifying `None` will automatically create the required dict with `"magnitude"` set to `0.0`.

        table_full_size (Tuple[float, float, float]): x, y, and z dimensions of the table.

        table_friction (Tuple[float, float, float]): the three mujoco friction parameters for
            the table.

        object_full_size (Tuple[float, float, float]): x, y, and z dimensions of the cube object that should be moved.

        use_camera_obs (bool): if `True`, every observation includes rendered image(s)

        use_object_obs (bool): if `True`, include object information in the observation.

        reward_scale (None | float): Scales the normalized reward function by the amount specified.
            If `None`, environment reward remains unnormalized

        reward_shaping (bool): if `True`, use dense rewards, else use sparse rewards.

        goal_dist (float): Distance threshold for reaching the goal.

        collision_reward (float): Reward to be given in the case of a collision.

        task_reward (float): Reward to be given in the case of completing the task (i.e. finishing the animation).

        object_at_target_reward (float): Reward if the object is within `goal_dist` of the target.

        object_gripped_reward (float): Additional reward for gripping the object when `reward_shaping=False`.
            If object is not gripped: `reward = -1`.
            If object gripped but not at the target: `object_gripped_reward`.
            If object is at the target: `reward = `object_at_target_reward`.
            If task completed (animation finished): `reward = task_reward`.
            `object_gripped_reward` defaults to `-1`.

        object_placement_initializer (ObjectPositionSampler): if provided, will
            be used to place objects on every reset, else a `UniformRandomSampler`
            is used by default.
            Objects are elements that can and should be manipulated.

        obstacle_placement_initializer (ObjectPositionSampler): if provided, will
            be used to place obstacles on every reset, else a `UniformRandomSampler`
            is used by default.
            Obstacles are elements that should be avoided.

        has_renderer (bool): If `True`, render the simulation state in
            a viewer instead of headless mode.

        has_offscreen_renderer (bool): `True` if using off-screen rendering

        render_camera (str): Name of camera to render if `has_renderer` is `True`. Setting this value to `None`
            will resul` in the default angle being applied, which is useful as it can be dragged / panned by
            the user using the mouse

        render_collision_mesh (bool): `True` if rendering collision meshes in camera. `False` otherwise.

        render_visual_mesh (bool): `True` if rendering visual meshes in camera. `False` otherwise.

        render_gpu_device_id (int): corresponds to the GPU device id to use for offscreen rendering.
            Defaults to `-1`, in which case the device will be inferred from environment variables
            (`GPUS` or `CUDA_VISIBLE_DEVICES`).

        control_freq (float): how many control signals to receive in every second. This sets the amount of
            simulation time that passes between every action input.

        horizon (int): Every episode lasts for exactly `horizon` action steps.

        ignore_done (bool): `True` if never terminating the environment (ignore `horizon`).

        hard_reset (bool): If `True`, re-loads model, sim, and render object upon a `reset` call, else,
            only calls `self.sim.reset` and resets all robosuite-internal variables

        camera_names (str | List[str]): name of camera to be rendered. Should either be single `str` if
            same name is to be used for all cameras' rendering or else it should be a list of cameras to render.

            :Note: At least one camera must be specified if `use_camera_obs` is `True`.

            :Note: To render all robots' cameras of a certain type (e.g.: `"robotview"` or `"eye_in_hand"`), use the
                convention `"all-{name}"` (e.g.: `"all-robotview"`) to automatically render all camera images from each
                robot's camera list).

        camera_heights (int | List[int]): height of camera frame. Should either be single `int` if
            same height is to be used for all cameras' frames or else it should be a list of the same length as
            `camera_names` param.

        camera_widths (int | List[int]): width of camera frame. Should either be single `int` if
            same width is to be used for all cameras' frames or else it should be a list of the same length as
            `camera_names` param.

        camera_depths (bool | List[bool]): `True` if rendering RGB-D, and RGB otherwise. Should either be single
            bool if same depth setting is to be used for all cameras or else it should be a list of the same length as
            `camera_names` param.

        camera_segmentations (None | str | List[str] | List[List[str]]): Camera segmentation(s) to use
            for each camera. Valid options are:

                `None`: no segmentation sensor used
                `'instance'`: segmentation at the class-instance level
                `'class'`: segmentation at the class level
                `'element'`: segmentation at the per-geom level

            If not `None`, multiple types of segmentations can be specified. A [List[str] / str | None] specifies
            [multiple / a single] segmentation(s) to use for all cameras. A List[List[str]] specifies per-camera
            segmentation setting(s) to use.

        renderer (str): string for the renderer to use

        renderer_config (dict): dictionary for the renderer configurations

        use_failsafe_controller (bool): Whether or not the safety shield / failsafe controller should be active

        visualize_failsafe_controller (bool): Whether or not the reachable sets of the failsafe controller should be
            visualized

        visualize_pinocchio (bool): Whether or not pinocchio (collision prevention static env) should be visualized

        control_sample_time (float): Control frequency of the failsafe controller

        human_animation_names (List[str]): Human animations to play

        base_human_pos_offset (List[float]): Base human animation offset

        human_animation_freq (float): Speed of the human animation in fps.

        human_rand (List[float]): Max. randomization of the human [x-pos, y-pos, z-angle]

        safe_vel (float): Safe cartesian velocity. The robot is allowed to move with this velocity in the vicinity of
            humans.

        self_collision_safety (float): Safe distance for self collision detection

        seed (int): Random seed for `np.random`

        verbose (bool): If `True`, print out debug information

        done_at_collision (bool): If `True`, the episode is terminated when a collision occurs

        done_at_success (bool): If `True`, the episode is terminated when the goal is reached

    Raises:
        AssertionError: [Invalid number of robots specified]
    """
    def __init__(
        self,
        robots: Union[str, List[str]],
        robot_base_offset: Optional[Union[List[float], List[List[float]]]] = None,
        env_configuration: str = "default",
        controller_configs: Optional[Union[str, List[Dict[str, Any]]]] = None,
        gripper_types: Union[str, List[str]] = "default",
        initialization_noise: Union[str, List[str], List[Dict[str, Any]]] = "default",
        table_full_size: Tuple[float, float, float] = (1.5, 2.0, 0.05),
        table_friction: Tuple[float, float, float] = (1.0, 5e-3, 1e-4),
        object_full_size: Tuple[float, float, float] = (0.04, 0.04, 0.04),
        use_camera_obs: bool = True,
        use_object_obs: bool = True,
        reward_scale: Optional[float] = 1.0,
        reward_shaping: bool = False,
        goal_dist: float = 0.1,
        collision_reward: float = -10,
        task_reward: float = 1,
        object_at_target_reward: float = -1,
        object_gripped_reward: float = -1,
        object_placement_initializer: Optional[ObjectPositionSampler] = None,
        obstacle_placement_initializer: Optional[ObjectPositionSampler] = None,
        has_renderer: bool = False,
        has_offscreen_renderer: bool = True,
        render_camera: str = "frontview",
        render_collision_mesh: bool = False,
        render_visual_mesh: bool = True,
        render_gpu_device_id: int = -1,
        control_freq: float = 10,
        horizon: int = 1000,
        ignore_done: bool = False,
        hard_reset: bool = True,
        camera_names: Union[str, List[str]] = "frontview",
        camera_heights: Union[int, List[int]] = 256,
        camera_widths: Union[int, List[int]] = 256,
        camera_depths: Union[bool, List[bool]] = False,
        camera_segmentations: Optional[Union[str, List[str], List[List[str]]]] = None,
        renderer: str = "mujoco",
        renderer_config: Dict[str, Any] = None,
        use_failsafe_controller: bool = True,
        visualize_failsafe_controller: bool = False,
        visualize_pinocchio: bool = False,
        control_sample_time: float = 0.004,
        human_animation_names: List[str] = [
            "HumanRobotHandover/0",
            # "HumanRobotHandover/1",
        ],
        base_human_pos_offset: List[float] = [0.0, 0.0, 0.0],
        human_animation_freq: float = 30,
        human_rand: List[float] = [0.0, 0.0, 0.0],
        safe_vel: float = 0.001,
        self_collision_safety: float = 0.01,
        seed: int = 0,
        verbose: bool = False,
        done_at_collision: bool = False,
        done_at_success: bool = False,
    ):
        self.handover_phase: HumanRobotHandoverPhase = HumanRobotHandoverPhase.COMPLETE
        self._manipulation_object_weld_eq_id = None
        self._n_delayed_timesteps = None

        # Characteristics of the wait phase: The animation time is modulated by multiple layered
        # sine functions. The amplitudes and frequencies of these functions are obtained from the
        # animation info file with additional randomization.
        self._wait_animation_loop_amplitudes = None
        self._wait_animation_loop_speeds = None

        self.object_at_target_reward = object_at_target_reward

        super().__init__(
            robots=robots,
            robot_base_offset=robot_base_offset,
            env_configuration=env_configuration,
            controller_configs=controller_configs,
            gripper_types=gripper_types,
            initialization_noise=initialization_noise,
            table_full_size=table_full_size,
            table_friction=table_friction,
            object_full_size=object_full_size,
            use_camera_obs=use_camera_obs,
            use_object_obs=use_object_obs,
            reward_scale=reward_scale,
            reward_shaping=reward_shaping,
            goal_dist=goal_dist,
            collision_reward=collision_reward,
            task_reward=task_reward,
            object_gripped_reward=object_gripped_reward,
            object_placement_initializer=object_placement_initializer,
            target_placement_initializer=None,
            obstacle_placement_initializer=obstacle_placement_initializer,
            has_renderer=has_renderer,
            has_offscreen_renderer=has_offscreen_renderer,
            render_camera=render_camera,
            render_collision_mesh=render_collision_mesh,
            render_visual_mesh=render_visual_mesh,
            render_gpu_device_id=render_gpu_device_id,
            control_freq=control_freq,
            horizon=horizon,
            ignore_done=ignore_done,
            hard_reset=hard_reset,
            camera_names=camera_names,
            camera_heights=camera_heights,
            camera_widths=camera_widths,
            camera_depths=camera_depths,
            camera_segmentations=camera_segmentations,
            renderer=renderer,
            renderer_config=renderer_config,
            use_failsafe_controller=use_failsafe_controller,
            visualize_failsafe_controller=visualize_failsafe_controller,
            visualize_pinocchio=visualize_pinocchio,
            control_sample_time=control_sample_time,
            human_animation_names=human_animation_names,
            base_human_pos_offset=base_human_pos_offset,
            human_animation_freq=human_animation_freq,
            human_rand=human_rand,
            safe_vel=safe_vel,
            self_collision_safety=self_collision_safety,
            seed=seed,
            verbose=verbose,
            done_at_collision=done_at_collision,
            done_at_success=done_at_success,
        )

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        obs, rew, done, info = super().step(action)

        if self.handover_phase == HumanRobotHandoverPhase.PRESENT and obs["object_gripped"]:
            self._human_drop_object()
            self.handover_phase = HumanRobotHandoverPhase.WAIT
        elif self.handover_phase == HumanRobotHandoverPhase.WAIT and self._check_object_in_target_zone(
            achieved_goal=self._get_achieved_goal_from_obs(obs),
            desired_goal=self._get_desired_goal_from_obs(obs),
        ):
            self.handover_phase = HumanRobotHandoverPhase.RETREAT

        return obs, rew, done, info

    def _setup_arena(self):
        """Setup the mujoco arena.

        Must define `self.mujoco_arena`.
        Defines `self.objects` and `self.obstacles`.
        """
        self.mujoco_arena = TableArena(
            table_full_size=self.table_full_size,
            table_offset=self.table_offset,
            xml=xml_path_completion("arenas/table_arena.xml"),
        )

        self._set_origin()

        self._set_mujoco_camera()

        box_size = np.array(self.object_full_size)

        self.manipulation_object = HammerObject(
            name="manipulation_object",
            handle_length=(0.35, 0.45),
        )

        self.objects = [
            self.manipulation_object,
        ]

        # object_bin_boundaries = self._get_default_object_bin_boundaries()
        self.object_placement_initializer = self._setup_placement_initializer(
            name="ObjectSampler",
            initializer=self.object_placement_initializer,
            objects=[],
        )

        # << TARGETS >>
        # Targets specify the coordinates to which the object should be moved.
        target = BoxObject(
            name="target",
            size=box_size * 0.5,
            rgba=[0.9, 0.1, 0.1, 1],
        )

        target_bin_boundaries = self._get_default_target_bin_boundaries()
        self.target_placement_initializer = self._setup_placement_initializer(
            name="TargetSampler",
            initializer=self.target_placement_initializer,
            objects=[target],
            x_range=[target_bin_boundaries[0], target_bin_boundaries[1]],
            y_range=[target_bin_boundaries[2], target_bin_boundaries[3]],
            z_offset=box_size[2] * 0.5,
        )

        # << OBSTACLES >>
        self._setup_collision_objects(
            add_table=True,
            add_base=True,
            safety_margin=0.0
        )
        # Obstacles are elements that the robot should avoid.
        self.obstacles = []
        self.obstacle_placement_initializer = self._setup_placement_initializer(
            name="ObstacleSampler",
            initializer=self.obstacle_placement_initializer,
            objects=self.obstacles,
        )

    def _postprocess_model(self):
        super()._postprocess_model()

        mocap_object = ET.Element(
            "body", name="mocap_object", pos="0 0 0", quat="0 0 0 1", mocap="true"
        )

        self.model.worldbody.append(mocap_object)

        self.model.equality.append(
            ET.Element(
                "weld",
                name="manipulation_object_weld",
                body1="mocap_object",
                body2="manipulation_object_root",
                relpose="0 -0.03 -0.26 0 0 0 1",
                solref="-700 -100",
            )
        )

    def _setup_references(self):
        super()._setup_references()
        self._manipulation_object_weld_eq_id = mujoco_py.functions.mj_name2id(
            self.sim.model, mujoco_py.const.OBJ_EQUALITY, "manipulation_object_weld"
        )

        assert self._manipulation_object_weld_eq_id != -1

    def _check_success(self, achieved_goal: List[float], desired_goal: List[float]) -> bool:
        return self.handover_phase == HumanRobotHandoverPhase.COMPLETE

    def reward(
        self,
        achieved_goal: List[float],
        desired_goal: List[float],
        info: Dict[str, Any],
    ) -> float:
        object_gripped = bool(achieved_goal[6])

        reward = -1

        if self.reward_shaping:
            # TODO implement reward shaping
            pass
        else:
            if self._check_success(achieved_goal=achieved_goal, desired_goal=desired_goal):
                reward = self.task_reward
            elif self._check_object_in_target_zone(achieved_goal=achieved_goal, desired_goal=desired_goal):
                reward = self.object_at_target_reward
            elif object_gripped:
                reward = self.object_gripped_reward

        if COLLISION_TYPE(info["collision_type"]) not in (COLLISION_TYPE.NULL | COLLISION_TYPE.ALLOWED):
            reward += self.collision_reward

        if self.reward_scale is not None:
            reward *= self.reward_scale

        return reward

    def _compute_animation_time(self, control_time: int) -> int:
        animation_time = super()._compute_animation_time(control_time)
        classic_animation_time = animation_time

        animation_length = self.human_animation_data[self.human_animation_id][0]["Pelvis_pos_x"].shape[0]
        keyframes = self.human_animation_data[self.human_animation_id][1]["keyframes"]

        # Progress to present phase automatically depending on the animation
        if animation_time > keyframes[0] and self.handover_phase == HumanRobotHandoverPhase.APPROACH:
            self.handover_phase = HumanRobotHandoverPhase.PRESENT

        # Within the present phase loop back and forth between the two keyframes enclosing it
        if (
            animation_time > keyframes[0] + (keyframes[1] - keyframes[0]) / 2 and
            self.handover_phase == HumanRobotHandoverPhase.PRESENT
        ):
            animation_time = int(
                sin_modulation(
                    classic_animation_time=classic_animation_time,
                    modulation_start_time=(keyframes[0] + keyframes[1]) / 2,
                    amplitude=(keyframes[1] - keyframes[0]) / 2,
                    speed=1,
                )
            )

            self._n_delayed_timesteps[0] = classic_animation_time - animation_time

        # In the wait phase loop around the second keyframe
        if self.handover_phase == HumanRobotHandoverPhase.WAIT:
            animation_time = int(
                layered_sin_modulations(
                    classic_animation_time=animation_time - self._n_delayed_timesteps[0],
                    modulation_start_time=keyframes[1],
                    amplitudes=self._wait_animation_loop_amplitudes,
                    speeds=self._wait_animation_loop_speeds,
                )
            )

            self._n_delayed_timesteps[1] = classic_animation_time - animation_time

        # In the retreat phase run the animation linearly until it is finished
        if self.handover_phase == HumanRobotHandoverPhase.RETREAT:
            animation_time -= self._n_delayed_timesteps[1]

        # Once the animation is complete, freeze the animation time at the last frame
        if animation_time >= animation_length - 1:
            self.handover_phase = HumanRobotHandoverPhase.COMPLETE
            animation_time = animation_length - 1

        return animation_time

    def _control_human(self):
        super()._control_human()

        object_holding_hand = self.human_animation_data[self.human_animation_id][1]["object_holding_hand"]

        if object_holding_hand == "left":
            hand_body_name = "Human_L_Hand"
        elif object_holding_hand == "right":
            hand_body_name = "Human_R_Hand"
        else:
            raise ValueError(
                f"Animation info file does not specify a valid value for object_holding_hand: {object_holding_hand}"
            )

        hand_rot = quat_to_rot(self.sim.data.get_body_xquat(hand_body_name))

        pos_offset_towards_thumb = hand_rot.apply(np.array([0, 0, 1])) * 0.03

        if object_holding_hand == "left":
            hand_rot *= Rotation.from_euler("y", -np.pi / 2)
        else:
            hand_rot *= Rotation.from_euler("y", np.pi / 2)

        quat = rot_to_quat(hand_rot)

        self.sim.data.set_mocap_pos(
            "mocap_object",
            self.sim.data.get_site_xpos(hand_body_name) + pos_offset_towards_thumb
        )

        self.sim.data.set_mocap_quat(
            "mocap_object",
            quat,
        )

    def _on_goal_reached(self):
        super()._on_goal_reached()

        if not self.done_at_success:
            self._progress_to_next_animation(
                animation_start_time=int(self.low_level_time / self.human_animation_step_length)
            )

    def _reset_animation(self):
        self.handover_phase = HumanRobotHandoverPhase.APPROACH
        self._n_delayed_timesteps = [0, 0]

        self._wait_animation_loop_amplitudes, self._wait_animation_loop_speeds = sample_animation_loop_properties(
            animation_info=self.human_animation_data[self.human_animation_id][1],
        )

        self.sim.data.set_joint_qpos(
            "manipulation_object_joint0",
            np.concatenate(
                [
                    self.sim.data.get_mocap_pos("mocap_object"),
                    self.sim.data.get_mocap_quat("mocap_object"),
                ]
            )
        )

        self._human_pickup_object()

    def _progress_to_next_animation(self, animation_start_time: float):
        super()._progress_to_next_animation(animation_start_time=animation_start_time)
        self._control_human()
        self._reset_animation()

    def _reset_internal(self):
        super()._reset_internal()
        self._control_human()
        self._reset_animation()

    def _setup_observables(self) -> OrderedDict[str, Observable]:
        observables = super()._setup_observables()

        @sensor(modality="object")
        def object_gripped(obs_cache: Dict[str, Any]) -> bool:
            coll = cantor_pairing(
                self.sim.model.geom_name2id("gripper0_l_fingerpad_g0"),
                self.sim.model.geom_name2id("manipulation_object_handle"),
            ) in self.previous_robot_collisions and cantor_pairing(
                self.sim.model.geom_name2id("gripper0_r_fingerpad_g0"),
                self.sim.model.geom_name2id("manipulation_object_handle"),
            ) in self.previous_robot_collisions

            return coll

        @sensor(modality="object")
        def object_quat(obs_cache: Dict[str, Any]) -> bool:
            return T.convert_quat(self.sim.data.get_body_xquat("manipulation_object_root"), to="xyzw")

        @sensor(modality="object")
        def quat_eef_to_object(obs_cache: Dict[str, Any]) -> bool:
            if "robot0_eef_quat" not in obs_cache or "object_quat" not in obs_cache:
                return np.zeros(4)

            quat = rot_to_quat(
                quat_to_rot(obs_cache["object_quat"]) * quat_to_rot(obs_cache["robot0_eef_quat"]).inv()
            )
            return T.convert_quat(np.array(quat), "xyzw")

        sensors = [
            object_gripped,
            object_quat,
            quat_eef_to_object,
        ]

        names = [s.__name__ for s in sensors]

        for name, s in zip(names, sensors):
            observables[name] = Observable(
                name=name,
                sensor=s,
                sampling_rate=self.control_freq,
            )

        return observables

    def _set_manipulation_object_equality_status(self, status: bool):
        self.sim.model.eq_active[self._manipulation_object_weld_eq_id] = int(status)

    def _human_drop_object(self):
        self._set_manipulation_object_equality_status(False)

    def _human_pickup_object(self):
        self._set_manipulation_object_equality_status(True)

    def _get_default_target_bin_boundaries(self) -> Tuple[float, float, float, float]:
        """Get the x and y boundaries of the object sampling space.

        Returns:
            Tuple[float, float, float, float]:
                Boundaries of sampling space in the form (xmin, xmax, ymin, ymax)
        """
        bin_x_half = self.table_full_size[0] / 2 - 0.05
        bin_y_half = self.table_full_size[1] / 2 - 0.05

        return (
            bin_x_half * 0.45,
            bin_x_half * 0.85,
            -bin_y_half * 0.15,
            bin_y_half * 0.15,
        )

    def _visualize_goal(self):
        """Draw a sphere at the target location."""
        # sphere (type 2)
        if self.handover_phase == HumanRobotHandoverPhase.APPROACH:
            color = [1, 0, 0, 0.7]
        elif self.handover_phase == HumanRobotHandoverPhase.PRESENT:
            color = [1, 1, 0, 0.7]
        elif self.handover_phase == HumanRobotHandoverPhase.WAIT:
            color = [0, 1, 0, 0.7]
        else:
            color = [0, 0, 1, 0.7]

        self.viewer.viewer.add_marker(
            pos=self.target_pos,
            type=2,
            size=[self.goal_dist, self.goal_dist, self.goal_dist],
            rgba=color,
            label="",
            shininess=0.0,
        )

    def _visualize(self):
        """Visualize the goal space and the sampling space of initial object positions."""
        self._visualize_goal()
        self._visualize_target_sample_space()
