### learn a2a

Demo projects learning [google-a2a-samples](https://github.com/google-a2a/a2a-samples)

#### search_summary

A simple project using 3 agents to perfrom a sequential search-and-summary work.

- Searcher agent: Searches bing.com and returns json results.
- Summarizer agent: Call LLM using OpenAI Api, and summarize search results with to sections: brief and table.
- Orchestrator agent: Deal with user input and sequentially calling two agents above to complete the tasks.

For details, see `search_summary/README.md`.


#### image_description

A simple project to test multimodal data (text, image, audio) with google a2a protocol.

Use 3 agents to:

- Use pure text prompts and image to generate descriptions.
- Use audio prompts and image to generate descriptions.

Agents:

- Image Descriptor Agent: Generate descriptions using `gpt-4o` with given image and text prompts.
- Speech2Text Agent: Convert audio to text using `gpt-4o-audio`.
- User Agent: Call agents above to deal with user inputs. Both `text+image` and `audio+image` forms are accepted.

For details, see `image_description/README.md`.

#### network-simulator

A simple simulated-network for multiple users and multiple agents. Still under development.

##### Usage

**Configure**

- Go to `net_simulator/config` and create `config.json` according to `config_example.json`.

**Launch Server**

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

**Launch Web UI**

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

##### Backend (`net_simulator`)

A server that manages communications, registry, task end event updating.

##### Frontend (`net_simulator/chat-ui`)

An interface for users to chat with agents. Also for visualizing network graph.