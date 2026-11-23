# Proposed changes

43 proposals. Tick Approved to add an item, or Maybe later to see it again in 90 days, then merge. Items with neither box ticked count as reviewed and are not proposed again.

## 1. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): facts.enrollment should be '326' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Registry enrolment is 326 (ACTUAL) ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **Screener:** Recommended: tick (0.85): registry correction to an existing entry
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'facts.enrollment', 'from': None, 'to': 326}`
- [ ] Approved
- [ ] Maybe later

## 2. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): facts.phase should be 'na' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Record has no phase; registry has one ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **Screener:** Recommended: tick (0.85): registry correction to an existing entry
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'facts.phase', 'from': None, 'to': 'na'}`
- [ ] Approved
- [ ] Maybe later

## 3. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): facts.primary_completion_date should be '2017-07-31' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Registry primary completion date is 2017-07-31 (ACTUAL) ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **Screener:** Recommended: tick (0.85): registry correction to an existing entry
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'facts.primary_completion_date', 'from': None, 'to': '2017-07-31'}`
- [ ] Approved
- [ ] Maybe later

## 4. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): status should be 'completed' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Record has no status; registry has one ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **Screener:** Recommended: tick (0.85): registry correction to an existing entry
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'status', 'from': None, 'to': 'completed'}`
- [ ] Approved
- [ ] Maybe later

