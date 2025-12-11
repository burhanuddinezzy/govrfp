import numpy as np
from sentence_transformers import SentenceTransformer

ASPECT_TEXTS = {
    "scope_of_work": [
        "Assemble [COMPONENT] according to the provided specifications. Verify all dimensions and operational tolerances. Conduct functional testing and record any deviations. Submit documentation for approval before proceeding to integration.",
        "Execute [PROCESS] for [WORKSTREAM], completing preparation, implementation, and verification stages. Document steps, resources used, and time spent. Produce a report summarizing results, deviations, and recommended corrective actions.",
        "Develop [SOFTWARE MODULE] including configuration, testing, and integration with [PLATFORM]. Conduct multiple scenario tests to ensure reliability. Prepare user documentation and provide training sessions for [TEAM]. Collect feedback and update deliverables accordingly.",
        "Perform [RESEARCH/STUDY] on [TOPIC], starting with data collection from designated sources. Analyze data, validate findings against objectives, and summarize results. Present insights in a structured report with charts, tables, and actionable recommendations.",
        "Install [DEVICE/SYSTEM] at [LOCATION], following technical drawings. Verify calibration, operational parameters, and system safety. Document installation process and report any anomalies to stakeholders.",
        "Conduct quality assurance on [PRODUCT/DELIVERABLE], performing inspections at each milestone. Record compliance with specifications, highlight issues, and propose mitigation steps. Submit comprehensive inspection reports.",
        "Prepare and execute [OPERATIONAL TASKS], including coordination of [RESOURCES] and monitoring of [ACTIVITIES]. Document progress and deviations. Provide interim reports and update project documentation accordingly.",
        "Fabricate [COMPONENT/STRUCTURE] following detailed instructions. Perform assembly, verification, and operational testing. Document all measurements, tolerances, and functional checks. Submit completed work for review and approval.",
        "Manage configuration and deployment of [PLATFORM/SYSTEM] across multiple environments. Perform integration testing and validate system behavior. Train staff on new features and ensure documentation is up to date.",
        "Conduct training and knowledge transfer for [TEAM/USER GROUP] on [SYSTEM/PROCESS]. Provide practical exercises, assessments, and feedback. Ensure users are capable of independently operating and maintaining the system.",
        "Monitor [SYSTEM/PROCESS] over [TIMEFRAME], logging performance, anomalies, and interventions. Analyze trends, produce summary reports, and recommend adjustments to optimize outcomes.",
        "Deliver [SERVICE/OUTPUT] with all required subcomponents. Perform comprehensive testing, document results, and submit final deliverables for stakeholder review. Incorporate feedback into final revisions.",
        "Update [CONFIGURATION/SETTINGS] for [SYSTEM/PLATFORM]. Test changes in controlled scenarios, verify backward compatibility, and document results. Communicate updates to relevant teams.",
        "Execute operational tests on [EQUIPMENT/SOFTWARE] to verify [FUNCTIONAL REQUIREMENT]. Record deviations, implement corrective measures, and produce a validation report for review.",
        "Collect and analyze [METRICS/DATA] from [PROCESS/ACTIVITY]. Identify trends, anomalies, and actionable insights. Compile findings into a detailed report with visualizations and recommendations.",
        "Assemble, package, and deliver [PRODUCT/COMPONENTS] to [LOCATION]. Verify completeness and quality of all items. Document delivery, including condition upon receipt, and provide tracking to stakeholders.",
        "Perform [MAINTENANCE/UPGRADE] tasks on [SYSTEM/INFRASTRUCTURE]. Log procedures, document changes, and validate operational readiness. Report findings and follow-up actions required.",
        "Validate [OUTPUT/DELIVERABLE] against acceptance criteria. Conduct functional tests, document discrepancies, and implement corrective measures. Submit final validation report for approval.",
        "Coordinate execution of [MULTI-STEP TASK] across [TEAM/UNIT]. Ensure timely completion of each phase, track progress, and resolve bottlenecks. Document all activities and submit consolidated status reports."
    ],
    "timeline": [
        "The project shall commence on [START_DATE] and reach completion by [END_DATE]. Key milestones include [MILESTONE_1], [MILESTONE_2], and [MILESTONE_3]. Progress against each milestone shall be documented and submitted in weekly status reports.",
        "Deliverables shall be submitted according to the following schedule: [DELIVERABLE_1] by [DATE_1], [DELIVERABLE_2] by [DATE_2], and [DELIVERABLE_3] by [DATE_3]. Any delays must be reported immediately with a proposed mitigation plan.",
        "The timeline for [PHASED_TASKS] shall follow sequential stages: initiation, execution, validation, and closure. Each phase shall include documentation of completed activities, verification of deliverables, and approval before proceeding to the next phase.",
        "All [TASKS/ACTIVITIES] must be completed in accordance with the predefined timeline. Resource allocation and task sequencing shall be documented, and adjustments must be communicated to stakeholders.",
        "The project plan shall include key deadlines for [SUBMISSIONS, REVIEWS, TESTS]. Each deadline shall be clearly communicated to all relevant teams, with status updates provided at weekly progress meetings.",
        "Implementation phases shall adhere to the following schedule: preparation, execution, quality verification, and final review. Milestone completion shall be recorded, with delays or deviations explained in accompanying reports.",
        "Critical activities, including [TASK_1], [TASK_2], and [TASK_3], shall be performed according to the established timeline. Progress tracking and reporting shall ensure transparency and accountability throughout the project.",
        "Delivery dates for [COMPONENTS/DELIVERABLES] shall follow the agreed-upon schedule. Each submission shall include supporting documentation indicating adherence to timeline and quality standards.",
        "Tasks related to [DEPLOYMENT/IMPLEMENTATION] shall occur according to the planned timeline, with resource allocation optimized to meet all deadlines. Status reports shall be provided weekly."
    ],
    "pricing": [
        "The total estimated cost of the project shall not exceed $[TOTAL_COST]. All pricing shall include labor, materials, and any applicable fees. Detailed cost breakdowns must be provided for each component of the work.",
        "Payments shall be made according to the following schedule: $[AMOUNT_1] upon completion of [MILESTONE_1], $[AMOUNT_2] upon completion of [MILESTONE_2], and $[AMOUNT_3] upon final acceptance of all deliverables.",
        "The budget allocated for this project is $[TOTAL_BUDGET]. Any expenses exceeding this amount must be pre-approved and justified.",
        "Estimated costs for each project phase shall be provided, including [PHASE_1_COST], [PHASE_2_COST], and [PHASE_3_COST]. These estimates shall reflect the anticipated expenditures for all resources and services.",
        "The client shall provide up to $[MAX_AMOUNT] for reimbursable expenses. Supporting documentation for all charges must accompany invoices for payment.",
        "Pricing shall be itemized for each deliverable, showing total cost, estimated labor, materials, and any applicable taxes. The total shall not exceed $[TOTAL_COST_LIMIT].",
        "Payments shall be contingent on satisfactory completion and acceptance of deliverables. Each invoice must reference the associated milestone and cost allocation.",
        "The proposed contract value shall not exceed $[CONTRACT_VALUE]. Any additional services requested by the client shall require a separate cost estimate and approval.",
        "The financial proposal shall include a breakdown of fixed costs, variable costs, and contingency amounts, with a total not exceeding $[TOTAL_PROJECT_COST].",
        "The client anticipates expenditures of $[AMOUNT] for [SERVICE/DELIVERABLE]. All payments shall be made in accordance with the agreed-upon schedule.",
        "Cost estimates shall include expected labor charges, materials, and overhead. Total project cost shall be capped at $[TOTAL_COST], with any deviations subject to approval.",
        "The budget for optional services shall not exceed $[OPTIONAL_COST]. Any usage of optional funds must be pre-approved by the client.",
        "Estimated project costs shall be broken down into categories: labor $[LABOR_COST], materials $[MATERIAL_COST], equipment $[EQUIPMENT_COST], and other expenses $[OTHER_COST].",
        "The client shall not be liable for expenses exceeding the approved total of $[TOTAL_APPROVED]. Any overages must be documented, justified, and pre-approved.",
        "Payment terms shall be net [NUMBER] days from receipt of an approved invoice. The client reserves the right to withhold payments for incomplete or unsatisfactory deliverables.",
        "A detailed cost schedule shall accompany the submission, showing amounts allocated to each project task, milestone, and deliverable. Total cost shall not exceed $[TOTAL_COST].",
        "All costs must be expressed in [CURRENCY], with itemized breakdowns for labor, materials, equipment, and any other applicable charges. Total payment to the contractor shall not exceed $[MAX_TOTAL].",
        "It is anticipated that the range in price of this contract will be between $[MINIMUM_COST]and $[MAXIMUM_COST] (or equivalent in local currency)."
        
    ]
}

MODEL_NAME = "all-MiniLM-L6-v2"
_model = SentenceTransformer(MODEL_NAME)

def save_aspect_vectors():
    names = []
    centroids = []

    for aspect_name, passages in ASPECT_TEXTS.items():
        # Encode all passages for this aspect
        emb = _model.encode(passages, normalize_embeddings=True)  # (n_passages, dim)

        # Compute centroid
        centroid = emb.mean(axis=0)

        # Normalize centroid
        centroid = centroid / np.linalg.norm(centroid)

        if aspect_name == "pricing":
            np.save("aspect_method/pricing_vector.npy", centroid)

        names.append(aspect_name)
        centroids.append(centroid)

    names = np.array(names)                     # (n_aspects,)
    vectors = np.stack(centroids, axis=0)       # (n_aspects, dim)

    np.savez(
        "aspect_method/aspect_vectors.npz",
        names=names,
        vectors=vectors
    )

if __name__ == "__main__":
    save_aspect_vectors()

