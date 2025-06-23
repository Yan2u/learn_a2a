### learn a2a

Demo projects learning [google-a2a-samples](https://github.com/google-a2a/a2a-samples)

#### search_summary

A simple project using 3 agents to perfrom a sequential search-and-summary work.

- Searcher agent: Searches bing.com and returns json results.
- Summarizer agent: Call LLM using OpenAI Api, and summarize search results with to sections: brief and table.
- Orchestrator agent: Deal with user input and sequentially calling two agents above to complete the tasks.

For details, see `search_summary/README.md`.