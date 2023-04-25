"""This file describes a reach task for a single robot with a human doing tasks nearby.

This class is based on the human environment.

Owner:
    Jakob Thumm (JT)

Contributors:
    Julian Balletshofer JB
Changelog:
    2.5.22 JT Formatted docstrings
    15.7.22 JB added optional stop at collision
"""
from human_robot_gym.environments.manipulation.human_env import HumanEnv

from typing import Dict, Union, List

import numpy as np

from robosuite.models.arenas import TableArena
from robosuite.models.objects.primitive.box import BoxObject
from robosuite.utils.observables import Observable, sensor
from human_robot_gym.utils.mjcf_utils import xml_path_completion

from human_robot_gym.models.robots.manipulators.pinocchio_manipulator_model import (
    PinocchioManipulatorModel,
)


class ReachHuman(HumanEnv):
    """
    This class corresponds to the reaching task for a single robot arm in a human environment.

    Args:
        robots (str or list of str): Specification for specific robot arm(s) to be instantiated within this env
            (e.g: "Sawyer" would generate one arm; ["Panda", "Panda", "Sawyer"] would generate three robot arms)
            Note: Must be a single single-arm robot!

        robot_base_offset (None or list[double] or list[list[double]]): Offset (x, y, z) of the robot bases.
            If more than one robot is loaded provide a list of doubles, one for each robot.
            Specify None for an offset of (0, 0, 0) for each robot.

        env_configuration (str): Specifies how to position the robots within the environment (default is "default").
            For most single arm environments, this argument has no impact on the robot setup.

        controller_configs (str or list of dict): If set, contains relevant controller parameters for creating a
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

        object_placement_initializer (ObjectPositionSampler): if provided, will
            be used to place objects on every reset, else a UniformRandomSampler
            is used by default.
            Objects are elements that can and should be manipulated.

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

        randomize_initial_pos (bool): True - Use random initial joint position for robot.
                                      False - Do not override initial position.

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
        robots,
        robot_base_offset=None,
        env_configuration="default",
        controller_configs=None,
        gripper_types="default",
        initialization_noise="default",
        table_full_size=(1.5, 2.0, 0.05),
        table_friction=(1.0, 5e-3, 1e-4),
        use_camera_obs=True,
        use_object_obs=True,
        reward_scale=1.0,
        reward_shaping=False,
        goal_dist=0.1,
        collision_reward=-10,
        goal_reward=1,
        object_placement_initializer=None,
        obstacle_placement_initializer=None,
        has_renderer=False,
        has_offscreen_renderer=True,
        render_camera="frontview",
        render_collision_mesh=False,
        render_visual_mesh=True,
        render_gpu_device_id=-1,
        control_freq=10,
        horizon=1000,
        ignore_done=False,
        hard_reset=True,
        camera_names="frontview",
        camera_heights=256,
        camera_widths=256,
        camera_depths=False,
        camera_segmentations=None,  # {None, instance, class, element}
        renderer="mujoco",
        renderer_config=None,
        use_failsafe_controller=True,
        visualize_failsafe_controller=False,
        visualize_pinocchio=False,
        control_sample_time=0.004,
        human_animation_names=[
            "62_01",
            "62_03",
            "62_04",
            "62_07",
            "62_09",
            "62_10",
            "62_12",
            "62_13",
            "62_14",
            "62_15",
            "62_16",
            "62_18",
            "62_19",
        ],
        base_human_pos_offset=[0.0, 0.0, 0.0],
        human_animation_freq=120,
        human_rand=[0.0, 0.0, 0.0],
        safe_vel=0.001,
        randomize_initial_pos=False,
        self_collision_safety=0.01,
        seed=0,
        verbose=False,
        done_at_collision=False,
        done_at_success=False
    ):  # noqa: D107
        # settings for table top
        self.table_full_size = table_full_size
        self.table_friction = table_friction
        # settings for table top (hardcoded since it's not an essential part of the environment)
        self.table_offset = np.array((0.0, 0.0, 0.82))
        # reward configuration
        self.reward_scale = reward_scale
        self.reward_shaping = reward_shaping
        self.collision_reward = collision_reward
        self.goal_reward = goal_reward
        self.goal_dist = goal_dist
        self.desired_goal = np.array([0.0])
        # object placement initializer
        self.object_placement_initializer = object_placement_initializer
        self.obstacle_placement_initializer = obstacle_placement_initializer
        self.randomize_initial_pos = randomize_initial_pos
        # if run should stop at collision
        self.done_at_collision = done_at_collision
        self.done_at_success = done_at_success
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
        """Override base step function.

        Adds the goal position as an arrow to the visualizer.

        Args:
            action (np.array): Action to execute within the environment
        Returns:
            4-tuple:
                - (OrderedDict) observations from the environment
                - (float) reward from the environment
                - (bool) whether the current episode is completed or not
                - (dict) misc information
        Raises:
            ValueError: [Steps past episode termination]
        """
        obs, reward, done, info = super().step(action)
        if self.goal_reached:
            # if goal is reached, calculate a new goal.
            self.desired_goal = self._sample_valid_pos()
            if isinstance(self.robots[0].robot_model, PinocchioManipulatorModel):
                (self.goal_marker_trans, self.goal_marker_rot) = self.robots[
                    0
                ].robot_model.get_eef_transformation(self.desired_goal)
            self.goal_reached = False
        if self.has_renderer:
            self._visualize_goal()
        return obs, reward, done, info

    def reset(self):
        """
        Resets the environment.

        Returns:
            Observation
        """
        return super().reset()

    def _get_info(self) -> Dict:
        """Return the info dictionary of this step.

        Returns
            info dict containing of
                * collision: if there was a collision or not
                * collision_type: type of collision
                * timeout: if timeout was reached
                * failsafe_intervention: if the failsafe controller intervened
                    in this step or not
        """
        info = super()._get_info()
        # Add more info if wanted (do not forget to pass this to the tensorboard callback)
        # info["my_cool_info"] = 0
        return info

    def reward(
        self, achieved_goal: List[float], desired_goal: List[float], info: Dict
    ) -> float:
        """Compute the reward based on the achieved goal, the desired goal, and the info dict.

        If self.reward_shaping, we use a dense reward, otherwise a sparse reward.
        This function can only be called for one sample.

        Args:
            achieved_goal (List[float]): observation of robot state that is relevant for goal
            desired_goal (List[float]): the desired goal
            info (Dict): dictionary containing additional information like collision
        Returns:
            reward (float)
        """
        # sparse completion reward
        if self._check_success(achieved_goal, desired_goal):
            reward = self.goal_reward
        else:
            reward = -1.0
        # use a shaping reward
        if self.reward_shaping:
            reward += 1.0
            dist = np.sqrt(np.sum((achieved_goal - desired_goal)**2))
            reward -= dist * 0.1
        # Scale reward if requested
        if self.reward_scale is not None:
            reward *= self.reward_scale / 1.0
        if info["collision"]:
            reward += self.collision_reward
        return reward

    def _check_success(
        self, achieved_goal: List[float], desired_goal: List[float]
    ) -> bool:
        """Check if the desired goal was reached.

        Checks if all robot joints are at the desired position.
        The distance metric is a RMSE and the threshold is self.goal_dist.
        This function can only be called for one sample.

        Args:
            achieved_goal: observation of robot state that is relevant for goal
            desired_goal: the desired goal
        Returns:
            True if success
        """
        dist = np.sqrt(
            np.sum([(a - g) ** 2 for (a, g) in zip(achieved_goal, desired_goal)])
        )
        return dist <= self.goal_dist

    def _check_done(
        self, achieved_goal: List[float], desired_goal: List[float], info: Dict
    ) -> bool:
        """Compute the done flag based on the achieved goal, the desired goal, and the info dict.

        This function can only be called for one sample.

        Args:
            achieved_goal (List[float]): observation of robot state that is relevant for goal
            desired_goal (List[float]): the desired goal
            info (Dict): dictionary containing additional information like collision
        Returns:
            done (bool)
        """
        collision = info["collision"]
        if self.done_at_collision and collision:
            return True
        success = self._check_success(achieved_goal, desired_goal)
        if self.done_at_success and success:
            return True
        return False

    def _get_achieved_goal_from_obs(
        self, observation: Union[List[float], Dict]
    ) -> List[float]:
        """
        Extract the achieved goal from the observation.

        The achieved goal is the new joint angle position of all joints.

        Args:
            observation: The observation after the action is executed

        Returns:
            The achieved goal
        """
        prefix = self.robots[0].robot_model.naming_prefix
        return observation[prefix + "joint_pos"]

    def _get_desired_goal_from_obs(
        self, observation: Union[List[float], Dict]
    ) -> List[float]:
        """Extract the desired goal from the observation.

        The desired goal is a desired goal joint position.

        Args:
            observation: The observation after the action is executed

        Returns:
            The desired goal
        """
        return observation["desired_goal"]

    def _reset_internal(self):
        """Reset the simulation internal configurations."""
        # Set the desired new initial joint angles before resetting the robot.
        if self.randomize_initial_pos:
            if self.robots[0].controller is not None:
                self.robots[0].init_qpos = self._sample_valid_pos()
        super()._reset_internal()
        self.desired_goal = self._sample_valid_pos()
        if isinstance(self.robots[0].robot_model, PinocchioManipulatorModel):
            (self.goal_marker_trans, self.goal_marker_rot) = self.robots[
                0
            ].robot_model.get_eef_transformation(self.desired_goal)

    def _sample_valid_pos(self):
        """Randomly sample a new valid joint configuration
            without self-collisions or collisions with the static environment.

        Returns:
            joint configuration (np.array)
        """
        robot = self.robots[0]
        pos_limits = np.array(robot.controller.position_limits)
        goal = np.zeros(pos_limits.shape[1])
        for i in range(20):
            rand = np.random.rand(pos_limits.shape[1])
            goal = pos_limits[0] + (pos_limits[1] - pos_limits[0]) * rand
            if isinstance(robot.robot_model, PinocchioManipulatorModel):
                if not self._check_action_safety(robot.robot_model, goal):
                    goal = np.zeros(pos_limits.shape[1])
                    if self.visualize_pinocchio:
                        self.visualize_pin(self.pin_viz)
                else:
                    break
            else:
                break

        return goal

    def _setup_arena(self):
        """Set up the mujoco arena.

        Must define self.mujoco_arena.
        Define self.objects and self.obstacles here.
        """
        # load model for table top workspace
        self.mujoco_arena = TableArena(
            table_full_size=self.table_full_size,
            table_offset=self.table_offset,
            xml=xml_path_completion("arenas/table_arena.xml")
        )

        # Arena always gets set to zero origin
        self._set_origin()

        # Modify default agentview camera
        self._set_mujoco_camera()

        # << OBJECTS >>
        # Objects are elements that can be moved around and manipulated.
        # Create objects
        # Box example
        box_size = np.array([0.05, 0.05, 0.05])
        box = BoxObject(
            name="smallBox",
            size=box_size * 0.5,
            rgba=[0.1, 0.7, 0.3, 1],
        )
        self.objects = [box]
        # Placement sampler for objects
        bin_x_half = self.table_full_size[0] / 2 - 0.05
        bin_y_half = self.table_full_size[1] / 2 - 0.05
        self.object_placement_initializer = self._setup_placement_initializer(
            name="ObjectSampler",
            initializer=self.object_placement_initializer,
            objects=self.objects,
            x_range=[-bin_x_half, bin_x_half],
            y_range=[-bin_y_half, bin_y_half],
        )
        # << OBSTACLES >>
        self._setup_collision_objects(
            add_table=True,
            add_base=True,
            safety_margin=0.01
        )
        # Obstacles are elements that the robot should avoid.
        self.obstacles = []
        self.obstacle_placement_initializer = self._setup_placement_initializer(
            name="ObstacleSampler",
            initializer=self.obstacle_placement_initializer,
            objects=self.obstacles,
        )

    def _setup_references(self):
        """Set up references to important components."""
        super()._setup_references()

    def _setup_observables(self):
        """Set up observables to be used for this environment.

        Creates object-based observables if enabled.

        Returns:
            OrderedDict: Dictionary mapping observable names to its corresponding Observable object
        """
        observables = super()._setup_observables()
        # robot joint pos
        prefix = self.robots[0].robot_model.naming_prefix
        if prefix + "joint_pos" in observables:
            observables[prefix + "joint_pos"].set_active(True)
        if prefix + "joint_vel" in observables:
            observables[prefix + "joint_vel"].set_active(True)
        if prefix + "eef_pos" in observables:
            observables[prefix + "eef_pos"].set_active(True)
        if "human_joint_pos" in observables:
            observables["human_joint_pos"].set_active(True)
        if prefix + "joint_pos_cos" in observables:
            observables[prefix + "joint_pos_cos"].set_active(False)
        if prefix + "joint_pos_sin" in observables:
            observables[prefix + "joint_pos_sin"].set_active(False)
        if prefix + "gripper_qpos" in observables:
            observables[prefix + "gripper_qpos"].set_active(False)
        if prefix + "gripper_qvel" in observables:
            observables[prefix + "gripper_qvel"].set_active(False)
        if prefix + "eef_quat" in observables:
            observables[prefix + "eef_quat"].set_active(False)
        if "gripper_pos" in observables:
            observables["gripper_pos"].set_active(False)

        # low-level object information
        modality = "goal"

        @sensor(modality=modality)
        def desired_goal(obs_cache):
            return self.desired_goal

        @sensor(modality=modality)
        def goal_difference(obs_cache):
            return self.desired_goal - np.array([self.sim.data.qpos[x] for x in self.robots[0]._ref_joint_pos_indexes])

        sensors = [desired_goal]
        if len(self.robots[0]._ref_joint_pos_indexes) == self.desired_goal.shape[0]:
            sensors.append(goal_difference)

        names = [s.__name__ for s in sensors]

        # Create observables
        for name, s in zip(names, sensors):
            observables[name] = Observable(
                name=name,
                sensor=s,
                sampling_rate=self.control_freq,
            )
        return observables

    def _visualize_goal(self):
        """Visualize the goal state."""
        # arrow (type 100)
        self.viewer.viewer.add_marker(
            pos=self.goal_marker_trans,
            type=100,
            size=[0.01, 0.01, 0.2],
            mat=self.goal_marker_rot,
            rgba=[0.0, 1.0, 0.0, 0.7],
            label="",
            shininess=0.0,
        )
