import os
import json
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger(__name__)

CLINICAL_GUIDELINES_DATA = [
    {
        "title": "Acute Chest Pain and Coronary Syndrome Care",
        "source_citation": "ACC/AHA Guideline for Chest Pain Assessment",
        "content": (
            "Patients presenting with acute chest pain, pressure, tightness, or squeezing, especially "
            "when radiating to the left arm, shoulder, back, neck, or jaw, and accompanied by shortness of breath "
            "or diaphoresis (sweating), require immediate emergency clinical evaluation for acute coronary syndrome. "
            "Safe over-the-counter medication does not apply for cardiac emergencies. Advise the patient to remain "
            "at absolute rest and call emergency clinical SOS services immediately."
        )
    },
    {
        "title": "Dermatitis and Skin Rash Management",
        "source_citation": "AAD Clinical Guideline for Contact Dermatitis",
        "content": (
            "For mild contact dermatitis, localized eczema, dry skin itching (pruritus), or mild allergic skin rashes: "
            "Avoid scratching the affected area to prevent secondary infection. Apply over-the-counter (OTC) soothing "
            "topical emollients, Calamine lotion, or mild 1% hydrocortisone cream topically twice daily. For severe itching, "
            "oral over-the-counter antihistamines (such as Cetirizine 10mg daily or Loratadine 10mg daily) may be used "
            "short-term. Consult a dermatologist if lesions scale, weep, spread, or fail to resolve."
        )
    },
    {
        "title": "Acute Viral Pharyngitis Care",
        "source_citation": "IDSA Clinical Practice Guideline for Sore Throat",
        "content": (
            "Acute pharyngitis (sore throat) is overwhelmingly viral in origin. Recommended symptomatic therapies "
            "include warm saline gargles (1/2 teaspoon of salt in warm water) multiple times daily, maintaining "
            "generous fluid hydration, and utilizing over-the-counter (OTC) throat lozenges containing benzocaine "
            "or menthol for temporary topical numbing. For pain and fever relief, suggest Paracetamol (Acetaminophen) "
            "500mg every 6 hours as needed (do not exceed 3000mg/day) or Ibuprofen 400mg every 6-8 hours with food."
        )
    },
    {
        "title": "Pediatric Fever Comfort Management",
        "source_citation": "AAP Guideline for Fever and Antipyretic Use in Children",
        "content": (
            "Fever is a natural physiological defense. For mild pediatric fever (under 102F or 38.9C) where the child "
            "remains active and hydrated, focus on comfort rather than normalizing temperature. If antipyretics are "
            "indicated for distress, suggest pediatric Paracetamol (Acetaminophen) suspension (10-15 mg/kg per dose "
            "every 4-6 hours, max 5 doses daily) or pediatric Ibuprofen suspension (5-10 mg/kg per dose every 6-8 hours "
            "with food). NEVER administer Aspirin to children due to the fatal risk of Reye's Syndrome."
        )
    },
    {
        "title": "Acute Migraine and Tension Headache Care",
        "source_citation": "AHS Guideline for Acute Treatment of Tension Headache",
        "content": (
            "For mild tension headaches or early-onset migraines, advise rest in a quiet, dark room. Apply a cold "
            "compress to the forehead or temples. Recommended over-the-counter (OTC) medicines include Paracetamol "
            "(Acetaminophen) 500-1000mg or Ibuprofen 400mg. For migraine, a combination OTC pain reliever containing "
            "paracetamol, aspirin, and caffeine may be used. Limit use of OTC analgesics to 2-3 days per week to prevent "
            "medication overuse headaches."
        )
    }
]

def seed_clinical_guidelines(db: Session):
    try:
        # Check if guidelines are already seeded
        existing_count = db.query(models.ClinicalGuideline).count()
        if existing_count > 0:
            logger.info("Clinical guidelines already seeded. Skipping.")
            return

        logger.info("Seeding clinical guidelines...")
        
        # We write dummy vectors by default so that database creation is 100% offline-compatible.
        # RAG retrieval falls back on keyword search seamlessly when actual embeddings aren't generated.
        dummy_vector = [0.0] * 384  # Standard dimensions matching all-MiniLM-L6-v2
        dummy_vector_json = json.dumps(dummy_vector)
        
        for g in CLINICAL_GUIDELINES_DATA:
            new_guideline = models.ClinicalGuideline(
                title=g["title"],
                source_citation=g["source_citation"],
                content=g["content"],
                embedding_json=dummy_vector_json
            )
            db.add(new_guideline)
            
        db.commit()
        logger.info("Successfully seeded clinical guidelines.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to seed clinical guidelines: {e}")
