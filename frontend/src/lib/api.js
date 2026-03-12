// Shared GraphQL query constants and typed fetch wrappers.
// All fetch functions return snake_case objects; camelCase normalisation happens here.
// Components import these instead of embedding query strings inline.

import { gql, gqlUpload } from "./gql.js";

// ── Query string constants ────────────────────────────────────────────────────

export const MODULES_BASIC = `query { modules { moduleId moduleName markers { markerId markerName } } }`;

export const MODULES_FULL = `query { modules { moduleId moduleName description markers {
    markerId markerName description unit volatilityClass
} } }`;

export const ANALYSIS_METHODS = `query {
    analysisMethods {
        methodId methodName description status
        acceptsSingleMarker acceptsMarkerset
        minMarkers maxMarkers paramsSchema outputType
    }
}`;

export const MARKERSET_TEMPLATES_FULL = `query { markersetTemplates { markersetId name description markers {
    moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
} createdAt } }`;

export const JOB_STATUS_SUBSCRIPTION = `subscription($jobId: String!) {
    jobStatus(jobId: $jobId) {
        status progress errorMessage
        result {
            ... on TrajectoryReport {
                reportId
                datapoints {
                    timestamp xHours rawValue dataQuality
                    healthScore fittedValue zone
                    fPrime fDoublePrime trajectoryState timeToTransitionHours
                }
                fitMetadata {
                    coefficients t0Iso
                    zoneBoundaries { vulnerabilityMargin }
                }
            }
        }
    }
}`;

// ── Markerset marker field normaliser (shared by template + instance) ─────────

function normaliseMarkersetMarker(m) {
    return {
        module_id:              m.moduleId,
        marker_id:              m.markerId,
        weight:                 m.weight ?? 1.0,
        active:                 m.active ?? true,
        transform_type:         m.transformType ?? "none",
        transform_window_hours: m.transformWindowHours ?? null,
        transform_lag_hours:    m.transformLagHours ?? null,
        missing_data:           m.missingData ?? "interpolate",
    };
}

const MARKERSET_TEMPLATE_FIELDS = `markersetId name description markers {
    moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
} createdAt`;

const MARKERSET_INSTANCE_FIELDS = `instanceId subjectId markersetId name markers {
    moduleId markerId weight active transformType transformWindowHours transformLagHours missingData
} createdAt`;

// ── Read functions ────────────────────────────────────────────────────────────

const SUBJECT_FIELD_MAP = {
    subject_id: 'subjectId',
    first_name: 'firstName',
    last_name:  'lastName',
    sex:        'sex',
    dob:        'dob',
    email:      'email',
    phone:      'phone',
    notes:      'notes',
    created_at: 'createdAt',
};

const ALL_SUBJECT_FIELDS = ['subject_id', 'first_name', 'last_name', 'sex', 'dob', 'email', 'phone', 'notes', 'created_at'];

/**
 * Fetches subject(s) with the specified fields.
 * subjectId=null → returns array of all subjects.
 * subjectId="some_id" → returns a single object or null.
 * fields defaults to all subject fields.
 */
export async function fetchSubjectData(subjectId = null, fields = ALL_SUBJECT_FIELDS) {
    const gqlFields = fields.map(f => SUBJECT_FIELD_MAP[f]).join(' ');
    function mapObj(obj) {
        const result = {};
        for (const f of fields) result[f] = obj[SUBJECT_FIELD_MAP[f]];
        return result;
    }
    if (subjectId === null) {
        const data = await gql(`query { subjects { ${gqlFields} } }`);
        return data.subjects.map(mapObj);
    } else {
        const data = await gql(
            `query($id: String!) { subject(subjectId: $id) { ${gqlFields} } }`,
            { id: subjectId }
        );
        return data.subject ? mapObj(data.subject) : null;
    }
}

/** Returns [{ module_id, module_name, markers: [{ marker_id, marker_name }] }] */
export async function fetchModulesBasic() {
    const data = await gql(MODULES_BASIC);
    return data.modules.map(m => ({
        module_id:   m.moduleId,
        module_name: m.moduleName,
        markers:     m.markers.map(mk => ({ marker_id: mk.markerId, marker_name: mk.markerName })),
    }));
}

/** Returns [{ module_id, module_name, description, markers: [{ marker_id, marker_name, description, unit, volatility_class }] }] */
export async function fetchModulesFull() {
    const data = await gql(MODULES_FULL);
    return data.modules.map(m => ({
        module_id:   m.moduleId,
        module_name: m.moduleName,
        description: m.description,
        markers:     m.markers.map(mk => ({
            marker_id:        mk.markerId,
            marker_name:      mk.markerName,
            description:      mk.description,
            unit:             mk.unit,
            volatility_class: mk.volatilityClass,
        })),
    }));
}

