// Shared GraphQL client utility.
// Provides gql() for queries/mutations, gqlUpload() for file uploads,
// and subscribe() for WebSocket subscriptions.

const GQL_URL    = "http://localhost:8000/graphql";
const GQL_WS_URL = "ws://localhost:8000/graphql";

/** Send a query or mutation. Returns data or throws with the first GraphQL error message. */
export async function gql(query, variables = {}) {
    const res  = await fetch(GQL_URL, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ query, variables }),
    });
    const json = await res.json();
    if (json.errors?.length) throw new Error(json.errors[0].message);
    return json.data;
}

/**
 * Send a mutation that includes a file upload (GraphQL multipart request spec).
 * fileKey is the variable name (e.g. "file") and file is a File object.
 */
export async function gqlUpload(query, variables, fileKey, file) {
    const form = new FormData();
    form.append("operations", JSON.stringify({ query, variables: { ...variables, [fileKey]: null } }));
    form.append("map",        JSON.stringify({ "0": [`variables.${fileKey}`] }));
    form.append("0", file);
    const res  = await fetch(GQL_URL, { method: "POST", body: form });
    const json = await res.json();
    if (json.errors?.length) throw new Error(json.errors[0].message);
    return json.data;
}

/**
 * Open a GraphQL subscription over WebSocket (graphql-transport-ws protocol).
 * onData is called with each payload.data object.
 * onError is called with an Error object on failure.
 * Returns a cleanup function that closes the socket.
 */
export function subscribe(query, variables, onData, onError) {
    const ws = new WebSocket(GQL_WS_URL, "graphql-transport-ws");
    const id = String(Math.random());

    ws.onopen = () => {
        ws.send(JSON.stringify({ type: "connection_init" }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "connection_ack") {
            ws.send(JSON.stringify({ id, type: "subscribe", payload: { query, variables } }));
        } else if (msg.type === "next" && msg.id === id) {
            if (msg.payload.errors?.length) {
                onError?.(new Error(msg.payload.errors[0].message));
            } else {
                onData(msg.payload.data);
            }
        } else if (msg.type === "error" && msg.id === id) {
            onError?.(new Error(msg.payload?.[0]?.message ?? "Subscription error"));
        } else if (msg.type === "complete" && msg.id === id) {
            ws.close();
        }
    };

    ws.onerror = () => onError?.(new Error("WebSocket connection error"));

    return () => ws.close();
}
