# Proposed changes

38 proposals. Approve by merging; reject by deleting the line.

## 1. Add device K260413: Levo Gen 2 Tinnitus Therapy System (Levo Medical Corporation)

- **Why it surfaced:** An FDA device decision under a tinnitus-related product code is not in the knowledge graph yet
- **Evidence:** FDA decision 'Substantially Equivalent' on 2026-08-13, product code KLW ([source](https://api.fda.gov/device/510k.json?search=k_number%3AK260413))
- **Wrong if:** the device only lists tinnitus among many uses, or the record duplicates an existing device under another name
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'device', 'name': 'Levo Gen 2 Tinnitus Therapy System', 'key': 'K260413', 'key_fact': 'fda_submission_number', 'link_predicate': 'related_to', 'facts': {'fda_submission_number': {'value': 'K260413', 'source': 'https://api.fda.gov/device/510k.json?search=k_number%3AK260413'}, 'fda_decision': {'value': 'Substantially Equivalent', 'source': 'https://api.fda.gov/device/510k.json?search=k_number%3AK260413'}, 'fda_decision_date': {'value': '2026-08-13', 'source': 'https://api.fda.gov/device/510k.json?search=k_number%3AK260413'}, 'fda_product_code': {'value': 'KLW', 'source': 'https://api.fda.gov/device/510k.json?search=k_number%3AK260413'}}}}`
- [ ] Approved

## 2. Add trial NCT04066348: TNF-α Treatment of Blast-Induced Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status active_not_recruiting, phase phase2, sponsor Wayne State University, last updated 2026-10-20 ([source](https://clinicaltrials.gov/study/NCT04066348))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'TNF-α Treatment of Blast-Induced Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT04066348'], 'status': 'active_not_recruiting'}}`
- [ ] Approved