/**
 * Returns normalised analysis method list.
 * Falls back to a hardcoded trajectory entry if the server is unreachable.
 */
export async function fetchAnalysisMethods() {
    try {
        const data = await gql(ANALYSIS_METHODS);
        return data.analysisMethods.map(m => ({
            method_id:             m.methodId,
            method_name:           m.methodName,
            description:           m.description,
            status:                m.status,
            accepts_single_marker: m.acceptsSingleMarker,
            accepts_markerset:     m.acceptsMarkerset,
            params_schema:         m.paramsSchema,
        }));
    } catch (e) {
        console.error("Failed to load analysis methods:", e);
        return [{
            method_id:             "trajectory",
            method_name:           "Trajectory Analysis",
            description:           "Polynomial fit + 27-state classification.",
            status:                "implemented",
            accepts_single_marker: true,
            accepts_markerset:     true,
            params_schema:         "trajectory",
        }];
    }
}

/**
 * Returns [{ instance_id, name }] for the given subject, or [] if no subjectId provided.
 * Silently returns [] on error.
 */
export async function fetchMarkersetInstancesSlim(subjectId) {
    if (!subjectId || subjectId === "nothing") return [];
    try {
        const data = await gql(
            `query($s: String!) { markersetInstances(subjectId: $s) { instanceId name } }`,
            { s: subjectId }
        );
        return data.markersetInstances.map(i => ({ instance_id: i.instanceId, name: i.name }));
    } catch (e) {
        console.error("Failed to load markerset instances:", e);
        return [];
    }
}

/** Returns [{ markerset_id, name, description, markers: [...], created_at }] */
export async function fetchMarkersetTemplates() {
    const data = await gql(MARKERSET_TEMPLATES_FULL);
    return data.markersetTemplates.map(mapMarkersetTemplate);
}

/** Returns full instances with markers for the given subject. */
export async function fetchMarkersetInstancesFull(subjectId) {
    const data = await gql(
        `query($s: String!) { markersetInstances(subjectId: $s) { ${MARKERSET_INSTANCE_FIELDS} } }`,
        { s: subjectId }
    );
    return data.markersetInstances.map(mapMarkersetInstance);
}

/** Returns [{ module_id, marker_id, entry_count }] */
export async function fetchDatasets(subjectId) {
    const data = await gql(
        `query($s: String!) { datasets(subjectId: $s) { moduleId markerId entryCount } }`,
        { s: subjectId }
    );
    return data.datasets.map(d => ({
        module_id:   d.moduleId,
        marker_id:   d.markerId,
        entry_count: d.entryCount,
    }));
}

/** Returns [{ measured_at, value, unit, data_quality }] */
export async function fetchDatapoints(subjectId, moduleId, markerId) {
    const data = await gql(
        `query($s: String!, $mo: String!, $ma: String!) {
            datapoints(subjectId: $s, moduleId: $mo, markerId: $ma) {
                measuredAt value unit dataQuality
            }
        }`,
        { s: subjectId, mo: moduleId, ma: markerId }
    );
    return data.datapoints.map(dp => ({
        measured_at:  dp.measuredAt,
        value:        dp.value,
        unit:         dp.unit,
        data_quality: dp.dataQuality,
    }));
}

/**
 * Returns { healthy_min, healthy_max, vulnerability_margin, note } or null.
 */
export async function fetchZoneReference(subjectId, moduleId, markerId) {
    const data = await gql(
        `query($s: String!, $mo: String!, $ma: String!) {
            zoneReference(subjectId: $s, moduleId: $mo, markerId: $ma) {
                healthyMin healthyMax vulnerabilityMargin note
            }
        }`,
        { s: subjectId, mo: moduleId, ma: markerId }
    );
    const ref = data.zoneReference;
    if (!ref) return null;
    return {
        healthy_min:          ref.healthyMin,
        healthy_max:          ref.healthyMax,
        vulnerability_margin: ref.vulnerabilityMargin,
        note:                 ref.note,
    };
}

/** Returns [{ sex, age, healthy_min, healthy_max, vulnerability_margin }] */
export async function fetchDemographicZones(moduleId, markerId) {
    const data = await gql(
        `query($mo: String!, $ma: String!) {
            demographicZones(moduleId: $mo, markerId: $ma) {
                sex age healthyMin healthyMax vulnerabilityMargin
            }
        }`,
        { mo: moduleId, ma: markerId }
    );
    return data.demographicZones.map(r => ({
        sex:                  r.sex,
        age:                  r.age,
        healthy_min:          r.healthyMin,
        healthy_max:          r.healthyMax,
        vulnerability_margin: r.vulnerabilityMargin,
    }));
}

