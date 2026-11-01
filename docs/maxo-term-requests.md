# MAXO new term requests (ready to post)

Two tinnitus interventions have no exact term in the Medical Action Ontology (MAXO). Checked against the MAXO repository (release committed 11 October 2026). MAXO has no issue template, so each request below is formatted as a standard OBO new-term request.

How to post: open https://github.com/monarch-initiative/MAxO/issues, click **New issue**, paste the title into the title box and everything under "Body" into the description, then click **Submit new issue**. Add your ORCID on the "Requested by" line if you have one.

When a term is accepted, add its MAXO identifier to the record's `xrefs` in `records/tinnitus.records.json` and delete that record's `closeMatches` entry. The record then joins the shareable Biolink graph on the next nightly run.

---

## Issue 1

**Title:** New term request: sound therapy (for tinnitus)

**Body:**

```
**Preferred term label:** sound therapy

**Synonyms:** acoustic therapy (RELATED); sound-based therapy (EXACT)

**Definition:** A therapy that uses an amplification device, a sound generator, or both, to reduce the perception of, or distress caused by, tinnitus or related auditory symptoms.

**Parent term:** MAXO:0001422 therapeutic procedure of vestibulo-auditory system

**Related existing terms:** MAXO:0009030 hearing aid usage covers amplification only; it does not cover sound generators or combination devices, which are the main subject of the Cochrane review cited below.

**References:**
- Sereda M, Xia J, El Refaie A, Hall DA, Hoare DJ. Sound therapy (using amplification devices or sound generators) for tinnitus. Cochrane Database of Systematic Reviews 2018, Issue 12. doi:10.1002/14651858.CD013094.pub2

**Use case:** Annotating tinnitus treatments in an open, Biolink-compliant knowledge graph, so the intervention can be linked to the condition (HP:0000360) with a standard identifier.

**Requested by:**
```

---

## Issue 2

**Title:** New term request: bimodal neuromodulation (for tinnitus)

**Body:**

```
**Preferred term label:** bimodal neuromodulation

**Synonyms:** bimodal stimulation (EXACT); bi-modal neuromodulation (EXACT)

**Definition:** A stimulation procedure that pairs auditory stimulation with electrical stimulation of a second sensory pathway, such as the tongue, to alter neural activity in the auditory system.

**Parent term:** MAXO:0000939 stimulation procedure

**Related existing terms:** MAXO:0000939 stimulation procedure is too broad to distinguish this intervention from other stimulation procedures.

**References:**
- Conlon B, et al. Bimodal neuromodulation combining sound and tongue stimulation reduces tinnitus symptoms in a large randomized clinical study. Science Translational Medicine 2020;12(564):eabb2830. doi:10.1126/scitranslmed.abb2830
- US FDA final order classifying the combined acoustic and electrical external stimulation device for the relief of tinnitus (21 CFR 874.3410). Federal Register, Docket FDA-2026-N-6010.

**Use case:** Annotating tinnitus treatments in an open, Biolink-compliant knowledge graph.

**Requested by:**
```