## 3. Add trial NCT04172766: Apple Hearing Study

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status terminated, phase not given, sponsor Apple Inc., last updated 2026-11-02 ([source](https://clinicaltrials.gov/study/NCT04172766))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Apple Hearing Study', 'xrefs': ['CLINICALTRIALS:NCT04172766'], 'status': 'terminated'}}`
- [ ] Approved

## 4. Add trial NCT05618002: Lemborexant vs Clonidine vs Sedatives to Treat Insomnia in Chronic Pain Patients

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase not given, sponsor Salem Anaesthesia Pain Clinic, last updated 2026-11-02 ([source](https://clinicaltrials.gov/study/NCT05618002))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Lemborexant vs Clonidine vs Sedatives to Treat Insomnia in Chronic Pain Patients', 'xrefs': ['CLINICALTRIALS:NCT05618002'], 'status': 'recruiting'}}`
- [ ] Approved

## 5. Add trial NCT05650645: The Efficacy of Incobotulinum Toxin A Injections for Treatment of Tinnitus: a Randomized Controlled Trial

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase phase2, sponsor University of Minnesota, last updated 2026-10-27 ([source](https://clinicaltrials.gov/study/NCT05650645))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'The Efficacy of Incobotulinum Toxin A Injections for Treatment of Tinnitus: a Randomized Controlled Trial', 'xrefs': ['CLINICALTRIALS:NCT05650645'], 'status': 'completed'}}`
- [ ] Approved

## 6. Add trial NCT06646302: Residual Inhibition of 40 Hz Burst Sound in Tinnitus Patients

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase na, sponsor Eye & ENT Hospital of Fudan University, last updated 2026-10-27 ([source](https://clinicaltrials.gov/study/NCT06646302))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Residual Inhibition of 40 Hz Burst Sound in Tinnitus Patients', 'xrefs': ['CLINICALTRIALS:NCT06646302'], 'status': 'completed'}}`
- [ ] Approved

## 7. Add trial NCT06799169: Management of Acute Tinnitus With Migraine Medications

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status suspended, phase phase4, sponsor University of California, Irvine, last updated 2026-10-27 ([source](https://clinicaltrials.gov/study/NCT06799169))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Management of Acute Tinnitus With Migraine Medications', 'xrefs': ['CLINICALTRIALS:NCT06799169'], 'status': 'suspended'}}`
- [ ] Approved

## 8. Add trial NCT07211711: Treatment of Temporomandibular Joint Disorders With a Stabilizing Occlusal Splint in Somatosensory Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase na, sponsor University of Sao Paulo General Hospital, last updated 2026-10-22 ([source](https://clinicaltrials.gov/study/NCT07211711))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Treatment of Temporomandibular Joint Disorders With a Stabilizing Occlusal Splint in Somatosensory Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07211711'], 'status': 'completed'}}`
- [ ] Approved

## 9. Add trial NCT07772089: Acute Nicotine Gum and Tinnitus Loudness in Non-Smoking Adults

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase phase1/phase2, sponsor San Diego State University, last updated 2026-10-16 ([source](https://clinicaltrials.gov/study/NCT07772089))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Acute Nicotine Gum and Tinnitus Loudness in Non-Smoking Adults', 'xrefs': ['CLINICALTRIALS:NCT07772089'], 'status': 'completed'}}`
- [ ] Approved

## 10. Add trial NCT07777549: A Study of the Safety and Efficacy of TRTL-913 in Healthy Volunteers (Part A) and in Adults With Tinnitus (Part B)

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase phase2, sponsor Tortugas Neuroscience, Inc., last updated 2026-11-04 ([source](https://clinicaltrials.gov/study/NCT07777549))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'A Study of the Safety and Efficacy of TRTL-913 in Healthy Volunteers (Part A) and in Adults With Tinnitus (Part B)', 'xrefs': ['CLINICALTRIALS:NCT07777549'], 'status': 'recruiting'}}`
- [ ] Approved

## 11. Add trial NCT07877701: Acute Nicotine Gum and Auditory Brain Responses in Adults With Chronic Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status not_yet_recruiting, phase phase1/phase2, sponsor San Diego State University, last updated 2026-11-06 ([source](https://clinicaltrials.gov/study/NCT07877701))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Acute Nicotine Gum and Auditory Brain Responses in Adults With Chronic Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07877701'], 'status': 'not_yet_recruiting'}}`
- [ ] Approved

## 12. Add trial NCT07885176: Deep Repetitive Transcranial Magnetic Stimulation in the Treatment of Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status recruiting, phase na, sponsor University of Regensburg, last updated 2026-10-21 ([source](https://clinicaltrials.gov/study/NCT07885176))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Deep Repetitive Transcranial Magnetic Stimulation in the Treatment of Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07885176'], 'status': 'recruiting'}}`
- [ ] Approved

## 13. Add trial NCT07887932: Multidimensional Phenotyping of Patients With Tinnitus Using Electronic Health Records and a Specialty Database

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status completed, phase not given, sponsor Eye & ENT Hospital of Fudan University, last updated 2026-10-22 ([source](https://clinicaltrials.gov/study/NCT07887932))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Multidimensional Phenotyping of Patients With Tinnitus Using Electronic Health Records and a Specialty Database', 'xrefs': ['CLINICALTRIALS:NCT07887932'], 'status': 'completed'}}`
- [ ] Approved

## 14. Add trial NCT07893860: Effect of a Totally Implantable Cochlear Implant on Tinnitus Severity in Adults With Preoperative Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status not_yet_recruiting, phase na, sponsor Cochlear, last updated 2026-10-26 ([source](https://clinicaltrials.gov/study/NCT07893860))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Effect of a Totally Implantable Cochlear Implant on Tinnitus Severity in Adults With Preoperative Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07893860'], 'status': 'not_yet_recruiting'}}`
- [ ] Approved

## 15. Add trial NCT07895004: Comparing an AI-driven Hearing Test With the Standard Hearing Test in Adults With Hearing Loss and Tinnitus

- **Why it surfaced:** A registered study for this condition is not in the knowledge graph yet
- **Evidence:** Status enrolling_by_invitation, phase not given, sponsor University College, London, last updated 2026-10-26 ([source](https://clinicaltrials.gov/study/NCT07895004))
- **Wrong if:** the study is only loosely related to the condition (for example it lists it as one of many)
- **Confidence:** medium
- **To apply:** `{'new_record': {'kind': 'trial', 'name': 'Comparing an AI-driven Hearing Test With the Standard Hearing Test in Adults With Hearing Loss and Tinnitus', 'xrefs': ['CLINICALTRIALS:NCT07895004'], 'status': 'enrolling_by_invitation'}}`
- [ ] Approved

## 16. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): facts.enrollment should be '326' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Registry enrolment is 326 (ACTUAL) ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'facts.enrollment', 'from': None, 'to': 326}`
- [ ] Approved

## 17. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): facts.phase should be 'na' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Record has no phase; registry has one ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'facts.phase', 'from': None, 'to': 'na'}`
- [ ] Approved

## 18. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): facts.primary_completion_date should be '2017-07-31' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Registry primary completion date is 2017-07-31 (ACTUAL) ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'facts.primary_completion_date', 'from': None, 'to': '2017-07-31'}`
- [ ] Approved

## 19. Treatment Evaluation of Neuromodulation for Tinnitus (TENT-A): status should be 'completed' (currently 'None')

- **Why it surfaced:** The nightly fact-check found the registry disagrees with the record
- **Evidence:** Record has no status; registry has one ([source](https://clinicaltrials.gov/study/NCT02669069))
- **Wrong if:** the registry entry is outdated or the record intentionally uses a different, sourced value
- **Confidence:** medium
- **To apply:** `{'record': 'tin:trial-tent-a', 'field': 'status', 'from': None, 'to': 'completed'}`
- [ ] Approved

## 20. Review new paper for relevant claims: A dual behavioral and electrophysiological evaluation of the sodium salicylate induced tinnitus model in rats: Comparing click and chirp stimuli in auditory brainstem responses

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Behav Brain Res, first published 2026-10-11 ([source](https://doi.org/10.1016/j.bbr.2026.116529))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1016/j.bbr.2026.116529'}`
- [ ] Approved

## 21. Review new paper for relevant claims: Clinical practice guidance for imaging selection in pulsatile tinnitus: an evidence-based expert consensus

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Eur J Radiol, first published 2026-10-09 ([source](https://doi.org/10.1016/j.ejrad.2026.113299))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1016/j.ejrad.2026.113299'}`
- [ ] Approved

## 22. Review new paper for relevant claims: Editorial: Tinnitus in relation to auditory processing: unravelling complex relationships

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Front Neurosci, first published 2026-10-19 ([source](https://doi.org/10.3389/fnins.2026.1814945))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.3389/fnins.2026.1814945'}`
- [ ] Approved

## 23. Review new paper for relevant claims: Effect of the vagus nerve stimulation combined with sound therapy for tinnitus treatment: a systematic review and meta-analysis

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Eur Arch Otorhinolaryngol, first published 2026-10-13 ([source](https://doi.org/10.1007/s00405-026-10713-y))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1007/s00405-026-10713-y'}`
- [ ] Approved

## 24. Review new paper for relevant claims: Embolization of jugular bulb diverticula in the management of pulsatile tinnitus

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Front Neurol, first published 2026-10-08 ([source](https://doi.org/10.3389/fneur.2026.1951324))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.3389/fneur.2026.1951324'}`
- [ ] Approved

## 25. Review new paper for relevant claims: Enhanced auditory gain and tinnitus-like behavior in mice lacking KCTD12, an auxiliary subunit of GABA&lt;sub&gt;B&lt;/sub&gt; receptors

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Neurobiol Dis, first published 2026-10-27 ([source](https://doi.org/10.1016/j.nbd.2026.107664))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1016/j.nbd.2026.107664'}`
- [ ] Approved

## 26. Review new paper for relevant claims: Establishment of an animal model of GPIAS-defined tinnitus-like behavior with normal auditory brainstem response threshold profiles

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Neuroscience, first published 2026-10-28 ([source](https://doi.org/10.1016/j.neuroscience.2026.10.043))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1016/j.neuroscience.2026.10.043'}`
- [ ] Approved

## 27. Review new paper for relevant claims: Eustachian Tube Dysfunction and Tinnitus: A Rapid Review of the Potential Complementary Role of Acoustic Immittance

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** J Int Adv Otol, first published 2026-10-23 ([source](https://doi.org/10.65717/iao.2026.262472))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.65717/iao.2026.262472'}`
- [ ] Approved

## 28. Review new paper for relevant claims: Everolimus for Tinnitus: A Questionable Causal Chain [Letter]

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Drug Des Devel Ther, first published 2026-10-16 ([source](https://doi.org/10.2147/dddt.s659416))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.2147/dddt.s659416'}`
- [ ] Approved

## 29. Review new paper for relevant claims: Exploring tinnitus-like central hyperactivity in a large language model-based computational analog of hearing loss

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Hear Res, first published 2026-10-23 ([source](https://doi.org/10.1016/j.heares.2026.109845))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1016/j.heares.2026.109845'}`
- [ ] Approved

## 30. Review new paper for relevant claims: Learning Perspectives in the Management of Sigmoid Sinus Diverticulum in the Absence of Pulsatile Tinnitus

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Ear Nose Throat J, first published 2026-10-09 ([source](https://doi.org/10.1177/01455613261480423))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1177/01455613261480423'}`
- [ ] Approved

## 31. Review new paper for relevant claims: Multidomain Auditory Differences in Tinnitus With a Clinically Normal Audiogram: Accounting for Extended High-Frequency Hearing

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** J Speech Lang Hear Res, first published 2026-10-12 ([source](https://doi.org/10.1044/2026_jslhr-26-00071))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1044/2026_jslhr-26-00071'}`
- [ ] Approved

## 32. Review new paper for relevant claims: Objective markers of altered neural gain dissociate tinnitus and self-reported listening problems in individuals with exceptional hearing thresholds

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-10-08 ([source](https://doi.org/10.64898/2026.10.01.755864))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.64898/2026.10.01.755864'}`
- [ ] Approved

## 33. Review new paper for relevant claims: Phenylacetylglutamine and memory B cells as mediators of the migraine–tinnitus relationship: a multi-omics two-step Mendelian randomization study

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-10-20 ([source](https://doi.org/10.21203/rs.3.rs-11247243/v1))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.21203/rs.3.rs-11247243/v1'}`
- [ ] Approved

## 34. Review new paper for relevant claims: Pulsatile Tinnitus Alleviated by Contralateral Stent Implantation

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Stroke, first published 2026-10-26 ([source](https://doi.org/10.1161/strokeaha.126.056600))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1161/strokeaha.126.056600'}`
- [ ] Approved

## 35. Review new paper for relevant claims: Pulsatile Tinnitus: A Multimodality Imaging Review of Etiology and Diagnostic Evaluation

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Journal not given, first published 2026-10-16 ([source](https://doi.org/10.21203/rs.3.rs-10916152/v1))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.21203/rs.3.rs-10916152/v1'}`
- [ ] Approved

## 36. Review new paper for relevant claims: Speech Perception in Noise in Individuals With Tinnitus: Top-Down and Bottom-Up Processes

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Ear Hear, first published 2026-10-15 ([source](https://doi.org/10.1097/aud.0000000000001896))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1097/aud.0000000000001896'}`
- [ ] Approved

## 37. Review new paper for relevant claims: The history of tinnitus: from ancient interpretations to contemporary neuroscience and neuromodulation

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Eur Arch Otorhinolaryngol, first published 2026-10-13 ([source](https://doi.org/10.1007/s00405-026-10711-0))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1007/s00405-026-10711-0'}`
- [ ] Approved

## 38. Review new paper for relevant claims: Tinnitus and inhibitory control in adults with bilateral hearing loss: A Stroop study in hearing aid users

- **Why it surfaced:** A new paper matching the condition query was published and is not cited yet
- **Evidence:** Appl Neuropsychol Adult, first published 2026-10-11 ([source](https://doi.org/10.1080/23279095.2026.2747122))
- **Wrong if:** the paper is off-topic, a duplicate of a cited paper, or too low in evidence level to matter
- **Confidence:** low
- **To apply:** `{'cite': 'doi:10.1080/23279095.2026.2747122'}`
- [ ] Approved
