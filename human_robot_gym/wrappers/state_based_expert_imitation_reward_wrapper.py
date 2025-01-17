"""This file implements wrappers to add reward for similarity between the states reached during an episode
by the agent and an expert.

State-based expert imitation reward wrappers load demonstration episodes using the expert policy from disk
and then compare the states reached by the agent to those obtained at the same time step in the demonstration
to determine an imitation reward.

Datasets can be generated by executing

```
python human_robot_gym/training/create_expert_dataset.py -cn my_data_collection_config
```

with a suitable config file.

This method uses similar concepts as the imitation reward approach proposed in DeepMimic (Peng et al., 2018).
Link to paper: https://arxiv.org/abs/1804.02717

Author:
    Felix Trost (FT)

Changelog:
    23.03.23 FT File creation
"""
from typing import Any, Dict, List, Tuple, Union

import numpy as np
from gym.core import Env
from gym.spaces import Box

from human_robot_gym.demonstrations.experts import ReachHumanExpert
from human_robot_gym.demonstrations.experts import PickPlaceHumanCartExpert
from human_robot_gym.demonstrations.experts import CollaborativeLiftingCartExpert
from human_robot_gym.wrappers.expert_obs_wrapper import ExpertObsWrapper
from human_robot_gym.wrappers.dataset_wrapper import DatasetRSIWrapper
from human_robot_gym.utils.expert_imitation_reward_utils import similarity_fn