## 5. Review new paper for relevant claims: Mindfulness-Based Interventions for Tinnitus Distress: A Systematic Review, Meta-Analysis, and Appraisal of Intervention Reporting

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** J Speech Lang Hear Res, first published 2026-11-16 ([source](https://doi.org/10.1044/2026_jslhr-26-00341))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** Recommended: tick (0.85): systematic review or meta-analysis
- **To apply:** `{'cite': 'doi:10.1044/2026_jslhr-26-00341'}`
- [ ] Approved
- [ ] Maybe later

## 6. Add trial NCT03511807: Acoustic and Electrical Stimulation for the Treatment of Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status active_not_recruiting, phase na, sponsor University of California, Irvine, last updated 2026-11-17 ([source](https://clinicaltrials.gov/study/NCT03511807))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Acoustic and Electrical Stimulation for the Treatment of Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT03511807'], 'status': 'active_not_recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 7. Add trial NCT05434637: Somatosensory Tinnitus RCT

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase na, sponsor VA Office of Research and Development, last updated 2026-11-18 ([source](https://clinicaltrials.gov/study/NCT05434637))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Somatosensory Tinnitus RCT', 'xrefs': ['CLINICALTRIALS:NCT05434637'], 'status': 'recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 8. Add trial NCT05650645: The Efficacy of Incobotulinum Toxin A Injections for Treatment of Tinnitus: a Randomized Controlled Trial

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase phase2, sponsor University of Minnesota, last updated 2026-10-27 ([source](https://clinicaltrials.gov/study/NCT05650645))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'The Efficacy of Incobotulinum Toxin A Injections for Treatment of Tinnitus: a Randomized Controlled Trial', 'xrefs': ['CLINICALTRIALS:NCT05650645'], 'status': 'completed'}}`
- [ ] Approved
- [ ] Maybe later

## 9. Add trial NCT05963542: Efficacy of Online Acceptance and Commitment Therapy and Sound Therapy for Patients With Tinnitus and Insomnia

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase na, sponsor Eye & ENT Hospital of Fudan University, last updated 2026-11-16 ([source](https://clinicaltrials.gov/study/NCT05963542))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Efficacy of Online Acceptance and Commitment Therapy and Sound Therapy for Patients With Tinnitus and Insomnia', 'xrefs': ['CLINICALTRIALS:NCT05963542'], 'status': 'completed'}}`
- [ ] Approved
- [ ] Maybe later

## 10. Add trial NCT06646302: Residual Inhibition of 40 Hz Burst Sound in Tinnitus Patients

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase na, sponsor Eye & ENT Hospital of Fudan University, last updated 2026-10-27 ([source](https://clinicaltrials.gov/study/NCT06646302))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Residual Inhibition of 40 Hz Burst Sound in Tinnitus Patients', 'xrefs': ['CLINICALTRIALS:NCT06646302'], 'status': 'completed'}}`
- [ ] Approved
- [ ] Maybe later

## 11. Add trial NCT07393880: Bimodal Electrical-Sound Stimulation and Auditory Training for Chronic Tonal Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase na, sponsor University of Dublin, Trinity College, last updated 2026-11-19 ([source](https://clinicaltrials.gov/study/NCT07393880))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Bimodal Electrical-Sound Stimulation and Auditory Training for Chronic Tonal Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07393880'], 'status': 'recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 12. Add trial NCT07777549: A Study of the Safety and Efficacy of TRTL-913 in Healthy Volunteers (Part A) and in Adults With Tinnitus (Part B)

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase phase2, sponsor Tortugas Neuroscience, Inc., last updated 2026-11-04 ([source](https://clinicaltrials.gov/study/NCT07777549))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'A Study of the Safety and Efficacy of TRTL-913 in Healthy Volunteers (Part A) and in Adults With Tinnitus (Part B)', 'xrefs': ['CLINICALTRIALS:NCT07777549'], 'status': 'recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 13. Add trial NCT07877701: Acute Nicotine Gum and Auditory Brain Responses in Adults With Chronic Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status not_yet_recruiting, phase phase1/phase2, sponsor San Diego State University, last updated 2026-11-06 ([source](https://clinicaltrials.gov/study/NCT07877701))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Acute Nicotine Gum and Auditory Brain Responses in Adults With Chronic Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07877701'], 'status': 'not_yet_recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 14. Add trial NCT07893860: Effect of a Totally Implantable Cochlear Implant on Tinnitus Severity in Adults With Preoperative Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status not_yet_recruiting, phase na, sponsor Cochlear, last updated 2026-11-10 ([source](https://clinicaltrials.gov/study/NCT07893860))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Effect of a Totally Implantable Cochlear Implant on Tinnitus Severity in Adults With Preoperative Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07893860'], 'status': 'not_yet_recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 15. Add trial NCT07895004: Comparing an AI-driven Hearing Test With the Standard Hearing Test in Adults With Hearing Loss and Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status enrolling_by_invitation, phase not given, sponsor University College, London, last updated 2026-10-26 ([source](https://clinicaltrials.gov/study/NCT07895004))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Comparing an AI-driven Hearing Test With the Standard Hearing Test in Adults With Hearing Loss and Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07895004'], 'status': 'enrolling_by_invitation'}}`
- [ ] Approved
- [ ] Maybe later

## 16. Add trial NCT07941648: Combined Treatments for Somatosensory Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase na, sponsor Universidade Federal de Santa Maria, last updated 2026-11-17 ([source](https://clinicaltrials.gov/study/NCT07941648))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: tick (0.75): registered trial, the condition is in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Combined Treatments for Somatosensory Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07941648'], 'status': 'recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 17. Review new paper for relevant claims: A state-of-the-art review of biosensor-based markers for tinnitus

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Hear Res, first published 2026-11-04 ([source](https://doi.org/10.1016/j.heares.2026.109847))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): review
- **To apply:** `{'cite': 'doi:10.1016/j.heares.2026.109847'}`
- [ ] Approved
- [ ] Maybe later

## 18. Review new paper for relevant claims: Bimodal versus unimodal high-definition Transcranial random noise stimulation of auditory cortex for tinnitus: A double-blind, sham-controlled crossover trial

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Brain Stimul, first published 2026-11-11 ([source](https://doi.org/10.1016/j.brs.2026.103251))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1016/j.brs.2026.103251'}`
- [ ] Approved
- [ ] Maybe later

## 19. Review new paper for relevant claims: Distinct Response Dynamics to Personalized Sound Therapy in Chronic Tinnitus: Sustained Clinical Benefits and a Critical Treatment Window

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Ear Hear, first published 2026-11-12 ([source](https://doi.org/10.1097/aud.0000000000001910))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1097/aud.0000000000001910'}`
- [ ] Approved
- [ ] Maybe later

## 20. Review new paper for relevant claims: Early Post-Market Surveillance of Bimodal Neuromodulation for Tinnitus

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Otolaryngol Head Neck Surg, first published 2026-11-06 ([source](https://doi.org/10.1002/ohn.70513))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1002/ohn.70513'}`
- [ ] Approved
- [ ] Maybe later

## 21. Review new paper for relevant claims: Harmonizing resting-state functional MRI data to increase sample size and to classify tinnitus brain connectivity

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-11-20 ([source](https://doi.org/10.64898/2026.11.19.767894))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.64898/2026.11.19.767894'}`
- [ ] Approved
- [ ] Maybe later

## 22. Review new paper for relevant claims: Hearing Loss, Not Tinnitus, Predicts Cognitive Performance in Hispanic/Latino Adults

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Am J Audiol, first published 2026-11-06 ([source](https://doi.org/10.1044/2026_aja-26-00098))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1044/2026_aja-26-00098'}`
- [ ] Approved
- [ ] Maybe later

## 23. Review new paper for relevant claims: Impaired cortical gap-mediated inhibition in chronic tinnitus but with limited individual diagnostic accuracy

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-11-13 ([source](https://doi.org/10.64898/2026.11.11.26367707))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.64898/2026.11.11.26367707'}`
- [ ] Approved
- [ ] Maybe later

## 24. Review new paper for relevant claims: Is routine serum TSH testing useful in the evaluation of primary subjective tinnitus? A case-control study

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Front Neurol, first published 2026-10-26 ([source](https://doi.org/10.3389/fneur.2026.1973811))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.3389/fneur.2026.1973811'}`
- [ ] Approved
- [ ] Maybe later

## 25. Review new paper for relevant claims: Neuromodulatory effects of audio-proprio-phonatory reinforcement training on subjective tinnitus, a HD-EEG study protocol

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** PLoS One, first published 2026-11-06 ([source](https://doi.org/10.1371/journal.pone.0357455))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1371/journal.pone.0357455'}`
- [ ] Approved
- [ ] Maybe later

## 26. Review new paper for relevant claims: Otological manifestations of disseminated metastatic breast cancer presenting with facial nerve palsy, tinnitus and otalgia

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** BMJ Case Rep, first published 2026-11-12 ([source](https://doi.org/10.1136/bcr-2026-273676))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1136/bcr-2026-273676'}`
- [ ] Approved
- [ ] Maybe later

## 27. Review new paper for relevant claims: Post-trauma acoustic environment and tinnitus susceptibility: Evidence for acoustic enrichment as a treatment strategy

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Hear Res, first published 2026-11-04 ([source](https://doi.org/10.1016/j.heares.2026.109859))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1016/j.heares.2026.109859'}`
- [ ] Approved
- [ ] Maybe later

## 28. Review new paper for relevant claims: Pulsatile Tinnitus Alleviated by Contralateral Stent Implantation

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Stroke, first published 2026-10-26 ([source](https://doi.org/10.1161/strokeaha.126.056600))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1161/strokeaha.126.056600'}`
- [ ] Approved
- [ ] Maybe later

## 29. Review new paper for relevant claims: Pulsatile Tinnitus, Dizziness, and Venous Outflow Physiology: A Retrospective Cohort with Nested Vestibular Phenotyping and a Proposed Otology-Led Diagnostic Pathway

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-11-09 ([source](https://doi.org/10.20944/preprints202611.0914.v1))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.20944/preprints202611.0914.v1'}`
- [ ] Approved
- [ ] Maybe later

## 30. Review new paper for relevant claims: Restoring the future: Integrating hope theory into the assessment and management of tinnitus distress

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** J Health Psychol, first published 2026-11-10 ([source](https://doi.org/10.1177/13591053261502553))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1177/13591053261502553'}`
- [ ] Approved
- [ ] Maybe later

## 31. Review new paper for relevant claims: Sleep disturbance and anxiety in female garment workers with tinnitus: An ENT outpatient study

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Am J Otolaryngol, first published 2026-11-09 ([source](https://doi.org/10.1016/j.amjoto.2026.104979))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1016/j.amjoto.2026.104979'}`
- [ ] Approved
- [ ] Maybe later

## 32. Review new paper for relevant claims: Sound-evoked facial movement and tinnitus distress: an exploratory secondary analysis. 

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Eur Arch Otorhinolaryngol, first published 2026-11-21 ([source](https://doi.org/10.1007/s00405-026-10848-y))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1007/s00405-026-10848-y'}`
- [ ] Approved
- [ ] Maybe later

## 33. Review new paper for relevant claims: The Three Levels of Tinnitus Chronification

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-11-10 ([source](https://doi.org/10.20944/preprints202611.1025.v1))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.20944/preprints202611.1025.v1'}`
- [ ] Approved
- [ ] Maybe later

## 34. Review new paper for relevant claims: The Tinnitus Integrated Digital Ecosystem Model for Digital Tinnitus Rehabilitation: A Clinical Framework

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Am J Audiol, first published 2026-11-12 ([source](https://doi.org/10.1044/2026_aja-26-00156))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.1044/2026_aja-26-00156'}`
- [ ] Approved
- [ ] Maybe later

## 35. Review new paper for relevant claims: Tinnitus Activities Treatment Update: Managing Attention and Auditory Attention

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-11-10 ([source](https://doi.org/10.20944/preprints202611.0967.v1))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.20944/preprints202611.0967.v1'}`
- [ ] Approved
- [ ] Maybe later

## 36. Review new paper for relevant claims: [Orofacial pain and somatosensory tinnitus: a biomechanical traction approach]

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Ned Tijdschr Tandheelkd, first published 2026-11-01 ([source](https://doi.org/10.5177/ntvt.2026.11.25029))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** On the fence: consider Maybe later (0.55): study in people
- **To apply:** `{'cite': 'doi:10.5177/ntvt.2026.11.25029'}`
- [ ] Approved
- [ ] Maybe later

## 37. Add trial NCT06799169: Management of Acute Tinnitus With Migraine Medications

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status suspended, phase phase4, sponsor University of California, Irvine, last updated 2026-10-27 ([source](https://clinicaltrials.gov/study/NCT06799169))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** On the fence: consider Maybe later (0.50): registered trial, the condition is in the title, status suspended
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Management of Acute Tinnitus With Migraine Medications', 'xrefs': ['CLINICALTRIALS:NCT06799169'], 'status': 'suspended'}}`
- [ ] Approved
- [ ] Maybe later

## 38. Add trial NCT05618002: Lemborexant vs Clonidine vs Sedatives to Treat Insomnia in Chronic Pain Patients

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase not given, sponsor Salem Anaesthesia Pain Clinic, last updated 2026-11-02 ([source](https://clinicaltrials.gov/study/NCT05618002))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: skip (0.35): registered trial, the condition is not in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Lemborexant vs Clonidine vs Sedatives to Treat Insomnia in Chronic Pain Patients', 'xrefs': ['CLINICALTRIALS:NCT05618002'], 'status': 'recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 39. Add trial NCT07950033: A Study to Evaluate the Effects of the EMF Harmony Products on Health Parameters Associated With EMF Radiation Exposure

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status active_not_recruiting, phase na, sponsor Life Harmony Energies, Inc., last updated 2026-11-20 ([source](https://clinicaltrials.gov/study/NCT07950033))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: skip (0.35): registered trial, the condition is not in the title
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'A Study to Evaluate the Effects of the EMF Harmony Products on Health Parameters Associated With EMF Radiation Exposure', 'xrefs': ['CLINICALTRIALS:NCT07950033'], 'status': 'active_not_recruiting'}}`
- [ ] Approved
- [ ] Maybe later

## 40. Review new paper for relevant claims: Enhanced auditory gain and tinnitus-like behavior in mice lacking KCTD12, an auxiliary subunit of GABA&lt;sub&gt;B&lt;/sub&gt; receptors

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Neurobiol Dis, first published 2026-10-27 ([source](https://doi.org/10.1016/j.nbd.2026.107664))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** Recommended: skip (0.20): animal or laboratory study
- **To apply:** `{'cite': 'doi:10.1016/j.nbd.2026.107664'}`
- [ ] Approved
- [ ] Maybe later

## 41. Review new paper for relevant claims: Establishment of an animal model of GPIAS-defined tinnitus-like behavior with normal auditory brainstem response threshold profiles

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Neuroscience, first published 2026-10-28 ([source](https://doi.org/10.1016/j.neuroscience.2026.10.043))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** Recommended: skip (0.20): animal or laboratory study
- **To apply:** `{'cite': 'doi:10.1016/j.neuroscience.2026.10.043'}`
- [ ] Approved
- [ ] Maybe later

## 42. Review new paper for relevant claims: Mitragynine reduces symptoms of alcohol use disorder (and tinnitus) in a self-medication of rodents

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-11-19 ([source](https://doi.org/10.64898/2026.11.19.767795))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **Screener:** Recommended: skip (0.20): animal or laboratory study
- **To apply:** `{'cite': 'doi:10.64898/2026.11.19.767795'}`
- [ ] Approved
- [ ] Maybe later

## 43. Add trial NCT04172766: Apple Hearing Study

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status terminated, phase not given, sponsor Apple Inc., last updated 2026-11-16 ([source](https://clinicaltrials.gov/study/NCT04172766))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **Screener:** Recommended: skip (0.10): registered trial, the condition is not in the title, status terminated
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Apple Hearing Study', 'xrefs': ['CLINICALTRIALS:NCT04172766'], 'status': 'terminated'}}`
- [ ] Approved
- [ ] Maybe later
