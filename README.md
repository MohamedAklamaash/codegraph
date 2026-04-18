# CodeGraph

CodeGraph takes a GitHub repository URL and turns its codebase into an interactive visual graph. It parses the source code, traces function calls, and explicitly maps out the relationships between different parts of a project so you can understand how everything fits together without having to manually grep through files.

![CodeGraph dashboard showing the keystore C++ repo](demo/graph.png)

## Features

- **Interactive Node Graph**: View the entire codebase as a network where every function is a node and every function call is an edge. You can click, drag, and play around with nodes to explore the architecture.
- **Directory and File Views**: Browse the repository structure in the sidebar. You can filter the graph to isolate the flow of a single file, or narrow down the graph to focus on a specific directory.
- **Function Inspection**: Click on any node to instantly see what file it lives in, its line numbers, and its direct dependencies.
- **Semantic Chat**: Ask plain language questions about the codebase (like "where is the billing logic handled?") and get direct answers backed by the underlying graph data.

## Supported Languages

Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Kotlin.

## Running Locally

You need Docker and Docker Compose. 

1. Copy `backend/.env.local` to `backend/.env`
2. Add your Gemini API key (free at https://aistudio.google.com/app/apikey)
3. Run `docker compose up --build`

When you submit a repository, the system silently clones it, extracts the functions, builds the graph, and generates embeddings for search. Small repositories usually take under a minute.

## Managing Repositories

You can jump between different repositories you've loaded using the dropdown menu. If a repository has been updated upstream, simply click the re-analyze button to pull the latest changes and rebuild the graph from scratch.