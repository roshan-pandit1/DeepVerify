"""Conservative, editable rule-based extraction; no LLM executes source instructions."""
import re


def metadata(text):
    return {
        'entities': sorted(set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text))),
        'dates': sorted(set(re.findall(r'\b(?:19|20)\d{2}(?:-\d{2}-\d{2})?\b', text))),
        'locations': sorted(set(re.findall(r'\b(?:in|at|near) ([A-Z][a-z]+(?: [A-Z][a-z]+)*)', text))),
    }


def extract(text):
    sentences = re.split(r'(?<=[.!?])\s+|[;\n]+', text)
    result = []
    for sentence in sentences:
        # Split independent clauses only when the second clause has an explicit subject and verb.
        for clause in re.split(r'\s+and\s+(?=[A-Z][\w ]{1,60}\s(?:is|was|has|were|are)\b)', sentence):
            clause = clause.strip()
            if len(clause) >= 5 and not clause.endswith('?'):
                result.append(clause)
    result = list(dict.fromkeys(result))
    if not result:
        raise ValueError('No factual assertion candidates found. Enter a declarative claim.')
    if len(result) > 20 or any(len(x) > 1500 for x in result):
        raise ValueError('Use at most 20 assertions, each at most 1,500 characters. Submit a shorter excerpt.')
    return result
