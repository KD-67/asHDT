# How the API Request Chain Works

This document explains the full journey of a request from the UI through the API and back, and how all the pieces fit together.

---

## The Big Picture

There are three distinct layers:

1. **The backend** — defines what the API can do (the schema)
2. **The transport layer** — sends and receives requests
3. **The frontend** — calls the transport layer and uses the results

---

## Step 1: Defining the Schema (Backend, at Startup)

Everything the API can do is defined in `/backend/graphql/`, organized by domain:

```
backend/graphql/
  subjects/     queries.py, mutations.py, types.py
  modules/      queries.py, mutations.py, types.py
  datapoints/   queries.py, mutations.py, types.py
  analysis/     queries.py, mutations.py, subscriptions.py, types.py
  markersets/   queries.py, mutations.py, types.py
```

Each domain defines its own **types** (what the data looks like), **input types** (what arguments a query or mutation accepts), **queries** (read operations), and **mutations** (write operations).

These are all declared as Python classes using strawberry decorators. Strawberry reads the decorators and understands what the schema looks like — the field names, their types, what arguments they take, and what function to call when a request comes in for them.

`schema.py` then imports all of those domain-specific classes and merges them into a single unified `Query`, `Mutation`, and `Subscription` root using `strawberry.merge_types()`.

`main.py` imports the compiled schema from `schema.py` and hands it to `GraphQLRouter`, which mounts it at `POST /graphql` (and `ws://localhost:8000/graphql` for subscriptions). After this point, the schema definition work is done. Strawberry now knows everything the API can do and sits waiting for requests to arrive.

> **Key point:** The schema is compiled once at startup. When a request comes in later, strawberry uses it as a routing map — it reads the incoming query string, validates it against the schema, and dispatches it to the correct resolver function automatically.

---

## Step 2: Sending a Request (Frontend Transport Layer)

All communication with the API happens through two files in `frontend/src/lib/`:

### `gql.js` — the transport layer

This file contains three functions that handle the actual sending and receiving:

- **`gql(query, variables)`** — the workhorse. Takes a GraphQL query string and a plain JS object of variable values, sends them as an HTTP POST request to `http://localhost:8000/graphql`, waits for the JSON response, and returns the data. If the response contains errors, it throws.
- **`gqlUpload(query, variables, fileKey, file)`** — same idea, but packages the request as multipart form data for file uploads.
- **`subscribe(query, variables, onData, onError)`** — opens a WebSocket connection to `ws://localhost:8000/graphql` for real-time subscriptions. Instead of waiting for a single response, it calls `onData` each time the server pushes an update, until the stream closes.

The first argument to `gql()` is not just a name — it's a full GraphQL query string written in GraphQL syntax, like:

```js
`mutation($input: SubjectInput!) {
    createSubject(input: $input) { subjectId }
}`
```

The operation name (`createSubject`), the input type name (`SubjectInput`), and the fields you want back (`subjectId`) are all spelled out inline. The second argument is the actual variable values to fill in the `$input` placeholder. When the server receives this, strawberry validates the string against the compiled schema and rejects it if anything doesn't match — wrong field name, wrong type, missing required argument, etc.

---

## Step 3: The API Layer (Frontend, `api.js`)

`gql.js` is intentionally low-level — it just sends things and returns what comes back. All the higher-level logic lives in `api.js`.

`api.js` wraps every query and mutation in a named JS function. For example:

```js
export async function createSubject(input) {
    const data = await gql(
        `mutation($input: SubjectInput!) { createSubject(input: $input) { subjectId } }`,
        { input }
    );
    return data.createSubject.subjectId;
}
```

`api.js` also handles **camelCase → snake_case normalization**. GraphQL returns field names in camelCase (e.g. `subjectId`, `healthyMin`) because that's the JS convention strawberry follows. But the rest of the frontend uses snake_case (e.g. `subject_id`, `healthy_min`). `api.js` converts on the way back, so by the time data reaches a Svelte component it's already in snake_case and components never see raw GraphQL response objects.

---

## Step 4: The UI Components (Frontend, Svelte)

Svelte components import functions from `api.js` and call them like any regular async JS function:

```js
import { createSubject, fetchSubjectData } from "../lib/api.js";

const id = await createSubject({ first_name: "Jane", ... });
const subjects = await fetchSubjectData();
```

They don't know or care about GraphQL, HTTP, or JSON. They just call a function and get data back.

The one exception is `request_report_form.svelte`, which imports `subscribe` directly from `gql.js` to open the WebSocket subscription for real-time analysis job updates, since that involves streaming (not a simple call-and-return).

---

## The Full Chain, End to End

```
User interacts with a Svelte component
  → component calls an api.js function (e.g. createSubject(input))
    → api.js builds the full GraphQL mutation string and calls gql()
      → gql.js sends HTTP POST to http://localhost:8000/graphql
        → strawberry validates the query string against the compiled schema
          → routes to the correct resolver function in /backend/graphql/{domain}/mutations.py
            → resolver reads/writes SQLite, the filesystem, or enqueues a Redis job
              → returns a result object
                → strawberry serializes it to JSON and sends it back
                  → gql.js receives the JSON response and returns data
                    → api.js normalizes camelCase → snake_case
                      → Svelte component receives a plain JS object and updates the UI
```

### For analysis jobs specifically, there's an extra async leg:

```
submitAnalysis mutation fires → server enqueues job to Redis → returns job_id immediately
  → component opens a WebSocket subscription (subscribe() from gql.js) with that job_id
    → ARQ worker picks up the job, runs the analysis pipeline
      → worker publishes progress updates to Redis pub/sub channel "job:{job_id}"
        → subscription resolver in /backend/graphql/analysis/subscriptions.py forwards each update
          → gql.js calls onData() with each update
            → component updates progress UI in real time
              → when status = COMPLETED, component stores the report in localStorage and navigates to the report page
```

---

## Where Things Are Defined vs. Where They're Used

| Thing | Defined in | Used by |
|---|---|---|
| Types, inputs, queries, mutations | `/backend/graphql/{domain}/` | strawberry schema (internal only) |
| Compiled schema | `schema.py` | `main.py` → `GraphQLRouter` |
| App context (db_path, redis, etc.) | `context.py` | every resolver, via `info.context` |
| HTTP/WebSocket transport | `frontend/src/lib/gql.js` | `api.js`, `request_report_form.svelte` |
| Named API functions + normalization | `frontend/src/lib/api.js` | all Svelte components |
| UI + user interaction | `frontend/src/components/*.svelte` | the user |
| Analysis computation | `backend/core/` | `backend/workers/analysis_tasks.py` |
| Async job execution | `backend/workers/analysis_tasks.py` | Redis / ARQ (no GraphQL involvement) |
