// Shared reactive store for subjects and modules.
// Fetches each list exactly once per session; components call ensure* on mount.
// All mutations flow through store helpers so components never re-fetch.

import { fetchSubjectData, fetchModulesFull } from './api.js';

export const appState = $state({
    subjects: [],         // full fields: subject_id, first_name, last_name, sex, dob, email, phone, notes, created_at
    subjectsLoaded: false,
    modules: [],          // full fields: module_id, module_name, description, markers[...]
    modulesLoaded: false,
});

// Guard flags prevent duplicate in-flight requests
let subjectsLoading = false;
let modulesLoading  = false;

export async function ensureSubjectsLoaded() {
    if (appState.subjectsLoaded || subjectsLoading) return;
    subjectsLoading = true;
    try {
        const subs = await fetchSubjectData();
        appState.subjects = subs;
        appState.subjectsLoaded = true;
    } finally {
        subjectsLoading = false;
    }
}

export async function ensureModulesLoaded() {
    if (appState.modulesLoaded || modulesLoading) return;
    modulesLoading = true;
    try {
        const mods = await fetchModulesFull();
        appState.modules = mods;
        appState.modulesLoaded = true;
    } finally {
        modulesLoading = false;
    }
}

// ── Subject store helpers ─────────────────────────────────────────────────────

// Appends appState.subjects with new object
export function storeAddSubject(subject) {
    appState.subjects.push(subject);
}

// Assings the updates to the specified object in appState.subjects
export function storeUpdateSubject(id, updates) {
    const found = appState.subjects.find(s => s.subject_id === id);
    if (found) Object.assign(found, updates);
}

// Removes the specified object from appState.subjects
export function storeRemoveSubject(id) {
    appState.subjects = appState.subjects.filter(s => s.subject_id !== id);
}

// ── Module store helpers ──────────────────────────────────────────────────────

// Pushes appState.modules with new object
export function storeAddModule(module) {
    appState.modules.push(module);
}

// Assings the updates to the specified object in appState.modules
export function storeUpdateModule(id, updates) {
    const found = appState.modules.find(m => m.module_id === id);
    if (found) Object.assign(found, updates);
}

// Removes the specified object from appState.modules
export function storeRemoveModule(id) {
    appState.modules = appState.modules.filter(m => m.module_id !== id);
}

// ── Marker store helpers ──────────────────────────────────────────────────────

// Finds parent module in appState.modules, then pushes new marker object to it's .markers array
export function storeAddMarker(moduleId, marker) {
    const mod = appState.modules.find(m => m.module_id === moduleId);
    if (mod) mod.markers.push(marker);
}

// Finds the module, then finds the marker, then updates the specified object
export function storeUpdateMarker(moduleId, markerId, updates) {
    const mod = appState.modules.find(m => m.module_id === moduleId);
    if (!mod) return;
    const mk = mod.markers.find(mk => mk.marker_id === markerId);
    if (mk) Object.assign(mk, updates);
}

// Finds the module, then replaces .markers array with a filtered copy that excluded specified object
export function storeRemoveMarker(moduleId, markerId) {
    const mod = appState.modules.find(m => m.module_id === moduleId);
    if (mod) mod.markers = mod.markers.filter(mk => mk.marker_id !== markerId);
}
