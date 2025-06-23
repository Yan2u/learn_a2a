### search_summary

A simple project using 3 agents to perfrom a sequential search-and-summary work.

Search engine is [bing](https://www.bing.com).

#### Agents

- Searcher agent: Searches bing.com and returns json results.
- Summarizer agent: Call LLM using OpenAI Api, and summarize search results with to sections: brief and table.
- Orchestrator agent: Deal with user input and sequentially calling two agents above to complete the tasks.

#### Usage

1. Initialize venv and install packages using `uv` (in root folder `learn_a2a`).

```bash
# in learn_a2a
uv venv
source .venv/bin/activate
uv sync
```

2. Create/Edit `.env` file to configure the project (in `learn_a2a/search_summary`):

```bash
# learn_a2a/search_summary/.env
API_KEY=${your api key}
BASE_URL=${your api base url}
MODEL=${model name to call}
SEARCHER_PORT=8000 # port of searcher agent
SUMMARIZER_PORT=8001 # port of summarizer agent
ORCHESTRATOR_PORT=8002 # port of orchestrator agent
```

3. Launch 3 agents (in 3 different terminals)

```bash
# terminal 1
# in learn_a2a/search_summary
uv run searcher.py

# terminal 2
# in learn_a2a/search_summary
uv run summarizer.py

# terminal 3
# in learn_a2a/search_summary
uv run orchestrator.py
```

4. Run tests

```bash
# in learn_a2a/search_summary
uv run test_client.py
```

Open `test_client.py` and edit `QUERY` to test for different query keywords.