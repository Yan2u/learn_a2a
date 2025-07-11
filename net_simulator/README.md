### network-simulator

A simple simulated-network for multiple users and multiple agents. Still under development.

#### Usage

##### Configure

- Go to `net_simulator/config` and create `config.json` according to `config_example.json`.

##### Launch Server

- Synchronize pip packages and activate virtual env

  ```bash
  # in learn_a2a
  uv sync
  source .venv/bin/activate
  ```

- Use `honcho` to launch all nodes.

  ```bash
  # in learn_a2a/net_simulator
  honcho -f procfile/launch_all.procfile start
  ```

  This will launch system server and all agent servers in network together.

##### Launch Web UI

- Install packages

  ```bash
  # in learn_a2a/net_simulator/chat-ui
  npm install
  ```

- Run

  ```bash
  # in learn_a2a/net_simulator/chat-ui
  npm run dev
  ```

- Visit `http://localhost:5173/login` and login to chat with agent.

- Visit `http://localhost:5173/dashboard` to view visual network graph.

#### Backend (`net_simulator`)

A server that manages communications, registry, task end event updating.

#### Frontend (`net_simulator/chat-ui`)

An interface for users to chat with agents. Also for visualizing network graph.

#### Project structure

```
net_simulator
- chat-ui                # frontend ui
- config                 # configurations
  - agents               # agent configs
  - user_agent_prompts   # user agent prompts
  - config.json          # global configs
- data                   # data for mcp
- datamodels             # data models for system server
- executors              # executors for agents in a2a
- mcp                    # mcp servers
- msgs                   # data models for comm messages
- nodes                  # server nodes (system, public agent)
- procfile               # for honcho
- utils.py               # utils
```