// ── Subject mutations ─────────────────────────────────────────────────────────

/** Returns subject_id string */
export async function createSubject(input) {
    const data = await gql(
        `mutation($input: SubjectInput!) { createSubject(input: $input) { subjectId } }`,
        { input }
    );
    return data.createSubject.subjectId;
}

export async function updateSubject(subjectId, input) {
    await gql(
        `mutation($id: String!, $input: SubjectInput!) { updateSubject(subjectId: $id, input: $input) { subjectId } }`,
        { id: subjectId, input }
    );
}

export async function deleteSubject(subjectId) {
    await gql(
        `mutation($id: String!) { deleteSubject(subjectId: $id) }`,
        { id: subjectId }
    );
}

// ── Module mutations ──────────────────────────────────────────────────────────

/** Returns module_id string */
export async function createModule(input) {
    const data = await gql(
        `mutation($input: ModuleInput!) { createModule(input: $input) { moduleId } }`,
        { input }
    );
    return data.createModule.moduleId;
}

export async function updateModule(moduleId, input) {
    await gql(
        `mutation($id: String!, $input: ModuleUpdateInput!) { updateModule(moduleId: $id, input: $input) { moduleId } }`,
        { id: moduleId, input }
    );
}

export async function deleteModule(moduleId) {
    await gql(
        `mutation($id: String!) { deleteModule(moduleId: $id) }`,
        { id: moduleId }
    );
}

// ── Marker mutations ──────────────────────────────────────────────────────────

/** Returns marker_id string */
export async function createMarker(moduleId, input) {
    const data = await gql(
        `mutation($mo: String!, $input: MarkerInput!) { createMarker(moduleId: $mo, input: $input) { markerId } }`,
        { mo: moduleId, input }
    );
    return data.createMarker.markerId;
}

export async function updateMarker(moduleId, markerId, input) {
    await gql(
        `mutation($mo: String!, $ma: String!, $input: MarkerUpdateInput!) { updateMarker(moduleId: $mo, markerId: $ma, input: $input) { markerId } }`,
        { mo: moduleId, ma: markerId, input }
    );
}

export async function deleteMarker(moduleId, markerId) {
    await gql(
        `mutation($mo: String!, $ma: String!) { deleteMarker(moduleId: $mo, markerId: $ma) }`,
        { mo: moduleId, ma: markerId }
    );
}

// ── Demographic zone mutations ────────────────────────────────────────────────

export async function addDemographicZone(moduleId, markerId, input) {
    await gql(
        `mutation($mo: String!, $ma: String!, $input: DemographicZoneInput!) {
            addDemographicZone(moduleId: $mo, markerId: $ma, input: $input) { sex age }
        }`,
        { mo: moduleId, ma: markerId, input }
    );
}

export async function updateDemographicZone(moduleId, markerId, sex, age, input) {
    await gql(
        `mutation($mo: String!, $ma: String!, $sex: String!, $age: Int!, $input: ZoneBoundaryInput!) {
            updateDemographicZone(moduleId: $mo, markerId: $ma, sex: $sex, age: $age, input: $input) { sex age }
        }`,
        { mo: moduleId, ma: markerId, sex, age, input }
    );
}

export async function deleteDemographicZone(moduleId, markerId, sex, age) {
    await gql(
        `mutation($mo: String!, $ma: String!, $sex: String!, $age: Int!) {
            deleteDemographicZone(moduleId: $mo, markerId: $ma, sex: $sex, age: $age)
        }`,
        { mo: moduleId, ma: markerId, sex, age }
    );
}

// ── Datapoint mutations ───────────────────────────────────────────────────────

/** Returns measured_at string */
export async function addDatapoint(subjectId, moduleId, markerId, input) {
    const data = await gql(
        `mutation($s: String!, $mo: String!, $ma: String!, $input: DatapointInput!) {
            addDatapoint(subjectId: $s, moduleId: $mo, markerId: $ma, input: $input) { measuredAt }
        }`,
        { s: subjectId, mo: moduleId, ma: markerId, input }
    );
    return data.addDatapoint.measuredAt;
}

/** Returns measured_at string */
export async function updateDatapoint(subjectId, moduleId, markerId, originalMeasuredAt, input) {
    const data = await gql(
        `mutation($s: String!, $mo: String!, $ma: String!, $orig: String!, $input: DatapointInput!) {
            updateDatapoint(subjectId: $s, moduleId: $mo, markerId: $ma, originalMeasuredAt: $orig, input: $input) { measuredAt }
        }`,
        { s: subjectId, mo: moduleId, ma: markerId, orig: originalMeasuredAt, input }
    );
    return data.updateDatapoint.measuredAt;
}