class StateBasedExpertImitationRewardWrapper(DatasetRSIWrapper):
    r"""Wrapper for adding imitation reward based on the similarity between the states reached during an episode.

    Builds on the dataset reference state initialization (RSI) wrapper:
        environments are initialized from dataset states.

    By default, these are the initial states of the dataset, but states later in the episode may also be sampled
    by changing the `rsi_prob` parameter.

    The imitation reward is given by this formula:
    $r = r_i * \alpha + r_{env} * (1 - \alpha)$

    Where:
        $r_{env}$: reward from wrapped environment.
        $r_i$: reward obtained from the similarity to the corresponding state in the expert demonstration episode.
            Depends on the specific environment, therefore implemented in subclasses.

    Args:
        env (Env): gym environment to wrap
        dataset_name (str): name of the dataset to load demonstration episodes from
        alpha (float): linear interpolation factor between
            just environment reward (`alpha = 0`) and
            just imitation reward (`alpha = 1`)
        observe_time (bool): whether to add a time parameter to the observation space
            normalized to the range [0, 1], where
                0: start of episode (after reset and one zero action)
                1: end of demonstration episode
            defaults to `True`
        rsi_prob (float): probability of using reference state initialization (RSI)
            to initialize the environment at each reset
        use_et (bool): whether to use early termination (ET) to terminate the episode early if the agent state
            diverges too far from the expert state.
            The criteria for ET are defined in subclasses.
        verbose (bool): whether to print debug information
    """
    def __init__(
        self,
        env: Env,
        dataset_name: str,
        alpha: float,
        observe_time: bool = True,
        rsi_prob: float = 0.0,
        use_et: bool = False,
        verbose: bool = False,
    ):
        super().__init__(
            env=env,
            dataset_name=dataset_name,
            rsi_prob=rsi_prob
        )

        self._alpha = alpha
        self._observe_time = observe_time
        self._use_et = use_et
        self._verbose = verbose

        if observe_time:
            self.observation_space = self._add_time_to_observation_space(self.observation_space)

        self._imitation_rewards = None
        self._environment_rewards = None

    def reset(self) -> np.ndarray:
        """Extend super `reset` method by adding the time parameter to the observation space if requested"""
        obs = super().reset()

        # Add time parameter to observation space
        if self._observe_time:
            obs = np.concatenate([obs, [self._dataset_ep_step_idx / self._dataset_transition_count]])

        # Bookkeeping for logging
        self._imitation_rewards = []
        self._environment_rewards = []

        return obs

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """Extend super `step` method by computing the imitation reward and combining it with the environment reward.

        Args:
            action (np.ndarray): action chosen by agent to take in environment

        Returns:
            4-tuple:
                -(np.ndarray): new observation
                -(float): combined reward
                -(bool): whether the current episode is completed
                -(dict): misc information

        Raises:
            NotImplementedError [get_imitation_reward method not implemented in StateBasedExpertImitationRewardWrapper]
            AssertionError [Expert observation not stored in info dict]
        """
        observation, env_reward, done, info = super().step(action)

        # Obtain the expert observations for comparison
        demonstration_obs_dict = self._dic["expert_observations"][self._dataset_ep_step_idx]
        policy_obs_dict = ExpertObsWrapper.get_current_expert_observation_from_info(info)

        imitation_reward = self._get_imitation_reward(
            demonstration_obs_dict=demonstration_obs_dict,
            policy_obs_dict=policy_obs_dict,
        )

        # Handle early termination
        if self._use_et:
            should_terminate_early = self._should_terminate_early(
                demonstration_obs_dict=demonstration_obs_dict,
                policy_obs_dict=policy_obs_dict,
            )

            done = done or should_terminate_early

            info["early_termination"] = int(should_terminate_early)

            if self._verbose and should_terminate_early:
                print("Early termination!")

        # Add time parameter to observation space
        if self._observe_time:
            observation = np.concatenate([observation, [self._dataset_ep_step_idx / self._dataset_transition_count]])

        # Bookkeeping for logging
        self._imitation_rewards.append(imitation_reward)
        self._environment_rewards.append(env_reward)

        reward = self._combine_reward(env_reward, imitation_reward)

        # Log the imitation and env rewards
        if done:
            if self._verbose:
                print(f"Expert ep len: {self._dataset_transition_count}, agent: {self._dataset_ep_step_idx + 1}")

            self._add_reward_to_info(info)

        return observation, reward, done, info

    def _add_reward_to_info(self, info: Dict[str, Any]):
        """Add the following data to the info dict:
            - `ep_im_rew_mean`: sum of imitation rewards in episode
            - `ep_env_rew_mean`: sum of environment rewards in episode
            - `ep_full_rew_mean`: sum of combined imitation and environment rewards in episode
            - `im_rew_mean`: mean of imitation rewards in episode
            - `env_rew_mean`: mean of environment rewards in episode
            - `full_rew_mean`: mean of combined imitation and environment rewards in episode

        Args:
            info (Dict[str, Any]): info dict to add data to
        """
        info["ep_im_rew_mean"] = sum(self._imitation_rewards)
        info["ep_env_rew_mean"] = sum(self._environment_rewards)
        info["ep_full_rew_mean"] = self._combine_reward(
            env_reward=info["ep_env_rew_mean"],
            imitation_reward=info["ep_im_rew_mean"],
        )

        info["im_rew_mean"] = np.nan if len(self._imitation_rewards) == 0 else np.mean(self._imitation_rewards)
        info["env_rew_mean"] = np.nan if len(self._environment_rewards) == 0 else np.mean(self._environment_rewards)
        info["full_rew_mean"] = self._combine_reward(
            env_reward=info["env_rew_mean"],
            imitation_reward=info["im_rew_mean"],
        )

    def _add_time_to_observation_space(self, observation_space: Box) -> Box:
        """Adds a parameter to the observation space, bound to [0, 1]
        to represent the time elapsed since the last reset.
        """
        low = np.concatenate([observation_space.low, [0]])
        high = np.concatenate([observation_space.high, [1]])
        return Box(low, high)

    def _combine_reward(
        self,
        env_reward: Union[float, List[float]],
        imitation_reward: Union[float, List[float]],
    ) -> float:
        """Combine the environment and imitation reward values by linear interpolation.
        Values either given as single values or as two lists of values.

        Args:
            env_reward (float | List[float]): reward given from wrapped env
            imitation_reward (float | List[float]): reward obtained from imitating the expert

        Returns:
            float: combined reward

        Raises:
            ValueError ["Either both or none of env and imitation are expected to be lists"]
        """
        if isinstance(env_reward, List) and isinstance(imitation_reward, List):
            return [r_im * self._alpha + r_env * (1 - self._alpha) for r_im, r_env in zip(imitation_reward, env_reward)]
        elif isinstance(env_reward, List) or isinstance(imitation_reward, List):
            raise ValueError("Either both or none of env and imitation are expected to be lists")
        else:
            return imitation_reward * self._alpha + env_reward * (1 - self._alpha)

    def _get_imitation_reward(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ) -> float:
        """Extract the imitation reward from the similarity between agent and expert states,
        represented by expert observation dicts.
        Depends on the specific environment, therefore implemented in subclasses.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            float: imitation reward

        Raises:
            NotImplementedError [get_imitation_reward method not implemented in StateBasedExpertImitationRewardWrapper]
        """
        raise NotImplementedError(
            "get_imitation_reward method not implemented in StateBasedExpertImitationRewardWrapper"
        )

    def _should_terminate_early(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ) -> bool:
        """Decide whether the training episode should be terminated early,
        based on the similarity between the current state reached by the agent
        and the corresponding state in the demonstration episode.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            bool: whether the training episode should be terminated early
        """
        raise NotImplementedError(
            "should_terminate_early method not implemented in StateBasedExpertImitationRewardWrapper"
        )


