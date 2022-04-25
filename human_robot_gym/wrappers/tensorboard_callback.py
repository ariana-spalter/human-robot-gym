import numpy as np
import gym

from stable_baselines3.common.utils import safe_mean
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.vec_env import (
    VecEnv,
    sync_envs_normalization,
)

from wandb.integration.sb3 import WandbCallback

from typing import Any, Dict, List, Union


class TensorboardCallback(WandbCallback):
    """
    Custom callback for plotting additional values in tensorboard.
    """

    def __init__(
        self,
        eval_env: Union[gym.Env, VecEnv],
        verbose: int = 0,
        model_save_path: str = None,
        model_save_freq: int = 0,
        gradient_save_freq: int = 0,
        save_freq: int = 100,
        model_file: str = "models",
        start_episode: int = 0,
        additional_log_info_keys: List[str] = ["goal_reached"],
        n_eval_episodes: int = 0,
        deterministic: bool = True,
        log_interval: int = 4,
        # log_path: Optional[str] = None,
    ):
        super(TensorboardCallback, self).__init__(
            verbose, model_save_path, model_save_freq, gradient_save_freq
        )
        self.save_freq = save_freq
        self.episode_counter = start_episode
        self.additional_log_info_keys = additional_log_info_keys
        self.model_file = model_file
        self.n_eval_episodes = n_eval_episodes
        self.deterministic = deterministic
        self._info_buffer = dict()
        for key in additional_log_info_keys:
            self._info_buffer[key] = []
        self.log_interval = log_interval
        """
        if log_path is not None:
            log_path = os.path.join(log_path, "evaluations")
        self.log_path = log_path
        """
        # eval results
        self.evaluations_results = []
        self.evaluations_timesteps = []
        self.evaluations_length = []
        # For computing success rate
        self._eval_info_buffer = dict()
        for key in additional_log_info_keys:
            self._eval_info_buffer[key] = []
        """
        self._eval_results = dict()
        for key in additional_log_info_keys:
            self._eval_results[key] = []
        """
        # We don't have seperate eval environments. You can add this if you need it.
        self.eval_env = eval_env
        if self.n_eval_episodes == 0:
            self.model_evaluated = True
        else:
            self.model_evaluated = False

    def _on_step(self) -> None:
        if self.locals["dones"][0]:
            for key in self.additional_log_info_keys:
                if key in self.locals["infos"][0]:
                    self._info_buffer[key].append(self.locals["infos"][0][key])
            if (self.episode_counter + 1) % self.log_interval == 0:
                for key in self.additional_log_info_keys:
                    if key in self.locals["infos"][0]:
                        self.logger.record(
                            "rollout/{}".format(key), safe_mean(self._info_buffer[key])
                        )
                        self._info_buffer[key] = []

    def _on_rollout_end(self) -> None:
        """
        for key in self.additional_log_info_keys:
            if key in self.locals["infos"][0]:
                self.logger.record(key, self.locals["infos"][0][key])
        """
        # self.logger.dump(self.episode_counter)
        self.episode_counter += 1
        if self.episode_counter % self.save_freq == 0:
            self.model.save(
                "{}/model_{}".format(self.model_file, str(self.episode_counter))
            )
            self.model.save_replay_buffer("{}/replay_buffer".format(self.model_file))

    def _log_success_callback(
        self, locals_: Dict[str, Any], globals_: Dict[str, Any]
    ) -> None:
        """
        Callback passed to the  ``evaluate_policy`` function
        in order to log the success rate (when applicable),
        for instance when using HER.
        :param locals_:
        :param globals_:
        """
        info = locals_["info"]

        if locals_["done"]:
            for key in self._eval_info_buffer.keys():
                maybe_is_key = info.get(key)
                if maybe_is_key is not None:
                    self._eval_info_buffer[key].append(maybe_is_key)

    def _on_training_end(self) -> bool:
        if self.model_evaluated:
            return True
        # Sync training and eval env if there is VecNormalize
        if self.model.get_vec_normalize_env() is not None:
            try:
                sync_envs_normalization(self.training_env, self.eval_env)
            except AttributeError:
                raise AssertionError(
                    "Training and eval env are not wrapped the same way, "
                    "see https://stable-baselines3.readthedocs.io/en/master/guide/callbacks.html#evalcallback "
                    "and warning above."
                )
        # Reset success rate buffer
        for key in self._eval_info_buffer.keys():
            self._eval_info_buffer[key] = []

        episode_rewards, episode_lengths = evaluate_policy(
            self.model,
            self.eval_env,
            n_eval_episodes=self.n_eval_episodes,
            render=False,
            deterministic=self.deterministic,
            return_episode_rewards=True,
            callback=self._log_success_callback,
        )
        """
        if self.log_path is not None:
            self.evaluations_timesteps.append(self.num_timesteps)
            self.evaluations_results.append(episode_rewards)
            self.evaluations_length.append(episode_lengths)

            # Save success log if present
            for key in self._eval_info_buffer.keys():
                if len(self._eval_info_buffer[key]) > 0:
                    self._eval_results[key].append(self._eval_info_buffer[key])

            np.savez(
                self.log_path,
                timesteps=self.evaluations_timesteps,
                results=self.evaluations_results,
                ep_lengths=self.evaluations_length,
                **self._eval_results,
            )
        """
        mean_reward, std_reward = np.mean(episode_rewards), np.std(episode_rewards)
        mean_ep_length, std_ep_length = np.mean(episode_lengths), np.std(
            episode_lengths
        )
        self.last_mean_reward = mean_reward

        if self.verbose > 0:
            print(
                f"Eval num_timesteps={self.num_timesteps}, "
                f"episode_reward={mean_reward:.2f} +/- {std_reward:.2f}"
            )
            print(f"Episode length: {mean_ep_length:.2f} +/- {std_ep_length:.2f}")
        # Add to current Logger
        self.logger.record("eval/num_episodes", len(episode_lengths))
        self.logger.record("eval/mean_reward", float(mean_reward))
        self.logger.record("eval/mean_ep_length", mean_ep_length)

        for key in self._eval_info_buffer.keys():
            if len(self._eval_info_buffer[key]) > 0:
                mean_val = np.mean(self._eval_info_buffer[key])
                if self.verbose > 0:
                    print(f"{key} rate: {100 * mean_val:.2f}%")
                self.logger.record(f"eval/{key}", mean_val)

        # Dump log so the evaluation results are printed with the correct timestep
        self.logger.record(
            "time/total_timesteps", self.num_timesteps, exclude="tensorboard"
        )
        self.logger.dump(self.num_timesteps)
        self.model_evaluated = True
        return True