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