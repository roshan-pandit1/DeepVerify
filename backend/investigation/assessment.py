def assess(stances):
    support = 'supporting' in stances
    contradiction = 'contradicting' in stances
    if support and contradiction:
        return 'mixed', 'Approved source-stance reviews disagree. Inspect passages and source limitations.'
    if support:
        return 'supported', 'At least one source has an approved supporting stance. This is source-level support, not independent proof.'
    if contradiction:
        return 'contradicted', 'At least one source has an approved contradicting stance. Inspect the reviewed passage and its limitations.'
    return 'insufficient evidence', 'No reviewed supporting or contradicting evidence. Missing evidence does not establish falsehood.'
