/**
 * Shared scoring vocabulary.
 *
 * Kept outside the component tree so both the breakdown bars and the detail
 * table describe the score in exactly the same terms.
 */

export const SCORE_COMPONENTS = [
  {
    key: 'skill_score',
    label: 'Skills',
    hint: 'How many of the job’s required skills the resume evidences.',
  },
  {
    key: 'experience_score',
    label: 'Experience',
    hint: 'Years of experience against the job’s stated minimum.',
  },
  {
    key: 'education_score',
    label: 'Education',
    hint: 'Highest qualification against the job’s education requirement.',
  },
  {
    key: 'semantic_score',
    label: 'Semantic',
    hint: 'Embedding cosine similarity between resume and job description.',
  },
  {
    key: 'evidence_score',
    label: 'Evidence',
    hint: 'How well the claims are backed by the uploaded resume text.',
  },
]

/** Education level index -> human label, matching the backend scale (0-5). */
export const EDUCATION_LEVELS = [
  'Not specified',
  'Secondary',
  'Diploma',
  'Bachelor',
  'Master',
  'Doctorate',
]
