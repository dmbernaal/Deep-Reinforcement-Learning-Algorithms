import gym
from collections import namedtuple
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim

# Hyperparameters
HIDDEN_SIZE = 128
BATCH_SIZE = 16
PERCENTILE = 70

## Neural Network - 1 hidden layer
class Net(nn.Module):
  def __init__(self, obs_size, hidden_size, n_actions):
    super(Net, self).__init__()
    self.net = nn.Sequential(
        nn.Linear(obs_size, hidden_size),
        nn.ReLU(),
        nn.Linear(hidden_size, n_actions)
      )

  def forward(self, x):
    return self.net(x)

Episode = namedtuple('Episode', field_names=['reward', 'steps'])
EpisodeStep = namedtuple('EpisodeStep', field_names=['observation', 'action'])

def iterate_batches(env, net, batch_size):
  batch = []
  episode_reward = 0.0
  episode_steps = []
  obs = env.reset()
  sm = nn.Softmax(dim=1)
  while True:
    obs_v = torch.Tensor([obs])
    act_probs_v = sm(net(obs_v))
    act_probs = act_probs_v.data.numpy()[0]
    action = np.random.choice(len(act_probs), p=act_probs)
    next_obs, reward, is_done, _ = env.step(action)

    episode_reward += reward
    episode_steps.append(EpisodeStep(observation=obs, action=action))

    if is_done:
      batch.append(Episode(reward=episode_reward, steps=episode_steps))
      episode_reward = 0.0
      episode_steps = []

      next_obs = env.reset()
      if len(batch) == batch_size:
        yield batch
        batch = []

    obs = next_obs


def filter_batch(batch, percentile):
  rewards = list(map(lambda s: s.reward, batch))
  reward_bound = np.percentile(rewards, percentile)
  reward_mean = float(np.mean(rewards))

  train_obs = []
  train_act = []

  for example in batch:
    if example.reward < reward_bound:
      continue
    train_obs.extend(map(lambda step: step.observation, example.steps))
    train_act.extend(map(lambda step: step.action, example.steps))

  train_obs_v = torch.Tensor(train_obs)
  train_act_v = torch.LongTensor(train_act)

  return train_obs_v, train_act_v, reward_bound, reward_mean


if __name__ == "__main__":
  env = gym.make('CartPole-v0')

  obs_size = env.observation_space.shape[0]
  n_actions = env.action_space.n

  net = Net(obs_size, HIDDEN_SIZE, n_actions)
  objective = nn.CrossEntropyLoss()
  optimizer = optim.Adam(params=net.parameters(), lr=0.05)

  for iter_no, batch in enumerate(iterate_batches(env, net, BATCH_SIZE)):
    env.render()
    obs_v, acts_v, reward_b, reward_m = filter_batch(batch, PERCENTILE)

    optimizer.zero_grad()
    action_scores_v = net(obs_v)

    loss_v = objective(action_scores_v, acts_v)
    loss_v.backward()

    optimizer.step()

    print(f'{iter_no}: loss={loss_v.item()}, reward_mean={reward_m}, reward_bound={reward_b}')
    print(f'Observation size: {obs_v.shape[0]}')
    print(f'Actions size: {acts_v.shape[0]}\n\n')

    if reward_m > 199:
      print('Solved!')
      env.close()
      break