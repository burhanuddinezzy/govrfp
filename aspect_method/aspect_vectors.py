import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

ASPECT_TEXTS = {
    "scope_of_work": (
        "This text describes the work that must be performed, including specific "
        "tasks, services, operational responsibilities, deliverables, and activities "
        "the vendor is expected to carry out as part of the project."
    ),
    "vendor_requirements": (
        "This text defines the experience, certifications, technical capabilities, "
        "staffing qualifications, and eligibility criteria a vendor must meet in order "
        "to be considered for this project."
    ),
    "timeline_schedule": (
        "This text outlines project timelines, schedules, milestones, important dates, "
        "deadlines, and time-based expectations related to project execution."
    ),
    "budget_pricing": (
        "This text describes project budget information, financial constraints, "
        "estimated costs, funding limits, payment structure, or pricing expectations for "
        "the work being requested."
    ),
    "evaluation_criteria": (
        "This text explains how proposals will be evaluated, including scoring criteria, "
        "selection methodology, performance weighting, and factors used to determine "
        "the winning vendor."
    ),
    "submission_instructions": (
        "This text provides instructions for preparing and submitting a proposal, "
        "including formatting rules, required documentation, submission method, and "
        "administrative procedures."
    )
}

_model = SentenceTransformer(MODEL_NAME)

def save_aspect_vectors():
    names = list(ASPECT_TEXTS.keys())
    texts = list(ASPECT_TEXTS.values())

    embeddings = _model.encode(texts, normalize_embeddings=True)

    np.savez(
        "aspect_vectors.npz",
        names=np.array(names),
        vectors=embeddings
    )

if __name__ == "__main__":
    save_aspect_vectors()