class ReachHumanStateBasedExpertImitationRewardWrapper(StateBasedExpertImitationRewardWrapper):
    r"""State-based expert imitation reward gym wrapper for the `ReachHuman` environment.

    Also applicable for the `ReachHumanCart` environment as the expert observation is identical.

    The expert observation dicts should contain all keys necessary
    to be stored as `ReachHumanExpertObservation` objects.

    Adds the possibility of using reference state initialization (RSI)
    to initialize the environment at a random state from the demonstration episode.

    If early termination (ET) is enabled, the episode is terminated early if the difference between expert
    and agent states beomes too large.

    The reward is given by this formula:
        $r = r_i * \alpha + r_{env} * (1 - \alpha)$

    Where:
        $r_{env}$: reward from wrapped environment
        $r_i = sim(||obsdiff||, \iota_m)$

        $obsdiff$: difference between demonstration and training state end effector position
        $sim$: similarity function, either $sim_G$ or $sim_T$.
            For more details, see `human_robot_gym.utils.expert_imitation_reward_utils`

    Args:
        env (Env): gym environment to wrap
        dataset_name (str): name of the expert dataset
        alpha (float): weight of imitation reward in combined reward:
            alpha = 0: only environment reward
            alpha = 1: only imitation reward
        iota (float): tolerance parameter for imitation reward:
            if the distance between demonstration and training state end effector position is smaller than `iota`,
            r_i is greater than 0.5 (1 at maximum, i.e. perfect imitation)
        sim_fn (str): similarity function to use for imitation reward. Can be either `"gaussian"` or `"tanh"`.
        observe_time (bool): whether to add a time parameter to the observation space
            normalized to the range [0, 1], where
            0: start of episode (after reset and one zero action)
            1: end of demonstration episode
            This value is clipped to one: if the training pass lasts longer than the demonstration pass,
            the time parameter is set to 1 for the rest of the episode.
            Thus, this value reflects the progress in the demonstration episode used for comparison.
        rsi_prob (float): probability of using reference state initialization (RSI)
            to initialize the environment at each reset
        use_et (bool): whether to use early termination (ET) to terminate the episode early.
            The criteria for ET are defined in subclasses.
        et_dist (float): distance threshold for early termination. Episode terminated early if `use_et` is `True`
            and the distance between the end effector positions from the expert state and the agent state
            is larger than `et_dist * iota`
        verbose (bool): whether to print debug information
    """
    def __init__(
        self,
        env: Env,
        dataset_name: str,
        alpha: float = 0,
        iota: float = 0.1,
        sim_fn: str = "gaussian",
        observe_time: bool = True,
        rsi_prob: float = 0.0,
        use_et: bool = False,
        et_dist: float = 2,
        verbose: bool = False,
    ):
        super().__init__(
            env=env,
            dataset_name=dataset_name,
            alpha=alpha,
            observe_time=observe_time,
            rsi_prob=rsi_prob,
            use_et=use_et,
            verbose=verbose,
        )

        self._iota = iota
        self._sim_fn = sim_fn
        self._et_dist = et_dist

    def _get_imitation_reward(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ) -> float:
        """Determine the imitation reward by comparing the agent and expert states.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            float: imitation reward
        """
        demonstration_obs = ReachHumanExpert.expert_observation_from_dict(demonstration_obs_dict)
        policy_obs = ReachHumanExpert.expert_observation_from_dict(policy_obs_dict)

        imitation_error = demonstration_obs.goal_difference - policy_obs.goal_difference
        imitation_reward = similarity_fn(
            name=self._sim_fn,
            delta=np.linalg.norm(imitation_error),
            iota=self._iota,
        )

        return imitation_reward

    def _should_terminate_early(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ) -> bool:
        """Decide whether the training episode should be terminated early based on the similarity
        between the current state reached by the agent.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            bool: whether the training episode should be terminated early
        """
        demonstration_obs = ReachHumanExpert.expert_observation_from_dict(demonstration_obs_dict)
        policy_obs = ReachHumanExpert.expert_observation_from_dict(policy_obs_dict)

        imitation_error_dist = np.linalg.norm(
            demonstration_obs.goal_difference - policy_obs.goal_difference
        )

        return imitation_error_dist > self._et_dist * self._iota