export async function deleteDatapoint(subjectId, moduleId, markerId, measuredAt) {
    await gql(
        `mutation($s: String!, $mo: String!, $ma: String!, $ts: String!) {
            deleteDatapoint(subjectId: $s, moduleId: $mo, markerId: $ma, measuredAt: $ts)
        }`,
        { s: subjectId, mo: moduleId, ma: markerId, ts: measuredAt }
    );
}

/** Returns measured_at string */
export async function uploadDatapoint(subjectId, moduleId, markerId, file) {
    const data = await gqlUpload(
        `mutation($s: String!, $mo: String!, $ma: String!, $file: Upload!) {
            uploadDatapoint(subjectId: $s, moduleId: $mo, markerId: $ma, file: $file) { measuredAt }
        }`,
        { s: subjectId, mo: moduleId, ma: markerId },
        "file",
        file
    );
    return data.uploadDatapoint.measuredAt;
}

export async function deleteDataset(subjectId, moduleId, markerId) {
    await gql(
        `mutation($s: String!, $mo: String!, $ma: String!) {
            deleteDataset(subjectId: $s, moduleId: $mo, markerId: $ma)
        }`,
        { s: subjectId, mo: moduleId, ma: markerId }
    );
}

// ── Markerset mutations ───────────────────────────────────────────────────────

/** Returns full normalised template object */
export async function createMarkersetTemplate(input) {
    const data = await gql(
        `mutation($input: CreateMarkersetTemplateInput!) {
            createMarkersetTemplate(input: $input) { ${MARKERSET_TEMPLATE_FIELDS} }
        }`,
        { input }
    );
    return mapMarkersetTemplate(data.createMarkersetTemplate);
}

/** Returns full normalised template object */
export async function updateMarkersetTemplate(markersetId, input) {
    const data = await gql(
        `mutation($id: String!, $input: CreateMarkersetTemplateInput!) {
            updateMarkersetTemplate(markersetId: $id, input: $input) { ${MARKERSET_TEMPLATE_FIELDS} }
        }`,
        { id: markersetId, input }
    );
    return mapMarkersetTemplate(data.updateMarkersetTemplate);
}

export async function deleteMarkersetTemplate(markersetId) {
    await gql(
        `mutation($id: String!) { deleteMarkersetTemplate(markersetId: $id) }`,
        { id: markersetId }
    );
}

/** Returns full normalised instance object */
export async function createMarkersetInstance(subjectId, input) {
    const data = await gql(
        `mutation($s: String!, $input: CreateMarkersetInstanceInput!) {
            createMarkersetInstance(subjectId: $s, input: $input) { ${MARKERSET_INSTANCE_FIELDS} }
        }`,
        { s: subjectId, input }
    );
    return mapMarkersetInstance(data.createMarkersetInstance);
}

/** Returns full normalised instance object */
export async function updateMarkersetInstance(instanceId, input) {
    const data = await gql(
        `mutation($id: String!, $input: CreateMarkersetInstanceInput!) {
            updateMarkersetInstance(instanceId: $id, input: $input) { ${MARKERSET_INSTANCE_FIELDS} }
        }`,
        { id: instanceId, input }
    );
    return mapMarkersetInstance(data.updateMarkersetInstance);
}

export async function deleteMarkersetInstance(instanceId) {
    await gql(
        `mutation($id: String!) { deleteMarkersetInstance(instanceId: $id) }`,
        { id: instanceId }
    );
}

// ── Analysis mutations ────────────────────────────────────────────────────────

/** Returns { job_id, status } */
export async function submitAnalysis(input) {
    const data = await gql(
        `mutation($input: AnalysisInput!) { submitAnalysis(input: $input) { jobId status } }`,
        { input }
    );
    return { job_id: data.submitAnalysis.jobId, status: data.submitAnalysis.status };
}

// ── Private helpers ───────────────────────────────────────────────────────────

function mapMarkersetTemplate(t) {
    return {
        markerset_id: t.markersetId,
        name:         t.name,
        description:  t.description ?? "",
        markers:      t.markers.map(normaliseMarkersetMarker),
        created_at:   t.createdAt,
    };
}

function mapMarkersetInstance(i) {
    return {
        instance_id:  i.instanceId,
        subject_id:   i.subjectId,
        markerset_id: i.markersetId ?? "",
        name:         i.name,
        markers:      i.markers.map(normaliseMarkersetMarker),
        created_at:   i.createdAt,
    };
}
