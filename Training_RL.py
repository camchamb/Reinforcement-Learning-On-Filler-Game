# Code based on tutorials on RL


import os
os.environ['TF_USE_LEGACY_KERAS'] = '1'

import collections
import gym
import statistics
import tqdm

from matplotlib import pyplot as plt
from tensorflow.keras import layers
from tensorflow import keras
from typing import Any, List, Sequence, Tuple

import abc
import tensorflow as tf
import numpy as np
import random

from tf_agents.environments import py_environment
from tf_agents.environments import tf_environment
from tf_agents.environments import tf_py_environment
from tf_agents.environments import utils
from tf_agents.specs import array_spec
from tf_agents.environments import wrappers
from tf_agents.environments import suite_gym
from tf_agents.trajectories import time_step as ts
from tensorflow.keras.layers import Dense
from tensorflow.keras.optimizers import Adam
import tensorflow_probability as tfp

import Grid
import Particle
import Test
import sand_simulation
from Test import start_game
from Test import choice


# Game environment where reward, action, and observations are obtained.
class FillerGameEnv():

  def __init__(self):
    self.grid = start_game(7, 7)
    self._episode_ended = False

  def action_spec(self):
    return self._action_spec

  def observation_spec(self):
    _observation_spec = self.grid.get_observation()
    return self._observation_spec

  def reset(self):
    self.grid = start_game(7, 7)
    self._episode_ended = False
    return self.grid.get_observation()

  def step(self, action, team):

    if self._episode_ended:
      # The last action ended the episode. Ignore the current action and start
      # a new episode.
      return self.reset()

    # Make sure episodes don't go on forever.
    col = action
    reward = 0
    if self.grid.game_over():
      self._episode_ended = True
      self.grid.num_changed = 0
      if self.grid.winner() == team:
        reward = 20
      else:
        reward = -20
    elif choice(self.grid, col) == False:
      reward = -100

    if self._episode_ended:
      return self.grid.get_observation(), reward + self.grid.num_changed, self.grid.game_over()
    else:
      return self.grid.get_observation(), reward + self.grid.num_changed, self.grid.game_over()


# An Actor-Critic Model
class ActorCriticNetwork(keras.Model):
    def __init__(self, n_actions, fc1_dims=1024, fc2_dims=512,
            name='actor_critic', chkpt_dir='tmp/actor_critic'):
        super(ActorCriticNetwork, self).__init__()
        self.fc1_dims = fc1_dims
        self.fc2_dims = fc2_dims
        self.n_actions = n_actions
        self.model_name = name
        self.checkpoint_dir = chkpt_dir
        self.checkpoint_file = os.path.join(self.checkpoint_dir, name+'_ac')

        self.fc1 = Dense(self.fc1_dims, activation='relu')
        self.fc2 = Dense(self.fc2_dims, activation='relu')
        self.v = Dense(1, activation=None)
        self.pi = Dense(n_actions, activation='softmax')

    def call(self, state):
        value = self.fc1(state)
        value = self.fc2(value)
        v = self.v(value)
        pi = self.pi(value)

        return v, pi


class Filler_Agent:
    def __init__(self, model_file, alpha=0.0003, gamma=0.99, n_actions=6):
        self.gamma = gamma
        self.n_actions = n_actions
        self.action = None
        self.action_space = [i for i in range(self.n_actions)]
        self.model_file = model_file
        self.actor_critic = ActorCriticNetwork(n_actions=n_actions)
        self.actor_critic.compile(optimizer=Adam(learning_rate=alpha))


    def choose_action(self, observation):
        state = tf.convert_to_tensor([observation])
        _, probs = self.actor_critic(state)

        action_probabilities = tfp.distributions.Categorical(probs=probs)
        action = action_probabilities.sample()
        log_prob = action_probabilities.log_prob(action)
        self.action = action

        return action.numpy()[0]

    def save_models(self):
        print(f'... saving {self.model_file} ...')
        self.actor_critic.save_weights(self.model_file)

    def load_models(self):
        print('... loading models ...')
        self.actor_critic.load_weights(self.model_file)

    def learn(self, state, reward, state_, done):
        state = tf.convert_to_tensor([state], dtype=tf.float32)
        state_ = tf.convert_to_tensor([state_], dtype=tf.float32)
        reward = tf.convert_to_tensor(reward, dtype=tf.float32) # not fed to NN
        with tf.GradientTape(persistent=True) as tape:
            state_value, probs = self.actor_critic(state)
            state_value_, _ = self.actor_critic(state_)
            state_value = tf.squeeze(state_value)
            state_value_ = tf.squeeze(state_value_)

            action_probs = tfp.distributions.Categorical(probs=probs)
            log_prob = action_probs.log_prob(self.action)

            delta = reward + self.gamma*state_value_*(1-int(done)) - state_value
            actor_loss = -log_prob*delta
            critic_loss = delta**2
            total_loss = actor_loss + critic_loss

        gradient = tape.gradient(total_loss, self.actor_critic.trainable_variables)
        self.actor_critic.optimizer.apply_gradients(zip(
            gradient, self.actor_critic.trainable_variables))


# Set up agents and train model
agent_1 = Filler_Agent('Model_1', alpha=1e-5, n_actions=6)
agent_2 = Filler_Agent('Model_2', alpha=1e-5, n_actions=6)
n_games = 300
env = FillerGameEnv()


best_score_1 = -1500
best_score_2 = -1500
score_history_1 = []
score_history_2 = []
load_checkpoint = False
load = True

if load:
    print('... loading models ...')
    agent_1.actor_critic.load_weights("old_Model_1")
    agent_2.actor_critic.load_weights("old_Model_2")

if load_checkpoint:
    agent_1.load_models()
    agent_2.load_models()

for i in range(n_games):
    observation = env.reset()
    done = False
    score_1 = 0
    score_2 = 0
    while not done:
        if env.grid.cur_player == 1:
          action = agent_1.choose_action(observation)
          # print(f"{action}, Player:{env.grid.cur_player}")
          observation_, reward, done = env.step(action, 1)
          # print(observation_)
          # print(reward)
          score_1 += reward
          if not load_checkpoint:
              agent_1.learn(observation, reward, observation_, done)
          observation = observation_
        elif env.grid.cur_player == 2:
          action = agent_2.choose_action(observation)
          # print(f"{action}, Player:{env.grid.cur_player}")
          observation_, reward, done = env.step(action, 2)
          # print(observation_)
          score_2 += reward
          if not load_checkpoint:
              agent_2.learn(observation, reward, observation_, done)
          observation = observation_
    score_history_1.append(score_1)
    avg_score_1 = np.mean(score_history_1[-5:])
    score_history_2.append(score_2)
    avg_score_2 = np.mean(score_history_2[-5:])

    if avg_score_1 > best_score_1:
        best_score_1 = avg_score_1
        if not load_checkpoint:
            agent_1.save_models()
    if avg_score_2 > best_score_2:
        best_score_2 = avg_score_2
        if not load_checkpoint:
            agent_2.save_models()
    print('episode: ', i, 'score 1: %.1f' % score_1, 'score 2: %.1f' % score_2)


print(f"best score 1 {avg_score_1}")
print(f"best score 2 {avg_score_2}")
print(f'... saving final models ...')
agent_1.actor_critic.save_weights("model_1_final")
agent_2.actor_critic.save_weights("model_2_final")