class PickPlaceHumanCartStateBasedExpertImitationRewardWrapper(StateBasedExpertImitationRewardWrapper):
    r"""State-based expert imitation reward gym wrapper for the `PickPlaceHumanCart` environment.

    Can be used with any environment that can be solved using the `PickPlaceHumanCartExpert` expert policy.

    The expert observation dicts should contain all keys necessary
    to be stored as `PickPlaceHumanCartExpertObservation` objects.

    Adds the possibility of using reference state initialization (RSI)
    to initialize the environment at a random state from the demonstration episode.

    The reward is given by this formula:
        $r = r_i * \alpha + r_{env} * (1 - \alpha)$

    Where:
        $r_{env}$: reward from wrapped environment
        $r_i$:
            if the expert has gripped the object but not the agent: $0$
            otherwise:
                $r_{motion} * \beta + r_{gripper} * (1 - \beta)$

        $r_{motion} = sim_{motion}(||motiondiff||, \iota_m)$
        $r_{gripper} = sim_{motion}(|gripperdiff|, \iota_g)$

        $motiondiff$: difference in end effector position between demonstration state and training state
        $gripperdiff$: difference in gripper joint position (joint angles of both fingers added together)
            between demonstration state and training state
        $sim_{motion}$ and $sim_{gripper}: similarity functions, either $sim_G$ or $sim_T$
            For more details, see `human_robot_gym.utils.expert_imitation_reward_utils`

    Args:
        env (Env): gym environment to wrap
        dataset_name (str): name of the expert dataset
        alpha (float): weight of imitation reward in combined reward:
            alpha = 0: only environment reward
            alpha = 1: only imitation reward
        beta (float): weight of motion reward in imitation reward:
            beta = 0: only gripper reward
            beta = 1: only motion reward
        iota_m (float): tolerance parameter for motion reward:
            if the distance between demonstration and training state end effector position is smaller than iota_m,
            r_{motion} is greater than 0.5 (1 at maximum, i.e. perfect imitation)
        iota_g (float): tolerance parameter for gripper reward:
            if the distance between demonstration and training state gripper joint position is smaller than iota_g,
            r_{gripper} is greater than 0.5 (1 at maximum, i.e. perfect imitation)
        m_sim_fn: similarity function to use for motion imitation reward. Can be either `"gaussian"` or `"tanh"`.
        g_sim_fn: similarity function to use for gripper imitation reward. Can be either `"gaussian"` or `"tanh"`.
        observe_time (bool): whether to add a time parameter to the observation space
            normalized to the range [0, 1], where
            0: start of episode (after reset and one zero action)
            1: end of demonstration episode
            This value is clipped to one: if the training pass lasts longer than the demonstration pass,
            the time parameter is set to 1 for the rest of the episode.
            Thus, this value reflects the progress in the demonstration episode used for comparison.
        seed_increment (int): increment to the seed of the environment at each reset
        rsi_prob (float): probability of using reference state initialization (RSI)
            to initialize the environment at each reset
        use_et (bool): whether to use early termination (ET) to terminate the episode early.
            The criteria for ET are defined in subclasses.
        et_dist (float): distance threshold for early termination.
            Episode terminated early if:
                -@use_et is True
                -the distance between the end effector positions from the expert state and the agent state
                    is larger than @et_dist * @iota_m
                -the expert has gripped the object but not the agent
        verbose (bool): whether to print debug information

    Raises:
        AssertionError: [Environment and expert have different action space shapes]
    """
    def __init__(
        self,
        env: Env,
        dataset_name: str,
        alpha: float = 0,
        beta: float = 0,
        iota_m: float = 0.1,
        iota_g: float = 0.05,
        m_sim_fn: str = "gaussian",
        g_sim_fn: str = "gaussian",
        observe_time: bool = True,
        rsi_prob: float = 0.0,
        use_et: bool = False,
        et_dist: float = 2,
        verbose: bool = False,
    ):
        super().__init__(
            env=env,
            dataset_name=dataset_name,
            alpha=alpha,
            observe_time=observe_time,
            rsi_prob=rsi_prob,
            use_et=use_et,
            verbose=verbose,
        )

        self._beta = beta
        self._iota_m = iota_m
        self._iota_g = iota_g
        self._m_sim_fn = m_sim_fn
        self._g_sim_fn = g_sim_fn
        self._et_dist = et_dist

        self._motion_imitation_rewards = None
        self._gripper_imitation_rewards = None

    def reset(self) -> np.ndarray:
        """Extend super `reset` method to reset imitation reward logging bookkeeping."""
        self._motion_imitation_rewards = []
        self._gripper_imitation_rewards = []

        return super().reset()

    def _add_reward_to_info(self, info: dict):
        """Extend super method to add imitation reward data of motion and gripper imitation rewards to info dict."""
        super()._add_reward_to_info(info)

        ep_m_im_rew = sum(self._motion_imitation_rewards)
        ep_g_im_rew = sum(self._gripper_imitation_rewards)
        ep_len = len(self._gripper_imitation_rewards)
        info["ep_m_im_rew_mean"] = sum(self._motion_imitation_rewards)
        info["ep_g_im_rew_mean"] = sum(self._gripper_imitation_rewards)

        info["m_im_rew_mean"] = np.nan if ep_len == 0 else ep_m_im_rew / ep_len
        info["g_im_rew_mean"] = np.nan if ep_len == 0 else ep_g_im_rew / ep_len

    def _get_imitation_reward(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ):
        """Override super class method to compute an imitation reward for the `PickPlaceHumanCart` environment.

        If the object is gripped in the demonstration state but not in the training state,
        we set the imitation reward to 0. This is done to encourage learning to grasp the object,
        opposed to just learning to follow the motion of the expert.

        Otherwise, we reward similarity in end effector and gripper joint positions.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            float: imitation reward
        """
        demonstration_obs = PickPlaceHumanCartExpert.expert_observation_from_dict(demonstration_obs_dict)
        policy_obs = PickPlaceHumanCartExpert.expert_observation_from_dict(policy_obs_dict)

        if demonstration_obs.object_gripped and not policy_obs.object_gripped:
            # This might be a bit harsh...
            return 0

        motion_imitation_error = demonstration_obs.vec_eef_to_target - policy_obs.vec_eef_to_target
        gripper_imitation_error = demonstration_obs.robot0_gripper_qpos - policy_obs.robot0_gripper_qpos

        motion_imitation_reward = similarity_fn(
            name=self._m_sim_fn,
            delta=np.linalg.norm(motion_imitation_error),
            iota=self._iota_m,
        )

        gripper_imitation_reward = similarity_fn(
            name=self._g_sim_fn,
            delta=np.abs(gripper_imitation_error[0] - gripper_imitation_error[1]),
            iota=self._iota_g,
        )

        self._motion_imitation_rewards.append(motion_imitation_reward)
        self._gripper_imitation_rewards.append(gripper_imitation_reward)

        return motion_imitation_reward * self._beta + gripper_imitation_reward * (1 - self._beta)

    def _should_terminate_early(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ) -> bool:
        """Decide whether the training episode should be terminated early,
        based on the similarity between the current state reached by the agent
        and the corresponding state in the demonstration episode.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            bool: whether the training episode should be terminated early
        """
        demonstration_obs = PickPlaceHumanCartExpert.expert_observation_from_dict(demonstration_obs_dict)
        policy_obs = PickPlaceHumanCartExpert.expert_observation_from_dict(policy_obs_dict)

        motion_imitation_error_dist = np.linalg.norm(
            demonstration_obs.vec_eef_to_target - policy_obs.vec_eef_to_target
        )

        return (
            demonstration_obs.object_gripped and not policy_obs.object_gripped and
            motion_imitation_error_dist > self._et_dist * 0.1 * self._iota_m
        ) or motion_imitation_error_dist > self._et_dist * self._iota_m


