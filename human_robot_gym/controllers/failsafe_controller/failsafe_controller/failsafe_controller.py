"""This file describes the failsafe controller.

The failsafe controller allows safe operation of a robot in the vacinity of humans.

Owner:
    Jakob Thumm (JT)

Contributors:

Changelog:
    2.5.22 JT Formatted docstrings
"""

import numpy as np
import os
from scipy.spatial.transform import Rotation

# from matplotlib import pyplot as plt

from robosuite.controllers.joint_pos import JointPositionController
from robosuite.utils.control_utils import set_goal_position

from safety_shield_py import SafetyShield, ShieldType  # noqa: F401

from .plot_capsule import PlotCapsule


class FailsafeController(JointPositionController):
    """Controller for safely controlling robot arm in the vacinity of humans.

    NOTE: Control input actions assumed to be taken relative to the current joint positions. A given action to this
    controller is assumed to be of the form: (dpos_j0, dpos_j1, ... , dpos_jn-1) for an n-joint robot

    Args:
        sim (MjSim): Simulator instance this controller will pull robot state updates from

        eef_name (str): Name of controlled robot arm's end effector (from robot XML)

        joint_indexes (dict): Each key contains sim reference indexes to relevant robot joint information, namely:

            :`'joints'`: list of indexes to relevant robot joints
            :`'qpos'`: list of indexes to relevant robot joint positions
            :`'qvel'`: list of indexes to relevant robot joint velocities

        actuator_range (2-tuple of array of float): 2-Tuple (low, high) representing the robot joint actuator range

        init_qpos (list[double]): Initial joint angles

        base_pos (list[double]): position of base [x, y, z]

        base_orientation (list[double]): orientation of base as quaternion [x, y, z, w]

        shield_type (str): Shield type to use. Valid options are: "OFF", "SSM", and "PFL"

        input_max (float or Iterable of float): Maximum above which an inputted action will be clipped. Can be either be
            a scalar (same value for all action dimensions), or a list (specific values for each dimension). If the
            latter, dimension should be the same as the control dimension for this controller

        input_min (float or Iterable of float): Minimum below which an inputted action will be clipped. Can be either be
            a scalar (same value for all action dimensions), or a list (specific values for each dimension). If the
            latter, dimension should be the same as the control dimension for this controller

        output_max (float or Iterable of float): Maximum which defines upper end of scaling range when scaling an input
            action. Can be either be a scalar (same value for all action dimensions), or a list (specific values for
            each dimension). If the latter, dimension should be the same as the control dimension for this controller

        output_min (float or Iterable of float): Minimum which defines upper end of scaling range when scaling an input
            action. Can be either be a scalar (same value for all action dimensions), or a list (specific values for
            each dimension). If the latter, dimension should be the same as the control dimension for this controller

        kp (float or Iterable of float): positional gain for determining desired torques based upon the joint pos error.
            Can be either be a scalar (same value for all action dims), or a list (specific values for each dim)

        damping_ratio (float or Iterable of float): used in conjunction with kp to determine the velocity gain for
            determining desired torques based upon the joint pos errors. Can be either be a scalar (same value for all
            action dims), or a list (specific values for each dim)

        impedance_mode (str): Impedance mode with which to run this controller. Options are {"fixed", "variable",
            "variable_kp"}. If "fixed", the controller will have fixed kp and damping_ratio values as specified by the
            @kp and @damping_ratio arguments. If "variable", both kp and damping_ratio will now be part of the
            controller action space, resulting in a total action space of num_joints * 3. If "variable_kp", only kp
            will become variable, with damping_ratio fixed at 1 (critically damped). The resulting action space will
            then be num_joints * 2.

        kp_limits (2-list of float or 2-list of Iterable of floats): Only applicable if @impedance_mode is set to either
            "variable" or "variable_kp". This sets the corresponding min / max ranges of the controller action space
            for the varying kp values. Can be either be a 2-list (same min / max for all kp action dims), or a 2-list
            of list (specific min / max for each kp dim)

        damping_ratio_limits (2-list of float or 2-list of Iterable of floats): Only applicable if @impedance_mode is
            set to "variable". This sets the corresponding min / max ranges of the controller action space for the
            varying damping_ratio values. Can be either be a 2-list (same min / max for all damping_ratio action dims),
            or a 2-list of list (specific min / max for each damping_ratio dim)

        policy_freq (int): Frequency at which actions from the robot policy are fed into this controller

        control_sample_time (double): time in between two low-level controller steps

        qpos_limits (2-list of float or 2-list of Iterable of floats): Limits (rad) below and above which the magnitude
            of a calculated goal joint position will be clipped. Can be either be a 2-list (same min/max value for all
            joint dims), or a 2-list of list (specific min/max values for each dim)

        interpolator (Interpolator): Interpolator object to be used for interpolating from the current joint position to
            the goal joint position during each timestep between inputted actions

        **kwargs: Does nothing; placeholder to "sink" any additional arguments so that instantiating this controller
            via an argument dict that has additional extraneous arguments won't raise an error

    Raises:
        AssertionError: [Invalid impedance mode]
    """

    def __init__(
        self,
        sim,
        eef_name,
        joint_indexes,
        actuator_range,
        init_qpos,
        robot_name,
        base_pos=[0.0, 0.0, 0.0],
        base_orientation=[0.0, 0.0, 0.0, 1.0],
        shield_type="SSM",
        input_max=1,
        input_min=-1,
        output_max=0.05,
        output_min=-0.05,
        kp=50,
        damping_ratio=1,
        impedance_mode="fixed",
        kp_limits=(0, 300),
        damping_ratio_limits=(0, 100),
        policy_freq=20,
        control_sample_time=0.004,
        qpos_limits=None,
        interpolator=None,
        **kwargs,  # does nothing; used so no error raised when dict is passed with extra terms used previously
    ):
        # noqa: D107
        super().__init__(
            sim,
            eef_name,
            joint_indexes,
            actuator_range,
            input_max,
            input_min,
            output_max,
            output_min,
            kp,
            damping_ratio,
            impedance_mode,
            kp_limits,
            damping_ratio_limits,
            policy_freq,
            qpos_limits,
            interpolator,
        )

        # Control dimension
        dir_path = os.path.dirname(os.path.realpath(__file__))
        rot = Rotation.from_quat(
            [
                base_orientation[0],
                base_orientation[1],
                base_orientation[2],
                base_orientation[3],
            ]
        )
        rpy = rot.as_euler("XYZ")

        robot_name = robot_name.lower()
        # Unfortunately, all other native python enum functions seem to fail.
        self.shield_type = eval("ShieldType." + shield_type)

        self.safety_shield = SafetyShield(
            sample_time=control_sample_time,
            trajectory_config_file=(
                f"{dir_path}/../sara-shield/safety_shield/config/trajectory_parameters_{robot_name}.yaml"
            ),
            robot_config_file=f"{dir_path}/../sara-shield/safety_shield/config/robot_parameters_{robot_name}.yaml",
            mocap_config_file=dir_path + "/../sara-shield/safety_shield/config/mujoco_mocap.yaml",
            init_x=base_pos[0],
            init_y=base_pos[1],
            init_z=base_pos[2],
            init_roll=rpy[0],
            init_pitch=rpy[1],
            init_yaw=rpy[2],
            init_qpos=init_qpos,
            shield_type=self.shield_type
        )
        self.desired_motion = self.safety_shield.step(0.0)
        self.robot_capsules = []
        self.human_capsules = []
        # Place holder for dynamic variables
        self.command_vel = [0.0 for i in init_qpos]
        self.robot_cap_in = []
        self.human_cap_in = []
        # Debug path following

        # self.desired_pos_dbg = np.zeros([1000, 6])
        # self.joint_pos_dbg = np.zeros([1000, 6])
        # self.dbg_c = 0

    def reset(self,
              base_pos=[0.0, 0.0, 0.0],
              base_orientation=[0.0, 0.0, 0.0, 1.0],
              shield_type="SSM",):
        """Reset the failsafe controller.

        Args:
            base_pos (list[double]): position of base [x, y, z]
            base_orientation (list[double]): orientation of base as quaternion [x, y, z, w]
            shield_type (str): Shield type to use. Valid options are: "OFF", "SSM", and "PFL"
        """
        self.goal_qpos = None
        # Torques being outputted by the controller
        self.torques = None
        # Update flag to prevent redundant update calls
        self.new_update = True
        # Move forward one timestep to propagate updates before taking first update
        self.sim.forward()
        # Initialize controller by updating internal state and setting the initial joint, pos, and ori
        self.update()
        self.joint_pos = np.array(self.sim.data.qpos[self.qpos_index])
        self.initial_joint = self.joint_pos
        self.initial_ee_pos = self.ee_pos
        self.initial_ee_ori_mat = self.ee_ori_mat
        # Control dimension
        rot = Rotation.from_quat(
            [
                base_orientation[0],
                base_orientation[1],
                base_orientation[2],
                base_orientation[3],
            ]
        )
        rpy = rot.as_euler("XYZ")
        # Unfortunately, all other native python enum functions seem to fail.
        self.shield_type = eval("ShieldType." + shield_type)
        self.safety_shield.reset(
            init_x=base_pos[0],
            init_y=base_pos[1],
            init_z=base_pos[2],
            init_roll=rpy[0],
            init_pitch=rpy[1],
            init_yaw=rpy[2],
            init_qpos=self.joint_pos,
            current_time=self.sim.data.time,
            shield_type=self.shield_type,
        )

    def set_goal(self, action, set_qpos=None):
        """Set goal based on input action.

        If self.impedance_mode is not "fixed", then the input will be parsed into the
        delta values to update the goal position / pose and the kp and/or damping_ratio values to be immediately updated
        internally before executing the proceeding control loop.

        Note that @action expected to be in the following format, based on impedance mode!
            :Mode `'fixed'`: [joint pos command]
            :Mode `'variable'`: [damping_ratio values, kp values, joint pos command]
            :Mode `'variable_kp'`: [kp values, joint pos command]

        Args:
            action (Iterable): Desired relative joint position goal state
            set_qpos (Iterable): If set, overrides @action and sets the desired absolute joint position goal state

        Raises:
            AssertionError: [Invalid action dimension size]
        """
        # Update state
        self.update()

        # Parse action based on the impedance mode, and update kp / kd as necessary
        jnt_dim = len(self.qpos_index)

        delta = action

        # Check to make sure delta is size self.joint_dim
        assert (
            len(delta) == jnt_dim
        ), "Delta qpos must be equal to the robot's joint dimension space!"

        if delta is not None:
            scaled_delta = self.scale_action(delta)
        else:
            scaled_delta = None

        self.goal_qpos = set_goal_position(
            scaled_delta,
            self.joint_pos,  # self.desired_motion.getAngle(),
            position_limit=self.position_limits,
            set_pos=set_qpos,
        )

        if self.interpolator is not None:
            raise NotImplementedError
            # self.interpolator.set_goal(self.goal_qpos)

        self.safety_shield.newLongTermTrajectory(self.goal_qpos, self.command_vel)

    def set_human_measurement(self, human_measurement, time):
        """Set the human measurement of the safety shield.

        Args:
            human_measurement (list[list[double]]): List of human measurements [x, y, z]-joint positions.
                The order of joints is defined in the motion capture config file.
            time (double): Time of the human measurement
        """
        self.safety_shield.humanMeasurement(human_measurement, time)

    def run_controller(self):
        """Calculate the torques required to reach the desired setpoint.

        Returns:
             np.array: Command torques
        """
        # Make sure goal has been set
        if self.goal_qpos is None:
            self.set_goal(np.zeros(self.control_dim))

        # Update state
        # self.update() <- takes forever
        # self.sim.forward()
        self.joint_pos = np.array(self.sim.data.qpos[self.qpos_index])
        self.joint_vel = np.array(self.sim.data.qvel[self.qvel_index])

        current_time = self.sim.data.time
        self.desired_motion = self.safety_shield.step(current_time)
        desired_qpos = self.desired_motion.getAngle()
        desired_qvel = self.desired_motion.getVelocity()
        desided_qacc = self.desired_motion.getAcceleration()
        # Debug path following -> How well is the robot following the desired trajectory.
        # You can use this to tune your PID values

        # self.desired_pos_dbg[self.dbg_c] = desired_qpos
        # self.joint_pos_dbg[self.dbg_c] = self.joint_pos
        # self.dbg_c+=1

        # if self.dbg_c == 1000:
        #     fig, axs = plt.subplots(self.control_dim)
        #     for joint in range(self.control_dim):
        #         ax = axs[joint]
        #         ax.plot(np.arange(0, self.dbg_c), self.desired_pos_dbg[0:self.dbg_c, joint], label='desired pos')
        #         ax.plot(np.arange(0, self.dbg_c), self.joint_pos_dbg[0:self.dbg_c, joint], label='joint pos')
        #         # ax.set_xlabel("Step")
        #         # ax.set_ylabel("Angle [rad]")
        #         # ax.set_title(f"Joint {joint+1}")
        #         ax.grid()
        #     ax.legend()
        #     fig.suptitle("Joint Angles, PD+ Controller with Grav. Comp.")
        #     plt.show()
        #     self.dbg_c=0

        # torques = pos_err * kp + vel_err * kd
        position_error = desired_qpos - self.joint_pos
        vel_pos_error = desired_qvel - self.joint_vel
        feedback_torque = np.multiply(
            np.array(position_error), np.array(self.kp)
        ) + np.multiply(vel_pos_error, self.kd)

        # Return desired torques plus gravity compensations
        # Similar to PD+ control, without squared velocity term
        self.torques = (
            np.dot(self.mass_matrix, feedback_torque + desided_qacc)
            + self.torque_compensation
        )

        self.torques = self.clip_torques(torques=self.torques)
        # Always run superclass call for any cleanups at the end
        self.new_update = True

        return self.torques

    def get_safety(self):
        """Return if the failsafe controller intervened in this step or not.

        Returns:
          bool: True: Safe, False: Unsafe
        """
        return self.safety_shield.getSafety()

    def get_robot_capsules(self):
        """Return the robot capsules in the correct format to plot them in mujoco.

        capsule:  pos = [x, y, z]
                  size = [radius, radius, length]
                  mat = 3x3 rotation matrix

        Returns:
            list[capsule]
        """
        self.robot_cap_in = self.safety_shield.getRobotReachCapsules()
        if len(self.robot_capsules) == 0:
            for cap in self.robot_cap_in:
                self.robot_capsules.append(PlotCapsule(cap[0:3], cap[3:6], cap[6]))
        else:
            assert len(self.robot_capsules) == len(self.robot_cap_in)
            for i in range(len(self.robot_cap_in)):
                self.robot_capsules[i].update_pos(
                    self.robot_cap_in[i][0:3], self.robot_cap_in[i][3:6], self.robot_cap_in[i][6]
                )

        return self.robot_capsules

    def get_human_capsules(self):
        """Return the human capsules in the correct format to plot them in mujoco.

        capsule:  pos = [x, y, z]
                  size = [radius, radius, length]
                  mat = 3x3 rotation matrix

        Returns:
            list[capsule]
        """
        self.human_cap_in = self.safety_shield.getHumanReachCapsules()
        if len(self.human_capsules) == 0:
            for cap in self.human_cap_in:
                self.human_capsules.append(PlotCapsule(cap[0:3], cap[3:6], cap[6]))
        else:
            assert len(self.human_capsules) == len(self.human_cap_in)
            for i in range(len(self.human_cap_in)):
                self.human_capsules[i].update_pos(
                    self.human_cap_in[i][0:3], self.human_cap_in[i][3:6], self.human_cap_in[i][6]
                )

        return self.human_capsules
