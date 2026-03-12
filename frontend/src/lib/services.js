// Service layer — wraps API calls with automatic appState store updates.
// Components import mutating operations from here instead of api.js directly.

import {
    createSubject as apiCreateSubject,
    updateSubject as apiUpdateSubject,
    deleteSubject as apiDeleteSubject,
    createModule  as apiCreateModule,
    updateModule  as apiUpdateModule,
    deleteModule  as apiDeleteModule,
    createMarker  as apiCreateMarker,
    updateMarker  as apiUpdateMarker,
    deleteMarker  as apiDeleteMarker,
} from './api.js';

import {
    storeAddSubject,  storeUpdateSubject,  storeRemoveSubject,
    storeAddModule,   storeUpdateModule,   storeRemoveModule,
    storeAddMarker,   storeUpdateMarker,   storeRemoveMarker,
} from './stores.svelte.js';


// ── Subjects ──────────────────────────────────────────────────────────────────

export async function createSubject({ first_name, last_name, sex, dob, email, phone, notes }) {
    const subject_id = await apiCreateSubject({ firstName: first_name, lastName: last_name, sex, dob, email, phone, notes });
    storeAddSubject({ subject_id, first_name, last_name, sex, dob, email, phone, notes, created_at: new Date().toISOString() });
    return subject_id;
}

export async function updateSubject(subject_id, { first_name, last_name, sex, dob, email, phone, notes }) {
    await apiUpdateSubject(subject_id, { firstName: first_name, lastName: last_name, sex, dob, email, phone, notes });
    storeUpdateSubject(subject_id, { first_name, last_name, sex, dob, email, phone, notes });
}

export async function deleteSubject(subject_id) {
    await apiDeleteSubject(subject_id);
    storeRemoveSubject(subject_id);
}


// ── Modules ───────────────────────────────────────────────────────────────────

export async function createModule({ module_id, module_name, description }) {
    await apiCreateModule({ moduleId: module_id, moduleName: module_name, description });
    storeAddModule({ module_id, module_name, description, markers: [] });
}

export async function updateModule(module_id, { module_name, description }) {
    await apiUpdateModule(module_id, { moduleName: module_name, description });
    storeUpdateModule(module_id, { module_name, description });
}

export async function deleteModule(module_id) {
    await apiDeleteModule(module_id);
    storeRemoveModule(module_id);
}


// ── Markers ───────────────────────────────────────────────────────────────────

export async function createMarker(module_id, { marker_id, marker_name, description, unit, volatility_class, healthy_min, healthy_max, vulnerability_margin }) {
    await apiCreateMarker(module_id, {
        markerId:            String(marker_id).trim(),
        markerName:          String(marker_name).trim(),
        description:         String(description).trim(),
        unit:                String(unit).trim(),
        volatilityClass:     String(volatility_class).trim(),
        healthyMin:          parseFloat(healthy_min),
        healthyMax:          parseFloat(healthy_max),
        vulnerabilityMargin: parseFloat(vulnerability_margin),
    });
    storeAddMarker(module_id, {
        marker_id:        String(marker_id).trim(),
        marker_name:      String(marker_name).trim(),
        description:      String(description).trim(),
        unit:             String(unit).trim(),
        volatility_class: String(volatility_class).trim(),
    });
}

export async function updateMarker(module_id, marker_id, { marker_name, description, unit, volatility_class, healthy_min, healthy_max, vulnerability_margin }) {
    await apiUpdateMarker(module_id, marker_id, {
        markerName:          marker_name,
        description,
        unit,
        volatilityClass:     volatility_class,
        healthyMin:          parseFloat(healthy_min),
        healthyMax:          parseFloat(healthy_max),
        vulnerabilityMargin: parseFloat(vulnerability_margin),
    });
    storeUpdateMarker(module_id, marker_id, { marker_name, description, unit, volatility_class });
}

export async function deleteMarker(module_id, marker_id) {
    await apiDeleteMarker(module_id, marker_id);
    storeRemoveMarker(module_id, marker_id);
}
