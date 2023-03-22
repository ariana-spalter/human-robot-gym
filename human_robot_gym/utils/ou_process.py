"""This file contains classes to generate Ornstein-Uhlenbeck processes.

Author:
    Felix Trost (FT)

Changelog:
    05.02.23 FT File creation
"""
from typing import Optional

import numpy as np


class OrnsteinUhlenbeckProcess:
    """This class can be used to generate Ornstein-Uhlenbeck processes:
        https://en.wikipedia.org/wiki/Ornstein%E2%80%93Uhlenbeck_process

    dX_t = alpha * (gamma - X_t) dt + beta * dW_t

    W_t refers to values of a Wiener process W at time t:
        https://en.wikipedia.org/wiki/Wiener_process

    Discretized using Euler-Maruyama method:
        X_{t+1} = X_t + alpha * (gamma - X_t) * dt + beta * sqrt(dt) * N(0;1)
        N: Normal distribution

    Starting value is the mean (X_0 = gamma).

    Each OrnsteinUhlenbeckProcess instance maintains its own random number generator.

    Args:
        size (int): number of processes,
            determines length of vectors generated by step method
        alpha (float): mean reversion parameter
        beta (float): random shock parameter
        gamma (float): drift parameter
        seed (Optional[int]): seed for random number generator
    """
    def __init__(
        self,
        size: int = 1,
        alpha: float = 0.5,
        beta: float = 1,
        gamma: float = 0,
        seed: Optional[int] = None,
    ):
        self._size = size
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma
        self.y = np.full(self._size, self._gamma, dtype=np.float64)
        self._rng = np.random.default_rng(seed=seed)

    def step(self, dt: float) -> np.ndarray:
        """Discrete step to estimate values after a given time interval.

        Args:
            dt (float): time delta

        Returns:
            np.ndarray: new noise values of shape (size,)
        """
        self.y = self.y + (
            self._alpha * (self._gamma - self.y) * dt +
            self._beta * np.sqrt(dt) * self._rng.standard_normal(size=self._size)
        )

        return self.y


class ReparameterizedOrnsteinUhlenbeckProcess(OrnsteinUhlenbeckProcess):
    """This class re-parameterizes the Ornstein-Uhlenbeck process.

    It generates Ornstein-Uhlenbeck noise signals based on asymptotic mean and variance values.
    Starting value is the mean (mu).

    Each ReparameterizedOrnsteinUhlenbeckProcess instance maintains its own random number generator.

    Args:
        alpha (float): rubber band parameter, controls signal convergence speed; alpha > 0
            For higher values of alpha, the distribution of samples approaches the
            normal distribution N(mu, sigma) faster
        mu (float): signal mean value for t -> inf
        sigma (float): signal variance for t -> inf
        seed (Optional[int]): seed for random number generator
    """
    def __init__(
        self,
        size: int = 1,
        alpha: float = 0.5,
        mu: float = 0,
        sigma: float = 1,
        seed: Optional[int] = None,
    ):
        super().__init__(
            size=size,
            alpha=alpha,
            beta=sigma*np.sqrt(2*alpha),
            gamma=mu,
            seed=seed,
        )


if __name__ == "__main__":
    """Plot noise using custom parameters.
    """
    from argparse import ArgumentParser
    import matplotlib.pyplot as plt

    parser = ArgumentParser(
        description="Create Ornstein-Uhlenbeck noise processes with custom parameters."
    )

    parser.add_argument(
        "--alpha",
        type=float,
        help="Rubber band parameter",
    )

    parser.add_argument(
        "--mu",
        type=float,
        default=0,
        help="Mean value of the distribution",
    )

    parser.add_argument(
        "--sigma",
        type=float,
        default=1.0,
        help="Variance of the distribution",
    )

    parser.add_argument(
        "--dt",
        type=float,
        default=0.01,
        help="Time delta between samples",
    )

    parser.add_argument(
        "--n_proc",
        type=int,
        default=10,
        help="Number of processes",
    )

    parser.add_argument(
        "--n_steps",
        type=int,
        default=10000,
        help="Number of samples per process"
    )

    args = parser.parse_args()

    noise = ReparameterizedOrnsteinUhlenbeckProcess(
        size=args.n_proc,
        alpha=args.alpha,
        mu=args.mu,
        sigma=args.sigma,
    )

    proc = []
    for _ in range(args.n_steps):
        proc.append(noise.step(args.dt))

    proc = np.array(proc)

    fig, (ax_proc, ax_hist) = plt.subplots(2)
    ax_proc.plot(proc)
    _, bins, _ = ax_hist.hist(proc[:], density=True, bins=50)
    approx = (
        (1 / (np.sqrt(2 * np.pi) * args.sigma)) *
        np.exp(-0.5 * (1 / args.sigma * (args.mu - bins))**2)
    )
    ax_hist.plot(bins, approx, '--')
    plt.show()