class CollaborativeLiftingCartStateBasedExpertImitationRewardWrapper(
    ReachHumanStateBasedExpertImitationRewardWrapper
):
    r"""State-based expert imitation reward gym wrapper for the `CollaborativeLiftingCart` environment.

    Can be used with any environment that can be solved using the `CollaborativeLiftingCartExpert` expert policy.

    The expert observation dicts should contain all keys necessary
    to be stored as `CollaborativeLiftingCartExpertObservation` objects.

    Adds the possibility of using reference state initialization (RSI)
    to initialize the environment at a random state from the demonstration episode.

    The reward is given by this formula:
        $r = r_i * \alpha + r_{env} * (1 - \alpha)$

    Where:
        $r_{env}$: reward from wrapped environment
        $r_i = sim(||obsdiff||, \iota_m)$

        $obsdiff$: difference between demonstration and training state end effector position
        $sim$: similarity function, either $sim_G$ or $sim_T$.
            For more details, see `human_robot_gym.utils.expert_imitation_reward_utils`

    Args:
        env (Env): gym environment to wrap
        dataset_name (str): name of the expert dataset
        alpha (float): weight of imitation reward in combined reward:
            alpha = 0: only environment reward
            alpha = 1: only imitation reward
        iota (float): tolerance parameter for imitation reward:
            if the distance between demonstration and training state end effector position is smaller than `iota`,
            r_i is greater than 0.5 (1 at maximum, i.e. perfect imitation)
        sim_fn (str): similarity function to use for imitation reward. Can be either `"gaussian"` or `"tanh"`.
        observe_time (bool): whether to add a time parameter to the observation space
            normalized to the range [0, 1], where
            0: start of episode (after reset and one zero action)
            1: end of demonstration episode
            This value is clipped to one: if the training pass lasts longer than the demonstration pass,
            the time parameter is set to 1 for the rest of the episode.
            Thus, this value reflects the progress in the demonstration episode used for comparison.
        rsi_prob (float): probability of using reference state initialization (RSI)
            to initialize the environment at each reset
        use_et (bool): whether to use early termination (ET) to terminate the episode early.
            The criteria for ET are defined in subclasses.
        et_dist (float): distance threshold for early termination. Episode terminated early if `use_et` is `True`
            and the distance between the end effector positions from the expert state and the agent state
            is larger than `et_dist * iota`
        verbose (bool): whether to print debug information
    """
    def __init__(
        self,
        env: Env,
        dataset_name: str,
        alpha: float = 0,
        iota: float = 0.1,
        sim_fn: str = "gaussian",
        observe_time: bool = True,
        rsi_prob: float = 0.0,
        use_et: bool = False,
        et_dist: float = 2,
        verbose: bool = False,
    ):
        super().__init__(
            env=env,
            dataset_name=dataset_name,
            alpha=alpha,
            iota=iota,
            sim_fn=sim_fn,
            observe_time=observe_time,
            rsi_prob=rsi_prob,
            use_et=use_et,
            et_dist=et_dist,
            verbose=verbose,
        )

    def _get_imitation_reward(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ):
        """Determine the imitation reward by comparing the agent and expert states.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            float: imitation reward
        """
        demonstration_obs = CollaborativeLiftingCartExpert.expert_observation_from_dict(demonstration_obs_dict)
        policy_obs = CollaborativeLiftingCartExpert.expert_observation_from_dict(policy_obs_dict)

        if demonstration_obs.board_gripped and not policy_obs.board_gripped:
            return 0

        imitation_error = demonstration_obs.vec_eef_to_human_lh - policy_obs.vec_eef_to_human_lh

        imitation_reward = similarity_fn(
            name=self._sim_fn,
            delta=np.linalg.norm(imitation_error),
            iota=self._iota,
        )

        return imitation_reward

    def _should_terminate_early(
        self,
        demonstration_obs_dict: dict,
        policy_obs_dict: dict,
    ) -> bool:
        """Decide whether the training episode should be terminated early,
        based on the similarity between the current state reached by the agent
        and the corresponding state in the demonstration episode.

        Args:
            demonstration_obs_dict (dict): expert observation dict
                of the compared state from the demonstration trajectory
            policy_obs_dict (dict): expert observation dict
                of the current state in the training episode

        Returns:
            bool: whether the training episode should be terminated early
        """
        demonstration_obs = CollaborativeLiftingCartExpert.expert_observation_from_dict(demonstration_obs_dict)
        policy_obs = CollaborativeLiftingCartExpert.expert_observation_from_dict(policy_obs_dict)

        imitation_error_dist = np.linalg.norm(
            demonstration_obs.vec_eef_to_human_lh - policy_obs.vec_eef_to_human_lh
        )

        return (
            demonstration_obs.board_gripped and not policy_obs.board_gripped or
            imitation_error_dist > self._et_dist * self._iota
        )
