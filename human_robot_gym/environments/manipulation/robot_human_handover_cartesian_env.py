"""This file describes a variant for the pick place task
where the robot should place the object onto the hand of the human.

Author
    Felix Trost (FT)

Changelog:
    06.02.23 FT File creation
"""
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from robosuite.models.arenas import TableArena
from robosuite.models.objects.primitive.box import BoxObject
from robosuite.utils.placement_samplers import ObjectPositionSampler
from robosuite.utils.observables import Observable, sensor

from human_robot_gym.environments.manipulation.human_env import HumanEnv
from human_robot_gym.utils.mjcf_utils import xml_path_completion
from human_robot_gym.utils.pairing import cantor_pairing


class RobotHumanHandoverCart(HumanEnv):
    """This class corresponds to the pick place task for a single robot arm in a human environment
    where the robot should place the object onto the hand of the human.

    Args:
        robots (str or list of str): Specification for specific robot arm(s) to be instantiated within this env
            (e.g: "Sawyer" would generate one arm; ["Panda", "Panda", "Sawyer"] would generate three robot arms)
            Note: Must be a single single-arm robot!

        robot_base_offset (None or list[double] or list[list[double]]): Offset (x, y, z) of the robot bases.
            If more than one robot is loaded provide a list of doubles, one for each robot.
            Specify None for an offset of (0, 0, 0) for each robot.

        env_configuration (str): Specifies how to position the robots within the environment (default is "default").
            For most single arm environments, this argument has no impact on the robot setup.

        controller_configs (None or str or list of dict): If set, contains relevant controller parameters for creating a
            custom controller. Else, uses the default controller for this specific task. Should either be single
            dict if same controller is to be used for all robots or else it should be a list of the same length as
            "robots" param

        gripper_types (str or list of str): type of gripper, used to instantiate
            gripper models from gripper factory. Default is "default", which is the default grippers(s) associated
            with the robot(s) the 'robots' specification. None removes the gripper, and any other (valid) model
            overrides the default gripper. Should either be single str if same gripper type is to be used for all
            robots or else it should be a list of the same length as "robots" param

        initialization_noise (dict or list of dict): Dict containing the initialization noise parameters.
            The expected keys and corresponding value types are specified below:

            :`'magnitude'`: The scale factor of uni-variate random noise applied to each of a robot's given initial
                joint positions. Setting this value to `None` or 0.0 results in no noise being applied.
                If "gaussian" type of noise is applied then this magnitude scales the standard deviation applied,
                If "uniform" type of noise is applied then this magnitude sets the bounds of the sampling range
            :`'type'`: Type of noise to apply. Can either specify "gaussian" or "uniform"

            Should either be single dict if same noise value is to be used for all robots or else it should be a
            list of the same length as "robots" param

            :Note: Specifying "default" will automatically use the default noise settings.
                Specifying None will automatically create the required dict with "magnitude" set to 0.0.

        table_full_size (3-tuple): x, y, and z dimensions of the table.

        table_friction (3-tuple): the three mujoco friction parameters for
            the table.

        use_camera_obs (bool): if True, every observation includes rendered image(s)

        use_object_obs (bool): if True, include object information in the observation.

        reward_scale (None or float): Scales the normalized reward function by the amount specified.
            If None, environment reward remains unnormalized

        reward_shaping (bool): if True, use dense rewards, else use sparse rewards.

        goal_dist (double): Distance threshold for reaching the goal.

        collision_reward (double): Reward to be given in the case of a collision.

        goal_reward (double): Reward to be given in the case of reaching the goal.

        object_gripped_reward (double): Additional reward for gripping the object when `reward_shaping=False`.
            If object is not gripped: `reward = -1`.
            If object gripped but not at the target: `object_gripped_reward`.
            If object is at the target: `reward = goal_reward`.
            `object_gripped_reward` defaults to -1.

        object_placement_initializer (ObjectPositionSampler): if provided, will
            be used to place objects on every reset, else a UniformRandomSampler
            is used by default.
            Objects are elements that can and should be manipulated.

        target_placement_initializer (ObjectPositionSampler): if provided, will
            be used to generate target locations every time the previous target was reached
            and on resets. If not set, a UniformRandomSampler is used by default.
            Targets specify the coordinates to which the object should be moved.

        obstacle_placement_initializer (ObjectPositionSampler): if provided, will
            be used to place obstacles on every reset, else a UniformRandomSampler
            is used by default.
            Obstacles are elements that should be avoided.

        has_renderer (bool): If true, render the simulation state in
            a viewer instead of headless mode.

        has_offscreen_renderer (bool): True if using off-screen rendering

        render_camera (str): Name of camera to render if `has_renderer` is True. Setting this value to 'None'
            will result in the default angle being applied, which is useful as it can be dragged / panned by
            the user using the mouse

        render_collision_mesh (bool): True if rendering collision meshes in camera. False otherwise.

        render_visual_mesh (bool): True if rendering visual meshes in camera. False otherwise.

        render_gpu_device_id (int): corresponds to the GPU device id to use for offscreen rendering.
            Defaults to -1, in which case the device will be inferred from environment variables
            (GPUS or CUDA_VISIBLE_DEVICES).

        control_freq (float): how many control signals to receive in every second. This sets the amount of
            simulation time that passes between every action input.

        horizon (int): Every episode lasts for exactly @horizon action steps.

        ignore_done (bool): True if never terminating the environment (ignore @horizon).

        hard_reset (bool): If True, re-loads model, sim, and render object upon a reset call, else,
            only calls self.sim.reset and resets all robosuite-internal variables

        camera_names (str or list of str): name of camera to be rendered. Should either be single str if
            same name is to be used for all cameras' rendering or else it should be a list of cameras to render.

            :Note: At least one camera must be specified if @use_camera_obs is True.

            :Note: To render all robots' cameras of a certain type (e.g.: "robotview" or "eye_in_hand"), use the
                convention "all-{name}" (e.g.: "all-robotview") to automatically render all camera images from each
                robot's camera list).

        camera_heights (int or list of int): height of camera frame. Should either be single int if
            same height is to be used for all cameras' frames or else it should be a list of the same length as
            "camera names" param.

        camera_widths (int or list of int): width of camera frame. Should either be single int if
            same width is to be used for all cameras' frames or else it should be a list of the same length as
            "camera names" param.

        camera_depths (bool or list of bool): True if rendering RGB-D, and RGB otherwise. Should either be single
            bool if same depth setting is to be used for all cameras or else it should be a list of the same length as
            "camera names" param.

        camera_segmentations (None or str or list of str or list of list of str): Camera segmentation(s) to use
            for each camera. Valid options are:

                `None`: no segmentation sensor used
                `'instance'`: segmentation at the class-instance level
                `'class'`: segmentation at the class level
                `'element'`: segmentation at the per-geom level

            If not None, multiple types of segmentations can be specified. A [list of str / str or None] specifies
            [multiple / a single] segmentation(s) to use for all cameras. A list of list of str specifies per-camera
            segmentation setting(s) to use.

        renderer (str): string for the renderer to use

        renderer_config (dict): dictionary for the renderer configurations

        use_failsafe_controller (bool): Whether or not the safety shield / failsafe controller should be active

        visualize_failsafe_controller (bool): Whether or not the reachable sets of the failsafe controller should be
            visualized

        visualize_pinocchio (bool): Whether or pinocchios (collision prevention static env) should be visualized

        control_sample_time (double): Control frequency of the failsafe controller

        human_animation_names (list[str]): Human animations to play

        base_human_pos_offset (list[double]): Base human animation offset

        human_animation_freq (double): Speed of the human animation in fps.

        human_rand (list[double]): Max. randomization of the human [x-pos, y-pos, z-angle]

        safe_vel (double): Safe cartesian velocity. The robot is allowed to move with this velocity in the vacinity of
            humans.

        self_collision_safety (double): Safe distance for self collision detection

        seed (int): Random seed for np.random

        verbose (bool): If True, print out debug information

        done_at_collision (bool): If True, the episode is terminated when a collision occurs

        done_at_success (bool): If True, the episode is terminated when the goal is reached

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
        use_camera_obs: bool = True,
        use_object_obs: bool = True,
        reward_scale: Optional[float] = 1.0,
        reward_shaping: bool = False,
        goal_dist: float = 0.1,
        collision_reward: float = -10,
        goal_reward: float = 1,
        object_gripped_reward: float = -1,
        object_placement_initializer: Optional[ObjectPositionSampler] = None,
        target_placement_initializer: Optional[ObjectPositionSampler] = None,
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
            "RobotHumanHandover/0",
            "RobotHumanHandover/1",
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
        self.table_full_size = table_full_size
        self.table_friction = table_friction
        self.table_offset = np.array([0.0, 0.0, 0.82])
        self.reward_scale = reward_scale
        self.reward_shaping = reward_shaping
        self.collision_reward = collision_reward
        self.goal_reward = goal_reward
        self.object_gripped_reward = object_gripped_reward
        self.goal_dist = goal_dist
        self.object_placement_initializer = object_placement_initializer
        self.obstacle_placement_initializer = obstacle_placement_initializer
        self.box_body_id = None
        self.done_at_collision = done_at_collision
        self.done_at_success = done_at_success
        self.target_pos = None

        super().__init__(
            robots=robots,
            robot_base_offset=robot_base_offset,
            env_configuration=env_configuration,
            controller_configs=controller_configs,
            gripper_types=gripper_types,
            initialization_noise=initialization_noise,
            use_camera_obs=use_camera_obs,
            use_object_obs=use_object_obs,
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
        )

    def step(self, action):
        obs, reward, done, info = super().step(action)
        if self.goal_reached:
            object_placements = self.object_placement_initializer.sample()
            for obj_pos, obj_quat, obj in object_placements.values():
                self.sim.data.set_joint_qpos(
                    obj.joints[0],
                    np.concatenate([obj_pos, obj_quat])
                )
            self.goal_reached = False
        if self.has_renderer:
            self._visualize_goal()
            self._visualize_object_sample_space()

        return obs, reward, done, info

    def reward(
        self,
        achieved_goal: np.ndarray,
        desired_goal: np.ndarray,
        info: Dict[str, Any],
    ) -> float:
        object_gripped = bool(achieved_goal[6])

        reward = -1

        if self._check_success(achieved_goal, desired_goal):
            reward = self.goal_reward
        elif object_gripped:
            reward = self.object_gripped_reward

        if self.reward_shaping:
            eef_pos = achieved_goal[:3]
            obj_pos = achieved_goal[3:6]
            reward += 1.0
            eef_to_obj = np.linalg.norm(obj_pos - eef_pos)
            obj_to_target = np.linalg.norm(desired_goal - obj_pos)
            reward -= (eef_to_obj * 0.2 + obj_to_target) * 0.1

        if info["collision"]:
            reward += self.collision_reward

        return reward * self.reward_scale

    def _check_success(
        self,
        achieved_goal: List[float],
        desired_goal: List[float],
    ) -> bool:
        dist_to_target = np.linalg.norm(achieved_goal[3:6] - desired_goal)
        return dist_to_target <= self.goal_dist

    def _check_done(
        self,
        achieved_goal: np.ndarray,
        desired_goal: np.ndarray,
        info: Dict[str, Any],
    ) -> bool:
        if self.done_at_collision and info["collision"]:
            return True
        if self.done_at_success and self._check_success(achieved_goal, desired_goal):
            return True
        return False

    def _get_achieved_goal_from_obs(
        self,
        observation: Dict[str, Any],
    ) -> np.ndarray:
        return np.concatenate(
            [
                observation[f"{self.robots[0].robot_model.naming_prefix}eef_pos"],
                observation["object_pos"],
                [observation["object_gripped"]],
            ]
        )

    def _get_desired_goal_from_obs(
        self,
        observation: Dict[str, Any],
    ) -> np.ndarray:
        return observation["target_pos"]

    def _reset_internal(self):
        self.robots[0].init_qpos = np.array([0.0, 0.0, -np.pi / 2, 0, -np.pi / 2, np.pi / 4])

        super()._reset_internal()

    def _setup_arena(self):
        self.mujoco_arena = TableArena(
            table_full_size=self.table_full_size,
            table_offset=self.table_offset,
            xml=xml_path_completion("arenas/table_arena.xml"),
        )

        self._set_origin()

        self._set_mujoco_camera()

        box_size = np.array([0.04, 0.04, 0.04])
        box = BoxObject(
            name="smallBox",
            size=box_size * 0.5,
            rgba=[0.1, 0.7, 0.3, 1],
        )
        self.objects = [box]
        object_bin_boundaries = self._get_object_bin_boundaries()
        self.object_placement_initializer = self._setup_placement_initializer(
            name="ObjectSampler",
            initializer=self.object_placement_initializer,
            objects=self.objects,
            x_range=[object_bin_boundaries[0], object_bin_boundaries[1]],
            y_range=[object_bin_boundaries[2], object_bin_boundaries[3]],
        )

        # << OBSTACLES >>
        self._setup_collision_objects(
            add_table=True,
            add_base=True,
            safety_margin=0.00
        )
        # Obstacles are elements that the robot should avoid.
        self.obstacles = []
        self.obstacle_placement_initializer = self._setup_placement_initializer(
            name="ObstacleSampler",
            initializer=self.obstacle_placement_initializer,
            objects=self.obstacles,
        )

    def _setup_references(self):
        super()._setup_references()

        assert len(self.objects) == 1
        self.box_body_id = self.sim.model.body_name2id(self.objects[0].root_body)

    def _setup_observables(self):
        observables = super()._setup_observables()
        # robot joint pos
        prefix = self.robots[0].robot_model.naming_prefix
        if prefix + "joint_pos" in observables:
            observables[prefix + "joint_pos"].set_active(False)
        if prefix + "joint_vel" in observables:
            observables[prefix + "joint_vel"].set_active(False)
        if prefix + "eef_pos" in observables:
            observables[prefix + "eef_pos"].set_active(True)
        if "human_joint_pos" in observables:
            observables["human_joint_pos"].set_active(True)
        if prefix + "joint_pos_cos" in observables:
            observables[prefix + "joint_pos_cos"].set_active(False)
        if prefix + "joint_pos_sin" in observables:
            observables[prefix + "joint_pos_sin"].set_active(False)
        if prefix + "gripper_qpos" in observables:
            observables[prefix + "gripper_qpos"].set_active(True)
        if prefix + "gripper_qvel" in observables:
            observables[prefix + "gripper_qvel"].set_active(True)
        if prefix + "eef_quat" in observables:
            observables[prefix + "eef_quat"].set_active(False)
        if "gripper_pos" in observables:
            observables["gripper_pos"].set_active(False)

        # low-level object information
        goal_mod = "goal"
        obj_mod = "object"
        pf = self.robots[0].robot_model.naming_prefix

        # Absolute coordinates of goal position
        @sensor(modality=goal_mod)
        def target_pos(obs_cache) -> np.ndarray:
            if self.human_animation_data[self.human_animation_id][1]["hand_to_place_on"] == "right":
                self.target_pos = self.sim.data.get_site_xpos(self.human.right_hand)
            elif self.human_animation_data[self.human_animation_id][1]["hand_to_place_on"] == "left":
                self.target_pos = self.sim.data.get_site_xpos(self.human.left_hand)

            self.target_pos += np.array([0, 0, 0.05])
            return self.target_pos

        # Absolute coordinates of object position
        @sensor(modality=obj_mod)
        def object_pos(obs_cache) -> np.ndarray:
            return np.array(self.sim.data.body_xpos[self.box_body_id])

        # Vector from robot end-effector to object
        @sensor(modality=obj_mod)
        def eef_to_object(obs_cache) -> np.ndarray:
            return (
                obs_cache["object_pos"] - obs_cache[f"{pf}eef_pos"]
                if "object_pos" in obs_cache and f"{pf}eef_pos" in obs_cache
                else np.zeros(3)
            )

        # Vector from object to target
        @sensor(modality=goal_mod)
        def object_to_target(obs_cache) -> np.ndarray:
            return (
                obs_cache["target_pos"] - obs_cache["object_pos"]
                if "target_pos" in obs_cache and "object_pos" in obs_cache
                else np.zeros(3)
            )

        @sensor(modality=goal_mod)
        def eef_to_target(obs_cache) -> np.ndarray:
            return (
                obs_cache["target_pos"] - obs_cache[f"{pf}eef_pos"]
                if "target_pos" in obs_cache and f"{pf}eef_pos" in obs_cache
                else np.zeros(3)
            )

        # Boolean value if the object is gripped
        # Checks if both finger pads are in contact with the object
        @sensor(modality="object")
        def object_gripped(obs_cache) -> bool:
            coll = cantor_pairing(
                self.sim.model.geom_name2id("gripper0_l_fingerpad_g0"),
                self.sim.model.geom_name2id("smallBox_g0"),
            ) in self.previous_robot_collisions and cantor_pairing(
                self.sim.model.geom_name2id("gripper0_r_fingerpad_g0"),
                self.sim.model.geom_name2id("smallBox_g0"),
            ) in self.previous_robot_collisions

            return coll

        @sensor(modality=goal_mod)
        def vec_to_next_objective(obs_cache) -> np.ndarray:
            if all([key in obs_cache for key in ["eef_to_object", "object_to_target", "object_gripped"]]):
                return obs_cache["object_to_target"] if obs_cache["object_gripped"] else obs_cache["eef_to_object"]
            else:
                return np.zeros(3)

        sensors = [
            target_pos,
            object_pos,
            eef_to_object,
            object_to_target,
            eef_to_target,
            object_gripped,
            vec_to_next_objective,
        ]

        names = [s.__name__ for s in sensors]

        # Create observables
        for name, s in zip(names, sensors):
            observables[name] = Observable(
                name=name,
                sensor=s,
                sampling_rate=self.control_freq,
            )

        return observables

    def _get_object_bin_boundaries(self) -> Tuple[float, float, float, float]:
        """Get the x and y boundaries of the object sampling space.

        Returns:
            (float, float, float, float):
                Boundaries of sampling space in the form (xmin, xmax, ymin, ymax)

        """
        bin_x_half = self.table_full_size[0] / 2 - 0.05
        bin_y_half = self.table_full_size[1] / 2 - 0.05

        return (
            bin_x_half * 0.35,
            bin_x_half * 0.6,
            bin_y_half * 0.25,
            bin_y_half * 0.45,
        )

    def _visualize_goal(self):
        return self.viewer.viewer.add_marker(
            pos=self.target_pos,
            size=[self.goal_dist, self.goal_dist, self.goal_dist],
            type=2,
            rgba=[0.0, 1.0, 0.0, 0.3],
            label="",
            shininess=0.0,
        )

    def _visualize_object_sample_space(self):
        self.draw_box(
            self._get_object_bin_boundaries() + (  # Add z boundaries
                0.8,
                0.9,
            ),
            (1.0, 0.0, 0.0, 0.3),
        )

    def draw_box(
        self,
        boundaries: Tuple[float, float, float, float, float, float],
        color: Tuple[float, float, float, float],
    ):
        """Render a box in the scene.

        Args:
            boundaries (float, float, float, float, float, float):
                Box boundaries in the form (xmin, xmax, ymin, ymax, zmin, zmax)
            color (float, float, float, float):
                Color in the form (r, g, b, a)
        """
        # Box (type 2)
        self.viewer.viewer.add_marker(
            pos=np.array([
                (boundaries[0] + boundaries[1]) / 2,
                (boundaries[2] + boundaries[3]) / 2,
                (boundaries[5] + boundaries[4]) / 2,
            ]),
            type=6,
            size=[
                (boundaries[1] - boundaries[0]) * 0.5,
                (boundaries[3] - boundaries[2]) * 0.5,
                (boundaries[5] - boundaries[4]) * 0.5,
            ],
            rgba=color,
            label="",
            shininess=0.0,
        )
